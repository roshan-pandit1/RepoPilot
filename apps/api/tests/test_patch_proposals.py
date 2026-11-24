import json
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.domain.models import CodeChunk, CodeSnapshot, IndexedFile, InvestigationEvidence, PatchOutbox, PatchProposal, now
from app.modules.patches.execution import Outcome, TestResult as ExecutionResult, compare
from app.modules.patches.generation import ProviderConfiguration
from app.modules.patches.worker import process_patch
from app.workers.dispatcher import dispatch_once
from app.workers.tasks import process_investigation
from test_auth_enrollment import csrf, github_auth as github_auth, sign_in
from test_investigation_evidence import context, stub_retrieval, submit

SOURCE = "def process_sync():\n    return None\n"
DIFF = ("--- a/src/tasks.py\n+++ b/src/tasks.py\n@@ -1,2 +1,2 @@\n"
        " def process_sync():\n-    return None\n+    return 0\n")


class SyntheticProvider:
    configuration = ProviderConfiguration("synthetic-test", "fixture-v1", requires_credentials=False)

    def generate(self, request, *, timeout_seconds):
        assert timeout_seconds == 30
        return json.dumps({"diff": DIFF, "evidence_ids": [request.untrusted_data.evidence[0].id], "rationale": "Fixture change."})


def parent_setup(client, factory, github, monkeypatch):
    snapshot, chunk_id = context(client, factory, github)
    with factory.begin() as db:
        chunk = db.get(CodeChunk, chunk_id)
        file = db.get(IndexedFile, chunk.file_id)
        chunk.start_line, chunk.end_line, chunk.source_text = 1, 2, SOURCE
        file.content_hash = sha256(SOURCE.encode()).hexdigest()
    stub_retrieval(monkeypatch, factory, chunk_id)
    parent = submit(client)
    process_investigation(parent, factory, github)
    return parent, snapshot, chunk_id


def proposal_root(parent):
    return f"/v1/repositories/902/investigations/{parent}/patch-proposals"


def enable(monkeypatch, provider=None):
    monkeypatch.setattr(get_settings(), "patch_proposals_enabled", True)
    monkeypatch.setattr("app.modules.patches.routes.get_candidate_provider", lambda: provider or SyntheticProvider())


def create(client, parent, request_id=None):
    response = client.post(proposal_root(parent), json={"request_id": str(request_id or uuid4())}, headers=csrf(client))
    assert response.status_code == 202, response.text
    return response.json()["id"]


def test_disabled_defaults_do_not_create_jobs(client, factory, github_auth, monkeypatch):
    parent, _, _ = parent_setup(client, factory, github_auth, monkeypatch)
    response = client.get(proposal_root(parent))
    assert response.status_code == 200 and not response.json()["available"]
    assert client.post(proposal_root(parent), json={"request_id": str(uuid4())}, headers=csrf(client)).status_code == 503
    with factory() as db:
        assert db.scalars(select(PatchProposal)).all() == []


def test_no_provider_is_reported_unavailable(client, factory, github_auth, monkeypatch):
    parent, _, _ = parent_setup(client, factory, github_auth, monkeypatch)
    monkeypatch.setattr(get_settings(), "patch_proposals_enabled", True)
    assert client.get(proposal_root(parent)).json()["available"] is False
    response = client.post(proposal_root(parent), json={"request_id": str(uuid4())}, headers=csrf(client))
    assert response.status_code == 503


@pytest.mark.parametrize(("configuration", "error_code"), [
    (ProviderConfiguration("synthetic-test", "", requires_credentials=False), "invalid_provider_configuration"),
    (ProviderConfiguration("synthetic-test", "fixture-v1"), "provider_credentials_missing"),
])
def test_worker_rejects_incomplete_provider_configuration(client, factory, github_auth, monkeypatch, configuration, error_code):
    parent, _, _ = parent_setup(client, factory, github_auth, monkeypatch)
    provider = SyntheticProvider()
    provider.configuration = configuration
    enable(monkeypatch, provider)
    proposal = create(client, parent)
    process_patch(proposal, factory, github_auth, provider)
    with factory() as db:
        task = db.get(PatchProposal, proposal)
        assert task.status == "failed" and task.error_code == error_code and task.diff is None
        assert db.get(PatchOutbox, proposal).status == "processed"


