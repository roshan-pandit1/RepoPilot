"""Fake-only, separately authorized input-token counting and replay protection."""

import json
import socket
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from app.domain.models import (
    AuthSession,
    CodeChunk,
    CodeSnapshot,
    Installation,
    InvestigationExecutorApproval,
    InvestigationJob,
    InvestigationReportJob,
    InvestigationRealReport,
    InvestigationTokenCount,
    InvestigationUsageReservation,
    now,
)
from app.evaluation.experiment_executor import canonical, digest, execute_fake, write_private
from app.evaluation.token_counting import (
    COUNT_ENDPOINT,
    FAKE_ACCOUNT,
    FAKE_PROJECT,
    _mark_fake_count_sent,
    count_projection,
    create_fake_count_approval,
    run_fake_count,
    validate_fake_count_for_generation,
)
from app.modules.investigation import openai_provider
from app.modules.investigation.report_model import ModelError
from app.modules.auth.session import utc
from test_auth_enrollment import github_auth as github_auth
from test_experiment_executor import setup_fixture, valid_output
from test_real_report_foundation import response

ROOT = Path(__file__).resolve().parents[3]


def test_utc_normalizes_aware_values_from_non_utc_database_sessions():
    value = datetime(2026, 1, 1, 12, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    normalized = utc(value)
    assert normalized == datetime(2026, 1, 1, 6, 30, tzinfo=timezone.utc)
    assert normalized.utcoffset() == timedelta(0)


@pytest.fixture
def scenario(client, factory, github_auth, monkeypatch, tmp_path):
    item = setup_fixture(client, factory, github_auth, monkeypatch)
    private = tmp_path / "review"
    private.mkdir(mode=0o700)
    write_private(private, item["payload"], item["manifest"])
    item["private"] = private
    with factory() as db:
        item["tenant"] = db.get(InvestigationReportJob, item["job"]).tenant_id
    item["args"] = {
        "job_id": item["job"],
        "experiment_id": item["experiment"],
        "tenant_id": item["tenant"],
        "account": FAKE_ACCOUNT,
        "project": FAKE_PROJECT,
        "snapshot_id": item["snapshot"],
    }
    item["count"] = create_fake_count_approval(
        factory,
        ROOT,
        job_id=item["job"],
        experiment_id=item["experiment"],
        tenant_id=item["tenant"],
        account=FAKE_ACCOUNT,
        project=FAKE_PROJECT,
        review_directory=private,
        generation_sha256=item["manifest"]["request_sha256"],
        manifest_sha256=digest(canonical(item["manifest"])),
        expires_at=now() + timedelta(minutes=10),
        acknowledge_count_disclosure=True,
    )
    return item


def run(factory, item, handler, **overrides):
    return run_fake_count(
        factory,
        ROOT,
        count_id=item["count"],
        transport=httpx.MockTransport(handler),
        **{**item["args"], **overrides},
    )


def preflight(factory, item, **overrides):
    return validate_fake_count_for_generation(
        factory, ROOT, count_id=item["count"], **{**item["args"], **overrides}
    )


def test_count_projection_preserves_context_and_schema(scenario):
    generation = scenario["payload"]
    count = count_projection(generation)
    assert set(count) == {"model", "instructions", "input", "text", "truncation"}
    assert (
        count["input"] == generation["input"]
        and count["instructions"] == generation["instructions"]
    )
    assert count["text"]["format"]["schema"] == generation["text"]["format"]["schema"]
    assert canonical(count) != canonical(generation) and digest(canonical(count)) != digest(
        canonical(generation)
    )


def test_duplicate_count_approval_is_rejected(factory, scenario):
    with pytest.raises(ModelError, match="count_approval_invalid"):
        create_fake_count_approval(
            factory, ROOT, job_id=scenario["job"], experiment_id=scenario["experiment"],
            tenant_id=scenario["tenant"], account=FAKE_ACCOUNT, project=FAKE_PROJECT,
            review_directory=scenario["private"], generation_sha256=scenario["manifest"]["request_sha256"],
            manifest_sha256=digest(canonical(scenario["manifest"])), expires_at=now() + timedelta(minutes=10),
            acknowledge_count_disclosure=True,
        )


def test_count_approval_requires_explicit_disclosure_acknowledgement(factory, scenario):
    with pytest.raises(ModelError, match="count_approval_invalid"):
        create_fake_count_approval(
            factory, ROOT, job_id=scenario["job"], experiment_id=scenario["experiment"],
            tenant_id=scenario["tenant"], account=FAKE_ACCOUNT, project=FAKE_PROJECT,
            review_directory=scenario["private"], generation_sha256=scenario["manifest"]["request_sha256"],
            manifest_sha256=digest(canonical(scenario["manifest"])), expires_at=now() + timedelta(minutes=10),
        )


@pytest.mark.parametrize(
    "feature", ["tools", "conversation", "previous_response_id", "reasoning", "metadata"]
)
def test_unsupported_generation_features_are_rejected(scenario, feature):
    generation = {**scenario["payload"], feature: []}
    with pytest.raises(ModelError, match="count_input_invalid"):
        count_projection(generation)


def test_fake_count_is_one_use_and_does_not_touch_generation_or_ledger(factory, scenario, caplog):
    calls = []

    def handler(request):
        calls.append(request)
        assert str(request.url) == COUNT_ENDPOINT and request.method == "POST"
        assert request.headers["openai-organization"] == FAKE_ACCOUNT
        assert request.headers["openai-project"] == FAKE_PROJECT
        assert digest(request.content) == digest(canonical(count_projection(scenario["payload"])))
        with pytest.raises(OSError, match="evaluation_network_blocked"):
            socket.getaddrinfo("api.openai.com", 443)
        return httpx.Response(200, json={"object": "response.input_tokens", "input_tokens": 1200})

    assert run(factory, scenario, handler) == 1200
    assert preflight(factory, scenario) == 1200
    with pytest.raises(ModelError, match="count_approval_invalid"):
        run(factory, scenario, handler)
    assert len(calls) == 1
    with factory() as db:
        count = db.get(InvestigationTokenCount, scenario["count"])
        approval = db.get(InvestigationExecutorApproval, scenario["approval"])
        assert (
            count.status == "complete" and count.input_tokens == 1200 and count.mode == "simulated"
        )
        assert count.count_sha256 == digest(canonical(count_projection(scenario["payload"])))
        assert count.generation_sha256 == scenario["manifest"]["request_sha256"]
        assert approval.state == "ready" and approval.mode == "simulated"
        assert db.scalar(select(InvestigationUsageReservation)) is None
        assert db.scalar(select(InvestigationRealReport)) is None
        assert FAKE_ACCOUNT not in repr(count.__dict__) and FAKE_PROJECT not in repr(count.__dict__)
    assert "synthetic-fake-only-key" not in caplog.text
    assert scenario["payload"]["input"][0]["content"] not in caplog.text


@pytest.mark.parametrize(
    "variant",
    [
        "missing",
        "expired",
        "model",
        "project",
        "account",
        "fixture",
        "snapshot",
        "manifest",
        "pricing",
        "output_limit",
        "invalidated",
        "tenant",
        "experiment",
    ],
)
def test_invalid_count_binding_fails_before_send(factory, scenario, monkeypatch, variant):
    overrides = {}
    if variant == "missing":
        scenario["count"] = str(uuid4())
    elif variant in {"project", "account"}:
        overrides[variant] = "unapproved"
    elif variant == "snapshot":
        overrides["snapshot_id"] = str(uuid4())
    elif variant == "tenant":
        overrides["tenant_id"] = 999
    elif variant == "experiment":
        overrides["experiment_id"] = str(uuid4())
    elif variant == "pricing":
        monkeypatch.setattr("app.evaluation.token_counting.PRICING_POLICY", "unreviewed")
    else:
        with factory.begin() as db:
            row = db.get(InvestigationTokenCount, scenario["count"])
            if variant == "expired":
                row.expires_at = now() - timedelta(seconds=1)
            elif variant == "model":
                row.model = "other-model"
            elif variant == "fixture":
                row.fixture_id = "other-fixture"
            elif variant == "manifest":
                row.manifest_sha256 = "a" * 64
            elif variant == "output_limit":
                row.max_output_tokens = 100
            elif variant == "invalidated":
                row.invalidated_at = now()
    calls = []
    with pytest.raises((ModelError, ValueError)):
        run(factory, scenario, lambda request: calls.append(request), **overrides)
    assert not calls


@pytest.mark.parametrize("change", ["source", "schema"])
def test_changed_source_or_schema_invalidates_count(factory, scenario, monkeypatch, change):
    if change == "source":
        with factory.begin() as db:
            db.get(CodeChunk, scenario["chunk"]).source_text += "\n# modified"
    else:
        original = openai_provider.strict_schema
        monkeypatch.setattr(
            openai_provider, "strict_schema", lambda: {**original(), "description": "changed"}
        )
    calls = []
    with pytest.raises((ModelError, ValueError)):
        run(factory, scenario, lambda request: calls.append(request))
    assert not calls


@pytest.mark.parametrize(
    "variant",
    ["project", "account", "snapshot", "tenant", "expired", "invalidated", "model", "fixture",
     "manifest", "pricing", "output_limit", "generation_hash", "count_hash", "source_commit", "source", "schema"],
)
def test_generation_preflight_rejects_changed_count_binding(factory, scenario, monkeypatch, variant):
    assert run(factory, scenario, lambda request: httpx.Response(200, json={
        "object": "response.input_tokens", "input_tokens": 12})) == 12
    overrides = {}
    if variant in {"project", "account"}:
        overrides[variant] = "unapproved"
    elif variant == "snapshot":
        overrides["snapshot_id"] = str(uuid4())
    elif variant == "tenant":
        overrides["tenant_id"] = 999
    elif variant == "pricing":
        monkeypatch.setattr("app.evaluation.token_counting.PRICING_POLICY", "unreviewed")
    elif variant == "source":
        with factory.begin() as db:
            db.get(CodeChunk, scenario["chunk"]).source_text += "\n# modified after count"
    elif variant == "schema":
        original = openai_provider.strict_schema
        monkeypatch.setattr(openai_provider, "strict_schema", lambda: {**original(), "description": "changed"})
    else:
        with factory.begin() as db:
            row = db.get(InvestigationTokenCount, scenario["count"])
            if variant == "expired":
                row.expires_at = now() - timedelta(seconds=1)
            elif variant == "invalidated":
                row.invalidated_at = now()
            elif variant == "model":
                row.model = "other-model"
            elif variant == "fixture":
                row.fixture_id = "other-fixture"
            elif variant == "manifest":
                row.manifest_sha256 = "a" * 64
            elif variant == "output_limit":
                row.max_output_tokens = 100
            elif variant == "generation_hash":
                row.generation_sha256 = "a" * 64
            elif variant == "count_hash":
                row.count_sha256 = "a" * 64
            elif variant == "source_commit":
                db.get(InvestigationJob, scenario["parent"]).snapshot_commit_sha = "a" * 40
    with pytest.raises((ModelError, ValueError)):
        preflight(factory, scenario, **overrides)


def test_revoked_access_blocks_count_before_send(factory, scenario):
    with factory.begin() as db:
        db.get(Installation, 901).active = False
    calls = []
    with pytest.raises(ModelError, match="count_access_denied"):
        run(factory, scenario, lambda request: calls.append(request))
    assert not calls


def test_count_record_cannot_contain_missing_result_or_actual_mode(factory, scenario):
    from sqlalchemy.exc import IntegrityError

    assert run(factory, scenario, lambda request: httpx.Response(200, json={
        "object": "response.input_tokens", "input_tokens": 0})) == 0
    with pytest.raises(IntegrityError):
        with factory.begin() as db:
            db.get(InvestigationTokenCount, scenario["count"]).input_tokens = None
    with pytest.raises(IntegrityError):
        with factory.begin() as db:
            db.get(InvestigationTokenCount, scenario["count"]).mode = "actual"
    with pytest.raises(IntegrityError):
        with factory.begin() as db:
            db.get(InvestigationTokenCount, scenario["count"]).tenant_id = 999


def test_sent_marker_without_result_blocks_replay(factory, scenario):
    _mark_fake_count_sent(factory, ROOT, count_id=scenario["count"], **scenario["args"])
    calls = []
    with pytest.raises(ModelError, match="count_approval_invalid"):
        run(factory, scenario, lambda request: calls.append(request))
    assert not calls
    with factory() as db:
        assert db.get(InvestigationTokenCount, scenario["count"]).status == "sent"


@pytest.mark.parametrize(
    "case",
    [
        "invalid_json",
        "missing",
        "wrong_object",
        "negative",
        "boolean",
        "fraction",
        "extra",
        "duplicate",
        "too_large",
        "provider_error",
        "redirect",
        "timeout",
    ],
)
def test_bad_or_uncertain_count_never_retries(factory, scenario, case):
    calls = []

    def handler(request):
        calls.append(request)
        if case == "timeout":
            raise httpx.ReadTimeout("synthetic")
        if case == "provider_error":
            return httpx.Response(500)
        if case == "redirect":
            return httpx.Response(302, headers={"Location": "https://attacker.invalid"})
        if case == "invalid_json":
            return httpx.Response(200, content=b"{")
        if case == "duplicate":
            return httpx.Response(
                200, content=b'{"object":"response.input_tokens","input_tokens":1,"input_tokens":2}'
            )
        payload = {"object": "response.input_tokens", "input_tokens": 1}
        if case == "missing":
            del payload["input_tokens"]
        elif case == "wrong_object":
            payload["object"] = "wrong"
        elif case == "negative":
            payload["input_tokens"] = -1
        elif case == "boolean":
            payload["input_tokens"] = True
        elif case == "fraction":
            payload["input_tokens"] = 1.5
        elif case == "extra":
            payload["extra"] = "unexpected"
        elif case == "too_large":
            payload["input_tokens"] = 1_050_001
        return httpx.Response(200, json=payload)

    with pytest.raises(ModelError, match="count_billing_unknown"):
        run(factory, scenario, handler)
    with pytest.raises(ModelError, match="count_approval_invalid"):
        run(factory, scenario, handler)
    assert len(calls) == 1
    with factory() as db:
        row = db.get(InvestigationTokenCount, scenario["count"])
        assert row.status == "uncertain" and row.input_tokens is None
        assert db.scalar(select(InvestigationUsageReservation)) is None


def test_count_over_threshold_is_retained_but_never_accepted(factory, scenario):
    with factory.begin() as db:
        row = db.get(InvestigationTokenCount, scenario["count"])
        # A changed threshold must invalidate the binding; prepare a separate valid lower threshold below instead.
        assert row.max_input_tokens == 16_384
    with pytest.raises(ModelError, match="count_limit_exceeded"):
        run(
            factory,
            scenario,
            lambda request: httpx.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 16_385}
            ),
        )
    with pytest.raises(ModelError, match="count_limit_exceeded"):
        preflight(factory, scenario)
    with factory() as db:
        row = db.get(InvestigationTokenCount, scenario["count"])
        assert row.status == "complete" and row.input_tokens == 16_385


