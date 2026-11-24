from datetime import timedelta
from hashlib import sha256
from uuid import uuid4

import pytest

from app.domain.models import CodeChunk, CodeSnapshot, IndexedFile, InvestigationJob, PatchProposal, SnapshotPublication
from app.modules.patches.worker import process_patch
from app.workers.tasks import process_investigation
from test_auth_enrollment import csrf, github_auth as github_auth, sign_in
from test_investigation_evidence import context, stub_retrieval, submit
from test_patch_proposals import DIFF, SOURCE, SyntheticProvider, create, enable, parent_setup, proposal_root


def generated(client, factory, github, monkeypatch):
    parent, snapshot, chunk = parent_setup(client, factory, github, monkeypatch)
    enable(monkeypatch)
    with factory.begin() as db:
        file = db.get(IndexedFile, db.get(CodeChunk, chunk).file_id)
        file.source_coverage = "COMPLETE_FILE"
        file.source_byte_length = len(SOURCE.encode())
        file.source_encoding = "utf-8"
        file.source_normalization = "identity"
    proposal = create(client, parent)
    process_patch(proposal, factory, github, SyntheticProvider())
    return parent, snapshot, chunk, proposal


def export_url(parent, proposal, digest):
    return proposal_root(parent) + f"/{proposal}/export?sha256={digest}"


def test_export_is_exact_validated_bytes_and_approved_review_does_not_execute(client, factory, github_auth, monkeypatch):
    parent, snapshot, _, proposal = generated(client, factory, github_auth, monkeypatch)
    digest = sha256(DIFF.encode()).hexdigest()
    detail = client.get(proposal_root(parent) + f"/{proposal}")
    assert detail.status_code == 200
    data = detail.json()
    assert data["patch_sha256"] == digest and data["export_available"] is True and data["source_stale"] is False
    assert data["source_coverage"][0]["classification"] == "COMPLETE_FILE"
    response = client.get(export_url(parent, proposal, digest))
    assert response.status_code == 200 and response.content == DIFF.encode("utf-8")
    assert response.headers["x-patch-sha256"] == digest
    assert response.headers["x-source-snapshot"] == snapshot and response.headers["x-source-commit"] == "a" * 40
    assert response.headers["content-disposition"] == f'attachment; filename="repopilot-{proposal}.patch"'
    assert response.headers["x-content-type-options"] == "nosniff" and response.headers["cache-control"] == "no-store"
    assert client.get(export_url(parent, proposal, "0" * 64)).status_code == 409
    reviewed = client.post(proposal_root(parent) + f"/{proposal}/review", json={"decision": "approved_for_review"}, headers=csrf(client))
    assert reviewed.status_code == 200 and reviewed.json()["review_state"] == "approved_for_review"
    assert client.get(export_url(parent, proposal, digest)).content == DIFF.encode("utf-8")
    with factory() as db:
        task = db.get(PatchProposal, proposal)
        assert task.status == "static_validated" and task.test_result["status"] == "VALIDATION_UNAVAILABLE"


def test_legacy_requires_explicit_static_recheck_before_export(client, factory, github_auth, monkeypatch):
    parent, _, _, proposal = generated(client, factory, github_auth, monkeypatch)
    digest = sha256(DIFF.encode()).hexdigest()
    with factory.begin() as db:
        task = db.get(PatchProposal, proposal)
        task.static_result = {"status": "passed", "checks": ["snapshot", "source_hash", "evidence", "diff"]}
    detail = client.get(proposal_root(parent) + f"/{proposal}").json()
    assert detail["patch_sha256"] is None and detail["export_available"] is False
    assert client.get(export_url(parent, proposal, digest)).status_code == 409
    check = client.post(proposal_root(parent) + f"/{proposal}/static-validation", headers=csrf(client))
    assert check.status_code == 200 and check.json()["patch_sha256"] == digest
    assert client.get(export_url(parent, proposal, digest)).content == DIFF.encode("utf-8")


@pytest.mark.parametrize("tamper", ["source", "digest", "digest_null", "equivalent_diff", "status", "rejected"])
def test_export_rejects_stale_or_unbound_candidate(client, factory, github_auth, monkeypatch, tamper):
    parent, _, chunk, proposal = generated(client, factory, github_auth, monkeypatch)
    digest = sha256(DIFF.encode()).hexdigest()
    with factory.begin() as db:
        task = db.get(PatchProposal, proposal)
        if tamper == "source":
            db.get(CodeChunk, chunk).source_text = "def process_sync():\n    return 3\n"
        if tamper == "digest":
            task.static_result = {**task.static_result, "patch_sha256": "0" * 64}
        if tamper == "digest_null":
            task.static_result = {**task.static_result, "patch_sha256": None}
        if tamper == "equivalent_diff":
            task.diff = task.diff.replace("@@ -1,2 +1,2 @@", "@@ -1,2 +1,2 @@ same change")
        if tamper == "status":
            task.status = "generating"
        if tamper == "rejected":
            task.review_state = "rejected"
    response = client.get(export_url(parent, proposal, digest))
    assert response.status_code == 409 and DIFF not in response.text


def test_export_checks_auth_tenant_repository_and_required_digest(client, factory, github_auth, monkeypatch):
    parent, _, _, proposal = generated(client, factory, github_auth, monkeypatch)
    digest = sha256(DIFF.encode()).hexdigest()
    url = export_url(parent, proposal, digest)
    assert client.get(proposal_root(parent) + f"/{proposal}/export").status_code == 422
    assert client.get(export_url(parent, proposal, "bad")).status_code == 422
    github_auth.include_repository = False
    assert client.get(url).status_code == 404
    github_auth.include_repository = True
    assert client.post("/v1/auth/logout", headers=csrf(client)).status_code == 200
    assert client.get(url).status_code == 401
    github_auth.user_id = github_auth.account_id = 78
    sign_in(client)
    assert client.get(url).status_code == 404