@pytest.mark.parametrize("field,value", [("repository_id", 903), ("tenant_id", 999),
                                        ("repository_full_name", "other/repository")])
def test_worker_rejects_wrong_request_identity_before_provider_call(client, factory, github_auth, monkeypatch, field, value):
    from app.modules.patches import worker

    parent, _, _ = parent_setup(client, factory, github_auth, monkeypatch)
    enable(monkeypatch)
    proposal = create(client, parent)
    original = worker.assemble_context
    monkeypatch.setattr(worker, "assemble_context", lambda *args, **kwargs: replace(original(*args, **kwargs), **{field: value}))
    class NeverCall(SyntheticProvider):
        def generate(self, request, *, timeout_seconds):
            pytest.fail("mismatched identity reached provider")
    process_patch(proposal, factory, github_auth, NeverCall())
    with factory() as db:
        task = db.get(PatchProposal, proposal)
        assert task.status == "stale" and task.error_code == "source_identity_changed" and task.diff is None


def test_synthetic_proposal_lifecycle_and_unavailable_sandbox(client, factory, github_auth, monkeypatch):
    parent, snapshot, _ = parent_setup(client, factory, github_auth, monkeypatch)
    enable(monkeypatch)
    key = uuid4()
    proposal = create(client, parent, key)
    assert create(client, parent, key) == proposal
    sent = []
    dispatch_once(factory, publish=lambda _: None, publish_sync=lambda _: None, publish_index=lambda _: None,
                  publish_embedding=lambda _: None, publish_investigation=lambda _: None, publish_report=lambda _: None,
                  publish_patch=sent.append)
    assert sent == [proposal]
    process_patch(proposal, factory, github_auth, SyntheticProvider())
    process_patch(proposal, factory, github_auth, SyntheticProvider())
    url = proposal_root(parent) + "/" + proposal
    response = client.get(url)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "static_validated" and data["snapshot_id"] == snapshot
    assert data["diff"] == DIFF and data["provider"] == "synthetic-test"
    assert data["static_result"]["status"] == "passed"
    assert data["test_result"]["status"] == "VALIDATION_UNAVAILABLE"
    assert data["test_result"]["sandbox_used"] is False and data["test_result"]["tests_run"] == []
    assert data["changed_files"][0]["before_sha256"] == sha256(SOURCE.encode()).hexdigest()
    assert client.post(url + "/static-validation", headers=csrf(client)).status_code == 200
    assert client.post(url + "/test-validation", headers=csrf(client)).status_code == 202
    process_patch(proposal, factory, github_auth)
    data = client.get(url).json()
    assert data["status"] == "static_validated" and data["test_result"]["status"] == "VALIDATION_UNAVAILABLE"
    assert client.post(url + "/review", headers=csrf(client), json={"decision": "approved_for_review"}).status_code == 200
    with factory() as db:
        row = db.get(PatchProposal, proposal)
        assert row.review_state == "approved_for_review" and row.reviewer_id is not None
        assert db.get(PatchOutbox, proposal).status == "processed"


def test_invalid_model_output_fails_without_persisting_partial_diff(client, factory, github_auth, monkeypatch):
    parent, _, _ = parent_setup(client, factory, github_auth, monkeypatch)
    enable(monkeypatch)
    proposal = create(client, parent)
    class Invalid(SyntheticProvider):
        def generate(self, context, *, timeout_seconds):
            return '{"diff":"x","diff":"y","evidence_ids":[],"rationale":"x"}'
    process_patch(proposal, factory, github_auth, Invalid())
    with factory() as db:
        row = db.get(PatchProposal, proposal)
        assert row.status == "failed" and row.error_code == "invalid_model_output"
        assert row.diff is None and row.changed_files is None