def test_crash_before_and_after_send_are_distinguished(factory, scenario, monkeypatch):
    from app.evaluation import token_counting

    original = token_counting._mark_fake_count_sent
    monkeypatch.setattr(
        token_counting,
        "_mark_fake_count_sent",
        lambda *args, **kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
    )
    with pytest.raises(KeyboardInterrupt):
        run(factory, scenario, lambda request: pytest.fail("not sent"))
    with factory() as db:
        assert db.get(InvestigationTokenCount, scenario["count"]).status == "ready"
    monkeypatch.setattr(token_counting, "_mark_fake_count_sent", original)
    calls = []

    def interrupted(request):
        calls.append(request)
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        run(factory, scenario, interrupted)
    with pytest.raises(ModelError, match="count_approval_invalid"):
        run(factory, scenario, interrupted)
    with factory() as db:
        assert db.get(InvestigationTokenCount, scenario["count"]).status == "uncertain"
    assert len(calls) == 1


def test_revocation_blocks_count_and_completed_preflight(factory, scenario):
    def revoke(request):
        with factory.begin() as db:
            db.get(Installation, 901).active = False
        return httpx.Response(200, json={"object": "response.input_tokens", "input_tokens": 42})

    with pytest.raises(ModelError, match="count_access_denied"):
        run(factory, scenario, revoke)
    with pytest.raises(ModelError, match="count_access_denied"):
        preflight(factory, scenario)
    with factory.begin() as db:
        assert db.get(InvestigationTokenCount, scenario["count"]).status == "uncertain"
        db.get(Installation, 901).active = True
    with pytest.raises(ModelError, match="count_approval_invalid"):
        preflight(factory, scenario)