def test_unknown_file_identity_allows_view_but_refuses_export(client, factory, github_auth, monkeypatch):
    parent, _, chunk, proposal = generated(client, factory, github_auth, monkeypatch)
    with factory.begin() as db:
        file = db.get(IndexedFile, db.get(CodeChunk, chunk).file_id)
        file.source_coverage = "UNKNOWN_COVERAGE"
        file.source_byte_length = None
        file.source_encoding = None
        file.source_normalization = None
    data = client.get(proposal_root(parent) + f"/{proposal}").json()
    assert data["source_coverage"][0]["classification"] == "UNKNOWN_COVERAGE"
    assert data["export_available"] is False and data["export_reason"] == "source_identity_unverified"
    digest = sha256(DIFF.encode()).hexdigest()
    assert client.get(export_url(parent, proposal, digest)).status_code == 409


@pytest.mark.parametrize(("status", "patch_status"), [("tests_passed", "passed"), ("tests_failed", "failed")])
def test_legacy_completed_recheck_preserves_verified_report(client, factory, github_auth, monkeypatch, status, patch_status):
    parent, _, _, proposal = generated(client, factory, github_auth, monkeypatch)
    report = {"status": "COMPLETED", "patched": {"status": patch_status}}
    with factory.begin() as db:
        task = db.get(PatchProposal, proposal)
        task.status = status
        task.static_result = {"status": "passed", "checks": ["snapshot", "source_hash", "evidence", "diff"]}
        task.test_result = report
    calls = []
    monkeypatch.setattr("app.modules.patches.trusted_execution.validate_completed_report",
                        lambda actual, *_: calls.append(actual))
    result = client.post(proposal_root(parent) + f"/{proposal}/static-validation", headers=csrf(client))
    assert result.status_code == 200 and calls == [report]
    with factory() as db:
        task = db.get(PatchProposal, proposal)
        assert task.status == status and task.test_result == report
        assert task.static_result["patch_sha256"] == sha256(DIFF.encode()).hexdigest()


def test_complete_file_with_bounded_evidence_can_export(client, factory, github_auth, monkeypatch):
    _, chunk_id = context(client, factory, github_auth)
    with factory.begin() as db:
        chunk = db.get(CodeChunk, chunk_id)
        file = db.get(IndexedFile, chunk.file_id)
        chunk.start_line, chunk.end_line, chunk.source_text = 1, 1, "def process_sync():\n"
        file.content_hash = sha256(SOURCE.encode()).hexdigest()
        file.source_coverage, file.source_byte_length = "COMPLETE_FILE", len(SOURCE.encode())
        file.source_encoding, file.source_normalization = "utf-8", "identity"
        second = CodeChunk(id=str(uuid4()), file_id=file.id, repository_id=file.repository_id,
                           tenant_id=file.tenant_id, symbol="process_sync", start_line=2, end_line=2,
                           source_text="    return None\n")
        db.add(second)
        second_id = second.id
    stub_retrieval(monkeypatch, factory, second_id)
    parent = submit(client)
    process_investigation(parent, factory, github_auth)
    enable(monkeypatch)
    proposal = create(client, parent)
    process_patch(proposal, factory, github_auth, SyntheticProvider())
    detail = client.get(proposal_root(parent) + f"/{proposal}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["source_coverage"][0]["classification"] == "BOUNDED_EXCERPT"
    assert detail.json()["export_available"] is True
    assert client.get(export_url(parent, proposal, sha256(DIFF.encode()).hexdigest())).content == DIFF.encode()


def test_complete_file_badge_requires_verified_complete_identity(client, factory, github_auth, monkeypatch):
    parent, _, chunk, proposal = generated(client, factory, github_auth, monkeypatch)
    with factory.begin() as db:
        file = db.get(IndexedFile, db.get(CodeChunk, chunk).file_id)
        file.source_coverage = "COMPLETE_FILE"
        file.source_byte_length = len(SOURCE.encode())
        file.source_encoding = "utf-8"
        file.source_normalization = "identity"
    data = client.get(proposal_root(parent) + f"/{proposal}").json()
    assert data["source_coverage"][0]["classification"] == "COMPLETE_FILE"
    with factory.begin() as db:
        file = db.get(IndexedFile, db.get(CodeChunk, chunk).file_id)
        file.source_byte_length += 1
    assert client.get(proposal_root(parent) + f"/{proposal}").status_code == 409


def test_historical_proposal_visible_but_cannot_export(client, factory, github_auth, monkeypatch):
    parent, snapshot, _, proposal = generated(client, factory, github_auth, monkeypatch)
    digest = sha256(DIFF.encode()).hexdigest()
    with factory.begin() as db:
        snap = db.get(CodeSnapshot, snapshot)
        job = db.get(InvestigationJob, parent)
        db.add(SnapshotPublication(snapshot_id=snap.id, repository_id=snap.repository_id, tenant_id=snap.tenant_id,
            commit_sha=snap.commit_sha, file_count=snap.file_count, chunk_count=snap.chunk_count,
            skipped_count=snap.skipped_count, published_at=job.created_at - timedelta(seconds=1)))
        snap.published = False
    detail = client.get(proposal_root(parent) + f"/{proposal}")
    assert detail.status_code == 200
    assert detail.json()["source_stale"] is True and detail.json()["export_available"] is False
    assert client.get(export_url(parent, proposal, digest)).status_code == 409