def test_provider_timeout_and_unsafe_patch_do_not_publish_partial_data(client, factory, github_auth, monkeypatch):
    parent, _, _ = parent_setup(client, factory, github_auth, monkeypatch)
    enable(monkeypatch)
    class Timeout(SyntheticProvider):
        def generate(self, context, *, timeout_seconds):
            raise TimeoutError("private diagnostic")
    timed_out = create(client, parent)
    process_patch(timed_out, factory, github_auth, Timeout())
    class Unsafe(SyntheticProvider):
        def generate(self, request, *, timeout_seconds):
            return json.dumps({"diff": DIFF.replace("src/tasks.py", "../.env"),
                "evidence_ids": [request.untrusted_data.evidence[0].id], "rationale": "fixture"})
    invalid = create(client, parent)
    process_patch(invalid, factory, github_auth, Unsafe())
    with factory() as db:
        assert db.get(PatchProposal, timed_out).error_code == "provider_timeout"
        assert db.get(PatchProposal, invalid).error_code == "validation_failed"
        assert db.get(PatchProposal, timed_out).diff is None and db.get(PatchProposal, invalid).diff is None
        assert db.get(PatchOutbox, timed_out).status == "processed"


def test_provider_exception_is_sanitized_and_never_publishes_partial_output(client, factory, github_auth, monkeypatch, caplog):
    parent, _, _ = parent_setup(client, factory, github_auth, monkeypatch)
    enable(monkeypatch)
    proposal = create(client, parent)
    class Broken(SyntheticProvider):
        def generate(self, request, *, timeout_seconds):
            raise RuntimeError("synthetic private provider diagnostic")
    process_patch(proposal, factory, github_auth, Broken())
    with factory() as db:
        task = db.get(PatchProposal, proposal)
        assert task.status == "failed" and task.error_code == "worker_failed"
        assert task.diff is None and task.changed_files is None
    assert "synthetic private provider diagnostic" not in caplog.text


def test_patch_lease_override_is_restricted_to_test_environment(monkeypatch):
    from pydantic import ValidationError
    from app.core.config import Settings

    for name in ("PATCH_WORKER_LEASE_SECONDS", "APP_ENV"):
        monkeypatch.delenv(name, raising=False)
    base = {"database_url": "sqlite://", "github_webhook_secret": "x" * 32,
            "demo_auth_enabled": False, "_env_file": None}
    assert Settings(**base, app_env="test", patch_worker_lease_seconds=5).patch_worker_lease_seconds == 5
    assert Settings(**base, app_env="production").patch_worker_lease_seconds == 120
    for env in ("development", "production"):
        with pytest.raises(ValidationError):
            Settings(**base, app_env=env, patch_worker_lease_seconds=5)
    for seconds in (0, 121):
        with pytest.raises(ValidationError):
            Settings(**base, app_env="test", patch_worker_lease_seconds=seconds)


def test_expired_worker_lease_is_reclaimed_without_partial_result(client, factory, github_auth, monkeypatch):
    parent, _, _ = parent_setup(client, factory, github_auth, monkeypatch)
    enable(monkeypatch)
    proposal = create(client, parent)
    class Disappears(SyntheticProvider):
        def generate(self, context, *, timeout_seconds):
            raise SystemExit("simulated disappearance")
    with pytest.raises(SystemExit):
        process_patch(proposal, factory, github_auth, Disappears())
    with factory.begin() as db:
        task = db.get(PatchProposal, proposal)
        assert task.status == "generating" and task.diff is None
        assert db.get(PatchOutbox, proposal).status == "pending"
        task.lease_expires_at = now() - timedelta(seconds=1)
    process_patch(proposal, factory, github_auth, SyntheticProvider())
    with factory() as db:
        task = db.get(PatchProposal, proposal)
        assert task.status == "static_validated" and task.attempts == 2
        assert db.get(PatchOutbox, proposal).status == "processed"


def test_expired_worker_error_cannot_finalize_or_consume_outbox(client, factory, github_auth, monkeypatch):
    parent, _, _ = parent_setup(client, factory, github_auth, monkeypatch)
    enable(monkeypatch)
    proposal = create(client, parent)

    class ExpiredFailure(SyntheticProvider):
        def generate(self, context, *, timeout_seconds):
            with factory.begin() as db:
                task = db.get(PatchProposal, proposal)
                task.lease_expires_at = now() - timedelta(seconds=1)
            raise TimeoutError("synthetic expired failure")

    process_patch(proposal, factory, github_auth, ExpiredFailure())
    with factory() as db:
        task = db.get(PatchProposal, proposal)
        assert task.status == "generating" and task.error_code is None
        assert task.diff is None and task.lease_token is not None
        assert db.get(PatchOutbox, proposal).status == "pending"
    process_patch(proposal, factory, github_auth, SyntheticProvider())
    with factory() as db:
        task = db.get(PatchProposal, proposal)
        assert task.status == "static_validated" and task.attempts == 2
        assert db.get(PatchOutbox, proposal).status == "processed"