def test_count_approval_cannot_authorize_generation_or_live_transport(
    factory, github_auth, scenario
):
    with pytest.raises(ModelError, match="approval_invalid"):
        execute_fake(
            factory,
            root=ROOT,
            job_id=scenario["job"],
            experiment_id=scenario["experiment"],
            approval_id=scenario["count"],
            manifest=scenario["manifest"],
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=valid_output(request))
            ),
            github=github_auth,
        )
    with pytest.raises(ModelError, match="count_not_enabled"):
        run_fake_count(
            factory, ROOT, count_id=scenario["count"], transport=None, **scenario["args"]
        )
    with pytest.raises(ModelError, match="count_approval_invalid"):
        run_fake_count(
            factory,
            ROOT,
            count_id=scenario["approval"],
            transport=httpx.MockTransport(lambda req: None),
            **scenario["args"],
        )


def test_counted_fake_generation_still_requires_separate_approval_and_full_reservation(factory, github_auth, scenario):
    assert run(factory, scenario, lambda request: httpx.Response(200, json={
        "object": "response.input_tokens", "input_tokens": 1200})) == 1200
    calls = []
    def handler(request):
        calls.append(request)
        return response(json.dumps(valid_output(request)))
    execute_fake(factory, root=ROOT, job_id=scenario["job"], experiment_id=scenario["experiment"],
        approval_id=scenario["approval"], manifest=scenario["manifest"], transport=httpx.MockTransport(handler),
        github=github_auth, count_id=scenario["count"], count_account=FAKE_ACCOUNT, count_project=FAKE_PROJECT)
    with factory() as db:
        assert db.get(InvestigationReportJob, scenario["job"]).status == "completed"
        assert db.get(InvestigationExecutorApproval, scenario["approval"]).state == "consumed"
        assert db.get(InvestigationTokenCount, scenario["count"]).status == "complete"
        assert db.scalar(select(InvestigationUsageReservation)).reserved_microusd == 5_815_551
        assert db.scalar(select(InvestigationRealReport)) is not None
    assert len(calls) == 1
    with pytest.raises(ModelError, match="approval_invalid"):
        execute_fake(factory, root=ROOT, job_id=scenario["job"], experiment_id=scenario["experiment"],
            approval_id=scenario["approval"], manifest=scenario["manifest"], transport=httpx.MockTransport(handler),
            github=github_auth, count_id=scenario["count"], count_account=FAKE_ACCOUNT, count_project=FAKE_PROJECT)
    assert len(calls) == 1


def test_count_invalidation_before_generation_send_marker_prevents_publication(factory, github_auth, scenario, monkeypatch):
    from app.evaluation import experiment_executor

    assert run(factory, scenario, lambda request: httpx.Response(200, json={
        "object": "response.input_tokens", "input_tokens": 10})) == 10
    original = experiment_executor.ApprovedFakeModel._mark_sent
    def invalidate(model, *args, **kwargs):
        with factory.begin() as db:
            db.get(InvestigationTokenCount, scenario["count"]).invalidated_at = now()
        return original(model, *args, **kwargs)
    monkeypatch.setattr(experiment_executor.ApprovedFakeModel, "_mark_sent", invalidate)
    calls = []
    execute_fake(factory, root=ROOT, job_id=scenario["job"], experiment_id=scenario["experiment"],
        approval_id=scenario["approval"], manifest=scenario["manifest"],
        transport=httpx.MockTransport(lambda request: calls.append(request)), github=github_auth,
        count_id=scenario["count"], count_account=FAKE_ACCOUNT, count_project=FAKE_PROJECT)
    with factory() as db:
        assert db.get(InvestigationReportJob, scenario["job"]).status == "failed"
        assert db.get(InvestigationExecutorApproval, scenario["approval"]).state == "ready"
        assert db.scalar(select(InvestigationRealReport)) is None
    assert not calls