@pytest.mark.parametrize("returns_candidate", [False, True])
def test_superseded_worker_cannot_publish_failure_or_candidate(client, factory, github_auth, monkeypatch, returns_candidate):
    parent, _, _ = parent_setup(client, factory, github_auth, monkeypatch)
    enable(monkeypatch)
    proposal = create(client, parent)
    newer_lease = str(uuid4())

    class Superseded(SyntheticProvider):
        def generate(self, context, *, timeout_seconds):
            with factory.begin() as db:
                task = db.get(PatchProposal, proposal)
                task.lease_token = newer_lease
                task.lease_expires_at = now() + timedelta(seconds=120)
            if not returns_candidate:
                raise TimeoutError("synthetic stale worker failure")
            return super().generate(context, timeout_seconds=timeout_seconds)

    process_patch(proposal, factory, github_auth, Superseded())
    with factory() as db:
        task = db.get(PatchProposal, proposal)
        assert task.status == "generating" and task.lease_token == newer_lease
        assert task.error_code is None and task.diff is None
        assert db.get(PatchOutbox, proposal).status == "pending"


@pytest.mark.parametrize("tamper", ["source", "hash", "snapshot", "range", "evidence"])
def test_pre_provider_source_and_evidence_tampering_fails_closed(client, factory, github_auth, monkeypatch, tamper):
    parent, snapshot, chunk_id = parent_setup(client, factory, github_auth, monkeypatch)
    enable(monkeypatch)
    proposal = create(client, parent)
    calls = []

    class RecordingProvider(SyntheticProvider):
        def generate(self, context, *, timeout_seconds):
            calls.append(True)
            return super().generate(context, timeout_seconds=timeout_seconds)

    with factory.begin() as db:
        chunk = db.get(CodeChunk, chunk_id)
        file = db.get(IndexedFile, chunk.file_id)
        evidence = db.scalar(select(InvestigationEvidence).where(InvestigationEvidence.job_id == parent))
        subject, attr, value = {
            "source": (chunk, "source_text", "def process_sync():\n    return 3\n"),
            "hash": (file, "content_hash", "0" * 64),
            "snapshot": (db.get(CodeSnapshot, snapshot), "commit_sha", "b" * 40),
            "range": (chunk, "end_line", chunk.end_line + 1),
            "evidence": (evidence, "chunk_fingerprint", "0" * 64),
        }[tamper]
        original = getattr(subject, attr)
        subject_id = subject.id
        subject_type = type(subject)
        setattr(subject, attr, value)
    process_patch(proposal, factory, github_auth, RecordingProvider())
    assert calls == []
    with factory.begin() as db:
        task = db.get(PatchProposal, proposal)
        assert task.status == "stale" and task.error_code == "issue_or_snapshot_changed"
        assert task.diff is None and db.get(PatchOutbox, proposal).status == "processed"
        setattr(db.get(subject_type, subject_id), attr, original)
    unaffected = create(client, parent)
    process_patch(unaffected, factory, github_auth, RecordingProvider())
    assert calls == [True]
    with factory() as db:
        assert db.get(PatchProposal, unaffected).status == "static_validated"