@pytest.mark.parametrize('change', [
    'model', 'instructions', 'input', 'schema', 'cache', 'output_limit', 'truncation', 'tier', 'store',
])
def test_counted_generation_rejects_changed_body_at_send_marker(factory, github_auth, scenario, monkeypatch, change):
    from app.evaluation import experiment_executor

    assert run(factory, scenario, lambda request: httpx.Response(200, json={
        'object': 'response.input_tokens', 'input_tokens': 1200})) == 1200
    original = experiment_executor.ApprovedFakeModel._mark_sent
    def change_before_marker(model, db_factory, job_id, lease, reservation_id, payload):
        changed = deepcopy(payload)
        if change == 'model':
            changed['model'] = 'unapproved-model'
        elif change == 'instructions':
            changed['instructions'] += ' changed'
        elif change == 'input':
            changed['input'][0]['content'] += ' changed'
        elif change == 'schema':
            changed['text']['format']['schema']['description'] = 'changed'
        elif change == 'cache':
            changed['prompt_cache_options']['ttl'] = '12h'
        elif change == 'output_limit':
            changed['max_output_tokens'] -= 1
        elif change == 'truncation':
            changed['truncation'] = 'auto'
        elif change == 'tier':
            changed['service_tier'] = 'priority'
        else:
            changed['store'] = True
        return original(model, db_factory, job_id, lease, reservation_id, changed)
    monkeypatch.setattr(experiment_executor.ApprovedFakeModel, '_mark_sent', change_before_marker)
    calls = []
    execute_fake(factory, root=ROOT, job_id=scenario['job'], experiment_id=scenario['experiment'],
        approval_id=scenario['approval'], manifest=scenario['manifest'],
        transport=httpx.MockTransport(lambda request: calls.append(request)), github=github_auth,
        count_id=scenario['count'], count_account=FAKE_ACCOUNT, count_project=FAKE_PROJECT)
    with factory() as db:
        assert db.get(InvestigationReportJob, scenario['job']).status == 'failed'
        assert db.get(InvestigationExecutorApproval, scenario['approval']).state == 'ready'
        assert db.scalar(select(InvestigationUsageReservation)).state == 'reserved'
        assert db.scalar(select(InvestigationRealReport)) is None
    assert calls == []


@pytest.mark.parametrize('failure', ['expired', 'excessive'])
def test_expired_or_excessive_count_blocks_fake_generation_before_reservation(factory, github_auth, scenario, failure):
    value = 16_385 if failure == 'excessive' else 1200
    if failure == 'excessive':
        with pytest.raises(ModelError, match='count_limit_exceeded'):
            run(factory, scenario, lambda request: httpx.Response(200, json={
                'object': 'response.input_tokens', 'input_tokens': value}))
    else:
        assert run(factory, scenario, lambda request: httpx.Response(200, json={
            'object': 'response.input_tokens', 'input_tokens': value})) == value
        with factory.begin() as db:
            db.get(InvestigationTokenCount, scenario['count']).expires_at = now() - timedelta(seconds=1)
    calls = []
    with pytest.raises(ModelError, match='count_approval_invalid|count_limit_exceeded'):
        execute_fake(factory, root=ROOT, job_id=scenario['job'], experiment_id=scenario['experiment'],
            approval_id=scenario['approval'], manifest=scenario['manifest'],
            transport=httpx.MockTransport(lambda request: calls.append(request)), github=github_auth,
            count_id=scenario['count'], count_account=FAKE_ACCOUNT, count_project=FAKE_PROJECT)
    with factory() as db:
        assert db.get(InvestigationExecutorApproval, scenario['approval']).state == 'ready'
        assert db.scalar(select(InvestigationUsageReservation)) is None
    assert calls == []


def test_successful_fake_count_does_not_clear_unknown_actual_pricing(factory, scenario):
    from app.evaluation.experiment_executor import execute_live, record_live_approval

    assert run(factory, scenario, lambda request: httpx.Response(200, json={
        'object': 'response.input_tokens', 'input_tokens': 1200})) == 1200
    with pytest.raises(ModelError, match='pricing_unverified'):
        record_live_approval(None, ROOT, experiment_id='', job_id='', directory='', request_hash='',
            manifest_hash='', screening_acknowledged=True, pricing_acknowledged=True)
    with pytest.raises(ModelError, match='pricing_unverified'):
        execute_live(None, ROOT, experiment_id='', job_id='', approval_id='', directory='')
    with factory() as db:
        assert db.get(InvestigationExecutorApproval, scenario['approval']).state == 'ready'
        assert db.scalar(select(InvestigationUsageReservation)) is None


def test_completed_count_does_not_allow_duplicate_generation_approval(factory, scenario):
    from app.evaluation.experiment_executor import create_fake_approval

    assert run(factory, scenario, lambda request: httpx.Response(200, json={
        'object': 'response.input_tokens', 'input_tokens': 1200})) == 1200
    with pytest.raises(ModelError, match='approval_invalid'):
        create_fake_approval(factory, experiment_id=scenario['experiment'], job_id=scenario['job'],
            manifest=scenario['manifest'], expires_at=now() + timedelta(minutes=10))
    with factory() as db:
        assert db.get(InvestigationTokenCount, scenario['count']).status == 'complete'
        assert db.get(InvestigationExecutorApproval, scenario['approval']).state == 'ready'
        assert len(db.scalars(select(InvestigationExecutorApproval)).all()) == 1
        assert db.scalar(select(InvestigationUsageReservation)) is None