@pytest.mark.parametrize("tamper_during_provider", [False, True])
def test_complete_file_length_mismatch_rejects_candidate(client, factory, github_auth, monkeypatch,
                                                         tamper_during_provider):
    parent, _, chunk_id = parent_setup(client, factory, github_auth, monkeypatch)
    enable(monkeypatch)
    with factory.begin() as db:
        file = db.get(IndexedFile, db.get(CodeChunk, chunk_id).file_id)
        file.source_coverage = "COMPLETE_FILE"
        file.source_byte_length = len(SOURCE.encode("utf-8"))
        file.source_encoding = "utf-8"
        file.source_normalization = "identity"
    proposal = create(client, parent)
    calls = []

    def corrupt_length():
        with factory.begin() as db:
            file = db.get(IndexedFile, db.get(CodeChunk, chunk_id).file_id)
            file.source_byte_length += 1

    class RecordingProvider(SyntheticProvider):
        def generate(self, context, *, timeout_seconds):
            calls.append(True)
            if tamper_during_provider:
                corrupt_length()
            return super().generate(context, timeout_seconds=timeout_seconds)

    if not tamper_during_provider:
        corrupt_length()
    process_patch(proposal, factory, github_auth, RecordingProvider())
    assert len(calls) == int(tamper_during_provider)
    with factory() as db:
        task = db.get(PatchProposal, proposal)
        assert task.status == "failed" and task.error_code == "source_identity_or_size"
        assert task.diff is None and db.get(PatchOutbox, proposal).status == "processed"


def test_cancel_during_generation_fences_late_provider_output(client, factory, github_auth, monkeypatch):
    parent, _, _ = parent_setup(client, factory, github_auth, monkeypatch)
    enable(monkeypatch)
    proposal = create(client, parent)
    class Cancelled(SyntheticProvider):
        def generate(self, context, *, timeout_seconds):
            response = client.post(proposal_root(parent) + f"/{proposal}/review", headers=csrf(client),
                                   json={"decision": "rejected"})
            assert response.status_code == 200
            return super().generate(context, timeout_seconds=timeout_seconds)
    process_patch(proposal, factory, github_auth, Cancelled())
    with factory() as db:
        task = db.get(PatchProposal, proposal)
        assert task.status == "failed" and task.error_code == "reviewer_cancelled"
        assert task.diff is None and task.review_state == "rejected"
        assert db.get(PatchOutbox, proposal).status == "processed"


def test_postgres_concurrent_patch_requests_are_idempotent(client, factory, github_auth, monkeypatch):
    if factory.kw["bind"].dialect.name != "postgresql":
        pytest.skip("PostgreSQL row locks are required")
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from fastapi.testclient import TestClient
    from app.main import app

    parent, _, _ = parent_setup(client, factory, github_auth, monkeypatch)
    enable(monkeypatch)
    key, cookies, headers, gate = str(uuid4()), dict(client.cookies), csrf(client), Barrier(2)

    def start():
        with TestClient(app, cookies=cookies) as other:
            gate.wait(timeout=10)
            response = other.post(proposal_root(parent), headers=headers, json={"request_id": key})
            return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: start(), range(2)))
    assert [status for status, _ in results] == [202, 202]
    assert results[0][1]["id"] == results[1][1]["id"]
    with factory() as db:
        assert len(db.scalars(select(PatchProposal)).all()) == 1
        assert len(db.scalars(select(PatchOutbox)).all()) == 1


def test_source_change_during_generation_never_publishes_diff(client, factory, github_auth, monkeypatch):
    parent, _, chunk_id = parent_setup(client, factory, github_auth, monkeypatch)
    enable(monkeypatch)
    proposal = create(client, parent)
    class Tampering(SyntheticProvider):
        def generate(self, context, *, timeout_seconds):
            with factory.begin() as db:
                db.get(CodeChunk, chunk_id).source_text = "def process_sync():\n    return 3\n"
            return super().generate(context, timeout_seconds=timeout_seconds)
    process_patch(proposal, factory, github_auth, Tampering())
    with factory() as db:
        task = db.get(PatchProposal, proposal)
        assert task.status == "stale" and task.error_code == "issue_or_snapshot_changed"
        assert task.diff is None and task.changed_files is None


def test_dispatch_retry_limit_is_visible_and_does_not_publish_again(client, factory, github_auth, monkeypatch):
    parent, _, _ = parent_setup(client, factory, github_auth, monkeypatch)
    enable(monkeypatch)
    proposal = create(client, parent)
    with factory.begin() as db:
        db.get(PatchOutbox, proposal).attempts = 20
    sent = []
    dispatch_once(factory, publish=lambda _: None, publish_sync=lambda _: None, publish_index=lambda _: None,
                  publish_embedding=lambda _: None, publish_investigation=lambda _: None, publish_report=lambda _: None,
                  publish_patch=sent.append)
    assert sent == []
    data = client.get(proposal_root(parent) + "/" + proposal).json()
    assert data["status"] == "queued" and data["dispatch_status"] == "failed"