@pytest.mark.parametrize('change', ['installation', 'session', 'snapshot', 'source'])
def test_changed_access_or_source_before_generation_marker_blocks_send(factory, github_auth, scenario, monkeypatch, change):
    from app.evaluation import experiment_executor

    assert run(factory, scenario, lambda request: httpx.Response(200, json={
        'object': 'response.input_tokens', 'input_tokens': 10})) == 10
    original = experiment_executor.ApprovedFakeModel._mark_sent
    def change_before_marker(model, *args, **kwargs):
        with factory.begin() as db:
            if change == 'installation':
                db.get(Installation, 901).active = False
            elif change == 'session':
                job = db.get(InvestigationReportJob, scenario['job'])
                db.get(AuthSession, job.session_hash).revoked_at = now()
            elif change == 'snapshot':
                db.get(CodeSnapshot, scenario['snapshot']).published = False
            else:
                db.get(CodeChunk, scenario['chunk']).source_text += '\n# changed after count'
        return original(model, *args, **kwargs)
    monkeypatch.setattr(experiment_executor.ApprovedFakeModel, '_mark_sent', change_before_marker)
    calls = []
    execute_fake(factory, root=ROOT, job_id=scenario['job'], experiment_id=scenario['experiment'],
        approval_id=scenario['approval'], manifest=scenario['manifest'],
        transport=httpx.MockTransport(lambda request: calls.append(request)), github=github_auth,
        count_id=scenario['count'], count_account=FAKE_ACCOUNT, count_project=FAKE_PROJECT)
    with factory() as db:
        assert db.get(InvestigationReportJob, scenario['job']).status in {'failed', 'cancelled'}
        assert db.get(InvestigationExecutorApproval, scenario['approval']).state == 'ready'
        assert db.scalar(select(InvestigationUsageReservation)).state == 'reserved'
        assert db.scalar(select(InvestigationRealReport)) is None
    assert calls == []


def test_postgres_concurrent_count_approval_consumption(factory, scenario):
    if factory.kw["bind"].dialect.name != "postgresql":
        pytest.skip("PostgreSQL row locks required")
    barrier = Barrier(2)

    def claim():
        barrier.wait()
        try:
            _mark_fake_count_sent(factory, ROOT, count_id=scenario["count"], **scenario["args"])
            return "sent"
        except ModelError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: claim(), range(2)))
    assert sorted(outcomes) == ["rejected", "sent"]
    with factory() as db:
        row = db.get(InvestigationTokenCount, scenario["count"])
        assert row.status == "sent" and row.sent_at is not None and row.input_tokens is None


def test_postgres_concurrent_counted_generation_publishes_once(factory, github_auth, scenario):
    if factory.kw['bind'].dialect.name != 'postgresql':
        pytest.skip('PostgreSQL row locks required')
    assert run(factory, scenario, lambda request: httpx.Response(200, json={
        'object': 'response.input_tokens', 'input_tokens': 1200})) == 1200
    barrier = Barrier(2)
    calls = []
    def handle(request):
        calls.append(request)
        return response(json.dumps(valid_output(request)))
    def attempt():
        barrier.wait()
        try:
            execute_fake(factory, root=ROOT, job_id=scenario['job'], experiment_id=scenario['experiment'],
                approval_id=scenario['approval'], manifest=scenario['manifest'], transport=httpx.MockTransport(handle),
                github=github_auth, count_id=scenario['count'], count_account=FAKE_ACCOUNT, count_project=FAKE_PROJECT)
        except ModelError:
            pass  # A concurrent loser may be rejected at preflight or find a terminal job.
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: attempt(), range(2)))
    assert len(calls) == 1
    with factory() as db:
        assert db.get(InvestigationReportJob, scenario['job']).status == 'completed'
        assert db.get(InvestigationExecutorApproval, scenario['approval']).state == 'consumed'
        assert len(db.scalars(select(InvestigationUsageReservation)).all()) == 1
        assert len(db.scalars(select(InvestigationRealReport)).all()) == 1