def test_active_proposal_limit_does_not_break_idempotency(client, factory, github_auth, monkeypatch):
    parent, _, _ = parent_setup(client, factory, github_auth, monkeypatch)
    enable(monkeypatch)
    key = uuid4()
    first = create(client, parent, key)
    create(client, parent)
    create(client, parent)
    assert create(client, parent, key) == first
    response = client.post(proposal_root(parent), json={"request_id": str(uuid4())}, headers=csrf(client))
    assert response.status_code == 429
    cancelled = client.post(proposal_root(parent) + f"/{first}/review", json={"decision": "rejected"}, headers=csrf(client))
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "failed"
    create(client, parent)


def test_tampered_source_and_snapshot_are_rejected(client, factory, github_auth, monkeypatch):
    parent, snapshot, chunk_id = parent_setup(client, factory, github_auth, monkeypatch)
    enable(monkeypatch)
    proposal = create(client, parent)
    process_patch(proposal, factory, github_auth, SyntheticProvider())
    url = proposal_root(parent) + "/" + proposal
    with factory.begin() as db:
        db.get(CodeChunk, chunk_id).source_text = "def process_sync():\n    return 2\n"
    assert client.get(url).status_code == 409
    with factory.begin() as db:
        db.get(CodeChunk, chunk_id).source_text = SOURCE
        db.get(CodeSnapshot, snapshot).commit_sha = "b" * 40
    assert client.get(url).status_code == 409


def test_unverified_test_results_cannot_be_presented_as_passing(client, factory, github_auth, monkeypatch):
    parent, _, _ = parent_setup(client, factory, github_auth, monkeypatch)
    enable(monkeypatch)
    proposal = create(client, parent)
    process_patch(proposal, factory, github_auth, SyntheticProvider())
    with factory.begin() as db:
        task = db.get(PatchProposal, proposal)
        task.test_result = {"status": "passed", "sandbox_used": True, "tests_run": ["unverified"]}
    url = proposal_root(parent) + "/" + proposal
    assert client.get(url).status_code == 409
    with factory.begin() as db:
        db.get(PatchProposal, proposal).status = "tests_passed"
    assert client.get(proposal_root(parent)).json()["items"][0]["status"] == "failed"


def test_authorization_and_csrf_are_enforced(client, factory, github_auth, monkeypatch):
    parent, _, _ = parent_setup(client, factory, github_auth, monkeypatch)
    enable(monkeypatch)
    assert client.post(proposal_root(parent), json={"request_id": str(uuid4())}).status_code == 403
    proposal = create(client, parent)
    github_auth.include_repository = False
    assert client.get(proposal_root(parent) + "/" + proposal).status_code == 404
    github_auth.include_repository = True
    assert client.post("/v1/auth/logout", headers=csrf(client)).status_code == 200
    github_auth.user_id = github_auth.account_id = 78
    sign_in(client)
    assert client.get(proposal_root(parent) + "/" + proposal).status_code == 404


@pytest.mark.parametrize(("baseline", "patched", "expected"), [
    ("failed", "passed", Outcome.BASELINE_FAILED_PATCH_PASSED),
    ("passed", "passed", Outcome.BOTH_PASSED),
    ("failed", "failed", Outcome.BOTH_FAILED),
    ("passed", "failed", Outcome.BASELINE_PASSED_PATCH_FAILED),
    ("passed", "timeout", Outcome.TIMEOUT),
    ("unavailable", "passed", Outcome.TEST_UNAVAILABLE),
    ("blocked", "passed", Outcome.EXECUTION_BLOCKED),
    ("unknown", "passed", Outcome.INCONCLUSIVE),
])
def test_before_after_comparison_only(baseline, patched, expected):
    assert compare(ExecutionResult(baseline), ExecutionResult(patched)) == expected
