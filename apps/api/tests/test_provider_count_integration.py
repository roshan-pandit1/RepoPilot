"""Synthetic-only checks for count provenance and the shared generation ledger."""

import json
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from app.domain.models import (
    InvestigationExecutorApproval,
    InvestigationExperiment,
    InvestigationProviderTokenCount,
    InvestigationRealReport,
    InvestigationReportJob,
    InvestigationTokenCount,
    InvestigationUsageReservation,
    now,
)
from app.evaluation.experiment_executor import canonical, digest, execute_fake
from app.evaluation.token_counting import (
    FAKE_ACCOUNT,
    FAKE_PROJECT,
    _check_provider_binding,
    _post_count,
    _provider_binding,
    _provider_count_uncertain,
    _provider_fee_terms,
    count_projection,
    provider_identity,
    record_provider_count_approval,
    run_provider_count,
    validate_locked_provider_count,
)
from app.modules.investigation.report_model import ModelError
from app.modules.investigation.usage_ledger import MODEL, PRICING_POLICY, VerifiedCountFee
from test_auth_enrollment import github_auth as github_auth
from test_experiment_executor import valid_output
from test_real_report_foundation import response
from test_token_counting import run, scenario as scenario

ROOT = Path(__file__).resolve().parents[3]


def test_synthetic_interrupted_count_stays_uncertain_and_cannot_be_replayed():
    """Exercise the post-send transition without persisting an external approval."""
    row = SimpleNamespace(status='sent', completed_at=None, fee_state='reserved', fee_reserved_microusd=1000)
    class Session:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def scalar(self, statement):
            return row
    class Factory:
        def begin(self):
            return Session()
    _provider_count_uncertain(Factory(), str(uuid4()))
    assert row.status == 'uncertain' and row.completed_at and row.fee_state == 'uncertain'
    assert row.fee_reserved_microusd == 1000
    with pytest.raises(ModelError, match='count_approval_invalid'):
        _provider_count_uncertain(Factory(), str(uuid4()))


def test_live_model_send_marker_requires_count_before_database():
    from app.evaluation.experiment_executor import ApprovedLiveModel

    model = ApprovedLiveModel(root=ROOT, experiment_id=str(uuid4()), job_id=str(uuid4()),
        approval_id=str(uuid4()), manifest_sha256='a' * 64, api_key='synthetic-not-a-credential',
        transport=httpx.MockTransport(lambda request: pytest.fail('must not send')))
    with pytest.raises(ModelError, match='count_approval_invalid'):
        model._mark_sent(None, model.job_id, str(uuid4()), str(uuid4()), {})


def test_actual_count_approval_and_send_are_blocked_by_unknown_fee_without_database(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-not-a-credential")
    with pytest.raises(ModelError, match="count_pricing_unverified"):
        record_provider_count_approval(
            None,
            ROOT,
            job_id="",
            experiment_id="",
            tenant_id=1,
            account=FAKE_ACCOUNT,
            project=FAKE_PROJECT,
            review_directory="",
            generation_sha256="",
            manifest_sha256="",
            expires_at=now(),
            max_input_tokens=16_384,
            disclosure_acknowledged=True,
            pricing_acknowledged=True,
        )
    with pytest.raises(ModelError, match="count_pricing_unverified"):
        run_provider_count(
            None,
            ROOT,
            count_id="",
            job_id="",
            experiment_id="",
            tenant_id=1,
            account=FAKE_ACCOUNT,
            project=FAKE_PROJECT,
            snapshot_id="",
        )
    with pytest.raises(ModelError, match="count_not_enabled"):
        run_provider_count(
            None,
            ROOT,
            count_id="",
            job_id="",
            experiment_id="",
            tenant_id=1,
            account=FAKE_ACCOUNT,
            project=FAKE_PROJECT,
            snapshot_id="",
            transport=httpx.MockTransport(lambda request: pytest.fail("must not send")),
        )
    with pytest.raises(ModelError, match="count_not_enabled"):
        _post_count(
            b"{}",
            count_id="fixture",
            account=FAKE_ACCOUNT,
            project=FAKE_PROJECT,
            api_key="fixture",
            transport=None,
        )


def test_actual_count_requires_postgresql_even_with_synthetic_fee_terms(monkeypatch):
    from app.evaluation import token_counting

    monkeypatch.setattr(token_counting, '_provider_fee_terms', lambda account, project: object())
    fake_factory = SimpleNamespace(kw={'bind': SimpleNamespace(dialect=SimpleNamespace(name='sqlite'))})
    with pytest.raises(ModelError, match='count_approval_invalid'):
        record_provider_count_approval(fake_factory, ROOT, job_id='', experiment_id='', tenant_id=1,
            account=FAKE_ACCOUNT, project=FAKE_PROJECT, review_directory='', generation_sha256='',
            manifest_sha256='', expires_at=now(), max_input_tokens=16_384,
            disclosure_acknowledged=True, pricing_acknowledged=True)
    with pytest.raises(ModelError, match='count_not_enabled'):
        run_provider_count(fake_factory, ROOT, count_id='', job_id='', experiment_id='', tenant_id=1,
            account=FAKE_ACCOUNT, project=FAKE_PROJECT, snapshot_id='')


@pytest.fixture
def synthetic_provider_values(factory, scenario):
    """Detached objects only: no external authorization or provider result is persisted."""
    with factory() as db:
        job = db.get(InvestigationReportJob, scenario["job"])
        exp = db.get(InvestigationExperiment, scenario["experiment"])
        db.expunge_all()
    exp.mode = "actual"  # Detached test value; the disposable experiment stays simulated.
    timestamp = now()
    terms = VerifiedCountFee(
        policy="synthetic-review",
        bound_microusd=1000,
        account_sha256=provider_identity("account", FAKE_ACCOUNT),
        project_sha256=provider_identity("project", FAKE_PROJECT),
        model=MODEL,
        generation_policy=PRICING_POLICY,
        valid_until=timestamp + timedelta(minutes=20),
    )
    payload, manifest = deepcopy(scenario["payload"]), deepcopy(scenario["manifest"])
    projection = count_projection(payload)
    row = SimpleNamespace(
        id=str(uuid4()),
        job_id=job.id,
        experiment_id=exp.id,
        investigation_id=job.investigation_id,
        snapshot_id=job.snapshot_id,
        repository_id=job.repository_id,
        tenant_id=job.tenant_id,
        source_commit=manifest["source_commit"],
        fixture_id=manifest["fixture_id"],
        origin="external",
        provider="openai",
        model=MODEL,
        account_sha256=terms.account_sha256,
        project_sha256=terms.project_sha256,
        generation_sha256=digest(canonical(payload)),
        count_sha256=digest(canonical(projection)),
        manifest_sha256=digest(canonical(manifest)),
        pricing_policy=PRICING_POLICY,
        fee_policy=terms.policy,
        fee_reserved_microusd=1000,
        fee_accounted_microusd=None,
        fee_state="uncertain",
        service_tier="default",
        cache_ttl="30m",
        max_input_tokens=16_384,
        max_output_tokens=2048,
        status="verified",
        input_tokens=1200,
        created_at=timestamp - timedelta(seconds=2),
        sent_at=timestamp - timedelta(seconds=1),
        completed_at=timestamp,
        expires_at=timestamp + timedelta(minutes=10),
        invalidated_at=None,
        consumed_at=None,
        generation_approval_id=None,
    )
    row.binding_sha256 = digest(canonical(_provider_binding(row)))
    return row, job, exp, payload, manifest, projection, terms


def test_detached_synthetic_values_exercise_provider_binding_without_recording_provider_result(
    factory, scenario, synthetic_provider_values
):
    row, job, exp, payload, manifest, projection, terms = synthetic_provider_values
    assert (
        _check_provider_binding(
            row,
            job,
            exp,
            payload,
            manifest,
            projection,
            FAKE_ACCOUNT,
            FAKE_PROJECT,
            job.snapshot_id,
            terms,
        )
        is row
    )
    with factory() as db:
        assert db.scalar(select(InvestigationProviderTokenCount)) is None
        assert db.get(InvestigationExperiment, scenario["experiment"]).mode == "simulated"


@pytest.mark.parametrize(
    "change",
    [
        "simulated",
        "model",
        "account",
        "project",
        "request",
        "count_hash",
        "manifest",
        "snapshot",
        "commit",
        "fixture",
        "tenant",
        "investigation",
        "repository",
        "pricing",
        "fee_policy",
        "fee_bound",
        "tier",
        "cache",
        "output",
        "input_limit",
        "excessive",
        "boolean",
        "expired",
        "invalidated",
        "consumed",
        "pending",
        "fee_unknown_shape",
        "future_completion",
        "experiment_requests",
        "experiment_concurrency",
        "experiment_budget",
        "experiment_investigation_budget",
        "experiment_output",
        "instructions",
        "schema",
    ],
)
def test_provider_binding_rejects_synthetic_mismatch_even_with_rehashed_row(
    synthetic_provider_values, change
):
    row, job, exp, payload, manifest, projection, terms = synthetic_provider_values
    account, project = FAKE_ACCOUNT, FAKE_PROJECT
    if change == "simulated":
        row.origin = "simulated"
    elif change == "model":
        row.model = "other-model"
    elif change == "account":
        account = "other-account"
    elif change == "project":
        project = "other-project"
    elif change == "request":
        row.generation_sha256 = "a" * 64
    elif change == "count_hash":
        row.count_sha256 = "a" * 64
    elif change == "manifest":
        row.manifest_sha256 = "a" * 64
    elif change == "snapshot":
        row.snapshot_id = str(uuid4())
    elif change == "commit":
        row.source_commit = "a" * 40
    elif change == "fixture":
        row.fixture_id = "other-fixture"
    elif change == "tenant":
        row.tenant_id += 1
    elif change == "investigation":
        row.investigation_id = str(uuid4())
    elif change == "repository":
        row.repository_id += 1
    elif change == "pricing":
        row.pricing_policy = "unknown"
    elif change == "fee_policy":
        row.fee_policy = "unknown"
    elif change == "fee_bound":
        row.fee_reserved_microusd += 1
    elif change == "tier":
        row.service_tier = "priority"
    elif change == "cache":
        row.cache_ttl = "12h"
    elif change == "output":
        row.max_output_tokens -= 1
    elif change == "input_limit":
        row.max_input_tokens = 16_385
    elif change == "excessive":
        row.input_tokens = 16_385
    elif change == "boolean":
        row.input_tokens = True
    elif change == "expired":
        row.expires_at = now() - timedelta(seconds=1)
    elif change == "invalidated":
        row.invalidated_at = now()
    elif change == "consumed":
        row.status, row.consumed_at = "consumed", now()
    elif change == "pending":
        row.status = "pending"
    elif change == "fee_unknown_shape":
        row.fee_accounted_microusd = 0
    elif change == "future_completion":
        row.completed_at = now() + timedelta(minutes=1)
    elif change == "experiment_requests":
        exp.max_requests = 2
    elif change == "experiment_concurrency":
        exp.max_concurrent = 2
    elif change == "experiment_budget":
        exp.budget_microusd = 10_000_001
    elif change == "experiment_investigation_budget":
        exp.investigation_budget_microusd = 6_000_001
    elif change == "experiment_output":
        exp.max_output_tokens -= 1
    elif change == "instructions":
        payload["instructions"] += " changed"
    else:
        payload["text"]["format"]["schema"]["description"] = "changed"
    row.binding_sha256 = digest(canonical(_provider_binding(row)))
    with pytest.raises(ModelError, match="count_approval_invalid|count_input_invalid"):
        _check_provider_binding(
            row, job, exp, payload, manifest, projection, account, project, job.snapshot_id, terms
        )


def test_simulated_database_count_is_rejected_by_provider_preflight(
    factory, scenario, synthetic_provider_values, monkeypatch
):
    _, _, detached_exp, payload, manifest, _, terms = synthetic_provider_values
    monkeypatch.setattr(
        "app.evaluation.token_counting._provider_fee_terms", lambda account, project: terms
    )
    with factory.begin() as db:
        job = db.get(InvestigationReportJob, scenario["job"])
        with pytest.raises(ModelError, match="count_approval_invalid"):
            validate_locked_provider_count(
                db,
                count_id=scenario["count"],
                job=job,
                exp=detached_exp,
                generation=payload,
                manifest=manifest,
                account=FAKE_ACCOUNT,
                project=FAKE_PROJECT,
                snapshot_id=job.snapshot_id,
            )
    with factory() as db:
        assert db.get(InvestigationExperiment, scenario["experiment"]).mode == "simulated"
        assert db.scalar(select(InvestigationProviderTokenCount)) is None


def test_simulated_count_cannot_be_promoted_to_provider_authorization(
    factory, scenario, synthetic_provider_values, monkeypatch
):
    _, _, _, _, _, _, terms = synthetic_provider_values
    # Test-only terms reach the isolation check; no actual pricing gate or approval is enabled.
    monkeypatch.setattr('app.evaluation.token_counting._provider_fee_terms', lambda account, project: terms)
    with pytest.raises(ModelError, match='count_approval_invalid'):
        record_provider_count_approval(factory, ROOT, job_id=scenario['job'],
            experiment_id=scenario['experiment'], tenant_id=scenario['tenant'], account=FAKE_ACCOUNT,
            project=FAKE_PROJECT, review_directory=scenario['private'],
            generation_sha256=scenario['manifest']['request_sha256'],
            manifest_sha256=digest(canonical(scenario['manifest'])), expires_at=now() + timedelta(minutes=5),
            max_input_tokens=16_384, disclosure_acknowledged=True, pricing_acknowledged=True)
    with factory() as db:
        assert db.get(InvestigationTokenCount, scenario['count']).mode == 'simulated'
        assert db.get(InvestigationExperiment, scenario['experiment']).mode == 'simulated'
        assert db.scalar(select(InvestigationProviderTokenCount)) is None


def test_fee_terms_must_match_account_project_model_policy_and_expiry(monkeypatch):
    from dataclasses import replace
    import app.evaluation.token_counting as counting

    terms = VerifiedCountFee(
        policy="synthetic-review",
        bound_microusd=1000,
        account_sha256=provider_identity("account", FAKE_ACCOUNT),
        project_sha256=provider_identity("project", FAKE_PROJECT),
        model=MODEL,
        generation_policy=PRICING_POLICY,
        valid_until=now() + timedelta(minutes=10),
    )
    monkeypatch.setattr(counting, "require_verified_count_pricing", lambda: terms)
    assert _provider_fee_terms(FAKE_ACCOUNT, FAKE_PROJECT) == terms
    for bad in (
        replace(terms, bound_microusd=-1),
        replace(terms, bound_microusd=True),
        replace(terms, account_sha256="other"),
        replace(terms, project_sha256="other"),
        replace(terms, model="other"),
        replace(terms, generation_policy="other"),
        replace(terms, valid_until=now() - timedelta(seconds=1)),
    ):
        monkeypatch.setattr(counting, "require_verified_count_pricing", lambda: bad)
        with pytest.raises(ModelError, match="count_pricing_unverified"):
            _provider_fee_terms(FAKE_ACCOUNT, FAKE_PROJECT)


def test_invalid_count_audit_fee_still_counts_against_same_experiment_budget(
    factory, github_auth, scenario
):
    """An invalid synthetic audit row is never an actual count approval or provider result."""
    timestamp = now()
    with factory.begin() as db:
        job = db.get(InvestigationReportJob, scenario["job"])
        db.add(
            InvestigationProviderTokenCount(
                id=str(uuid4()),
                job_id=job.id,
                experiment_id=scenario["experiment"],
                investigation_id=job.investigation_id,
                snapshot_id=job.snapshot_id,
                repository_id=job.repository_id,
                tenant_id=job.tenant_id,
                source_commit="a" * 40,
                fixture_id="synthetic-invalid",
                origin="external",
                provider="openai",
                model=MODEL,
                account_sha256="a" * 64,
                project_sha256="b" * 64,
                generation_sha256="c" * 64,
                count_sha256="d" * 64,
                manifest_sha256="e" * 64,
                binding_sha256="f" * 64,
                pricing_policy=PRICING_POLICY,
                fee_policy="synthetic-invalid",
                service_tier="default",
                cache_ttl="30m",
                max_input_tokens=16_384,
                max_output_tokens=2048,
                status="invalid",
                fee_state="uncertain",
                fee_reserved_microusd=200_000,
                created_at=timestamp,
                expires_at=timestamp + timedelta(minutes=10),
                invalidated_at=timestamp,
            )
        )
    calls = []
    execute_fake(
        factory,
        root=ROOT,
        job_id=scenario["job"],
        experiment_id=scenario["experiment"],
        approval_id=scenario["approval"],
        manifest=scenario["manifest"],
        transport=httpx.MockTransport(lambda request: calls.append(request)),
        github=github_auth,
    )
    with factory() as db:
        job = db.get(InvestigationReportJob, scenario["job"])
        assert job.status == "failed" and job.error_code == "budget_exhausted"
        assert db.scalar(select(InvestigationUsageReservation)) is None
        assert db.scalar(select(InvestigationProviderTokenCount)).fee_reserved_microusd == 200_000
        assert db.scalar(select(InvestigationRealReport)) is None
    assert calls == []


def test_tampered_generation_reservation_blocks_send_and_preserves_fake_approval(
    factory, github_auth, scenario, monkeypatch
):
    from app.evaluation import experiment_executor

    assert (
        run(
            factory,
            scenario,
            lambda request: httpx.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 1200}
            ),
        )
        == 1200
    )
    original = experiment_executor.ApprovedFakeModel._mark_sent

    def tamper(model, db_factory, job_id, lease, reservation_id, payload):
        with factory.begin() as db:
            db.get(InvestigationUsageReservation, reservation_id).reserved_microusd -= 1
        return original(model, db_factory, job_id, lease, reservation_id, payload)

    monkeypatch.setattr(experiment_executor.ApprovedFakeModel, "_mark_sent", tamper)
    calls = []
    execute_fake(
        factory,
        root=ROOT,
        job_id=scenario["job"],
        experiment_id=scenario["experiment"],
        approval_id=scenario["approval"],
        manifest=scenario["manifest"],
        transport=httpx.MockTransport(lambda request: calls.append(request)),
        github=github_auth,
        count_id=scenario["count"],
        count_account=FAKE_ACCOUNT,
        count_project=FAKE_PROJECT,
    )
    with factory() as db:
        assert db.get(InvestigationExecutorApproval, scenario["approval"]).state == "ready"
        assert db.scalar(select(InvestigationRealReport)) is None
    assert not calls


def test_fake_counted_generation_rejects_foreign_report_citation(factory, github_auth, scenario):
    assert (
        run(
            factory,
            scenario,
            lambda request: httpx.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 1200}
            ),
        )
        == 1200
    )
    calls = []

    def handler(request):
        calls.append(request)
        draft = valid_output(request)
        draft["hypotheses"][0]["evidence"][0]["chunk_id"] = str(uuid4())
        return response(json.dumps(draft))

    execute_fake(
        factory,
        root=ROOT,
        job_id=scenario["job"],
        experiment_id=scenario["experiment"],
        approval_id=scenario["approval"],
        manifest=scenario["manifest"],
        transport=httpx.MockTransport(handler),
        github=github_auth,
        count_id=scenario["count"],
        count_account=FAKE_ACCOUNT,
        count_project=FAKE_PROJECT,
    )
    with factory() as db:
        assert db.get(InvestigationReportJob, scenario["job"]).status == "failed"
        assert db.scalar(select(InvestigationRealReport)) is None
        assert db.get(InvestigationTokenCount, scenario["count"]).mode == "simulated"
    assert len(calls) == 1


@pytest.mark.parametrize('case', ['success', 'timeout', 'malformed', 'foreign_citation',
                                  'count_timeout', 'count_malformed', 'count_with_generation_approval',
                                  'count_screen_rejected'])
def test_postgres_synthetic_provider_count_and_generation_marker_are_atomic(client, factory, github_auth, monkeypatch, tmp_path, case):
    """Actual-shaped fixture only: fake transport, fake terms, no live approval or provider result."""
    is_postgres = factory.kw['bind'].dialect.name == 'postgresql'
    import socket
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from pydantic import SecretStr
    from sqlalchemy import text as sql_text

    from app.core.config import get_settings
    from app.evaluation import experiment_executor, token_counting
    from app.evaluation.provider_harness import network_fence
    from app.modules.investigation.report_worker import process_report
    import test_experiment_executor as fixture_module

    # The actual-shaped rows exist only in the isolated test database. The pricing
    # replacements and synthetic HTTP transport below cannot be enabled by configuration.
    monkeypatch.setattr(fixture_module, 'create_fake_approval', lambda *args, **kwargs: str(uuid4()))
    item = fixture_module.setup_fixture(client, factory, github_auth, monkeypatch)
    if not is_postgres:
        # Exercise orchestration locally as well; only PostgreSQL exercises row locking.
        monkeypatch.setattr(factory.kw['bind'].dialect, 'name', 'postgresql')
    timestamp = now()
    terms = VerifiedCountFee(policy='synthetic-test-only', bound_microusd=100_000,
        account_sha256=provider_identity('account', FAKE_ACCOUNT),
        project_sha256=provider_identity('project', FAKE_PROJECT), model=MODEL,
        generation_policy=PRICING_POLICY, valid_until=timestamp + timedelta(minutes=20))
    monkeypatch.setattr(token_counting, '_provider_fee_terms', lambda account, project: terms)
    monkeypatch.setattr(token_counting, 'require_stress_capacity', lambda *args: None)
    monkeypatch.setattr(experiment_executor, 'require_verified_actual_pricing', lambda: None)
    monkeypatch.setattr(experiment_executor, 'require_stress_capacity', lambda *args: None)
    private = tmp_path / 'review'
    private.mkdir(mode=0o700)
    experiment_executor.write_private(private, item['payload'], item['manifest'])
    with factory() as db:
        tenant_id = db.get(InvestigationReportJob, item['job']).tenant_id
    count_approval_args = dict(job_id=item['job'],
        experiment_id=item['experiment'], tenant_id=tenant_id, account=FAKE_ACCOUNT, project=FAKE_PROJECT,
        review_directory=private, generation_sha256=digest(canonical(item['payload'])),
        manifest_sha256=digest(canonical(item['manifest'])), expires_at=timestamp + timedelta(minutes=10),
        max_input_tokens=16_384, disclosure_acknowledged=True, pricing_acknowledged=True)
    if case == 'count_screen_rejected':
        from app.evaluation import disclosure_screen
        def reject_screen(*args):
            raise ValueError('synthetic_screen_rejection')
        with monkeypatch.context() as screening:
            screening.setattr(disclosure_screen, 'screen_exact', reject_screen)
            with pytest.raises(ValueError, match='synthetic_screen_rejection'):
                record_provider_count_approval(factory, ROOT, **count_approval_args)
        with factory() as db:
            assert db.scalar(select(InvestigationProviderTokenCount)) is None
            assert db.get(InvestigationExperiment, item['experiment']).mode == 'simulated'
        return
    count_id = record_provider_count_approval(factory, ROOT, **count_approval_args)
    if case == 'count_with_generation_approval':
        with factory.begin() as db:
            db.add(InvestigationExecutorApproval(id=str(uuid4()), job_id=item['job'],
                experiment_id=item['experiment'], tenant_id=tenant_id, snapshot_id=item['snapshot'],
                source_commit=item['manifest']['source_commit'], fixture_id=item['manifest']['fixture_id'],
                mode='actual', provider='openai', model=MODEL, request_sha256=digest(canonical(item['payload'])),
                manifest_sha256=digest(canonical(item['manifest'])), state='ready',
                expires_at=timestamp + timedelta(minutes=10)))
    settings = get_settings()
    monkeypatch.setattr(settings, 'investigation_provider', 'openai')
    monkeypatch.setattr(settings, 'investigation_real_enabled', False)
    monkeypatch.setattr(settings, 'investigation_paid_background_enabled', False)
    monkeypatch.setattr(settings, 'investigation_count_external_enabled', True)
    monkeypatch.setattr(settings, 'investigation_openai_api_key', SecretStr('synthetic-test-key'))
    monkeypatch.setattr(settings, 'investigation_openai_organization', SecretStr(FAKE_ACCOUNT))
    monkeypatch.setattr(settings, 'investigation_openai_project', SecretStr(FAKE_PROJECT))
    monkeypatch.setattr(settings, 'investigation_experiment_id', item['experiment'])
    count_calls = []
    def fake_count(request):
        count_calls.append(request)
        assert digest(request.content) == digest(canonical(count_projection(item['payload'])))
        with factory() as db:
            assert db.get(InvestigationProviderTokenCount, count_id).status == 'sent'
        with pytest.raises(OSError, match='evaluation_network_blocked'):
            socket.getaddrinfo('api.openai.com', 443)
        if case == 'count_timeout':
            raise httpx.ReadTimeout('synthetic count timeout')
        if case == 'count_malformed':
            return httpx.Response(200, content=b'{')
        return httpx.Response(200, json={'object': 'response.input_tokens', 'input_tokens': 1200})
    real_client = httpx.Client
    def fake_client(*args, **kwargs):
        return real_client(*args, transport=httpx.MockTransport(fake_count), **kwargs)
    count_args = dict(count_id=count_id, job_id=item['job'], experiment_id=item['experiment'],
        tenant_id=tenant_id, account=FAKE_ACCOUNT, project=FAKE_PROJECT, snapshot_id=item['snapshot'])
    with network_fence(factory.kw['bind'].url.port), monkeypatch.context() as fake_http:
        fake_http.setattr(token_counting.httpx, 'Client', fake_client)
        if case == 'count_with_generation_approval':
            with pytest.raises(ModelError, match='count_approval_invalid'):
                run_provider_count(factory, ROOT, **count_args)
        elif case in ('count_timeout', 'count_malformed'):
            with pytest.raises(ModelError, match='count_billing_unknown'):
                run_provider_count(factory, ROOT, **count_args)
        elif is_postgres and case == 'success':
            count_barrier = Barrier(2)
            def count_deliver():
                count_barrier.wait(timeout=10)
                try:
                    return run_provider_count(factory, ROOT, **count_args)
                except ModelError as exc:
                    return str(exc)
            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(lambda _: count_deliver(), range(2)))
            assert outcomes.count(1200) == 1 and outcomes.count('count_approval_invalid') == 1
        else:
            assert run_provider_count(factory, ROOT, **count_args) == 1200
        with pytest.raises(ModelError, match='count_approval_invalid'):
            run_provider_count(factory, ROOT, **count_args)
    if case == 'count_with_generation_approval':
        with factory() as db:
            assert db.get(InvestigationProviderTokenCount, count_id).status == 'pending'
        assert not count_calls
        return
    assert len(count_calls) == 1
    if case in ('count_timeout', 'count_malformed'):
        with factory() as db:
            count = db.get(InvestigationProviderTokenCount, count_id)
            assert count.status == 'uncertain' and count.fee_state == 'uncertain'
            assert count.fee_reserved_microusd == 100_000
            assert db.scalar(select(InvestigationExecutorApproval)) is None
            assert db.scalar(select(InvestigationUsageReservation)) is None
        return
    monkeypatch.setattr(settings, 'investigation_provider', 'mock')
    monkeypatch.setattr(settings, 'investigation_openai_api_key', SecretStr(''))
    monkeypatch.setattr(settings, 'investigation_count_external_enabled', False)
    approval_id = experiment_executor.record_live_approval(factory, ROOT, experiment_id=item['experiment'],
        job_id=item['job'], directory=private, request_hash=digest(canonical(item['payload'])),
        manifest_hash=digest(canonical(item['manifest'])), screening_acknowledged=True, pricing_acknowledged=True,
        count_id=count_id, account=FAKE_ACCOUNT, project=FAKE_PROJECT)
    monkeypatch.setattr(settings, 'investigation_provider', 'openai')
    monkeypatch.setattr(settings, 'investigation_real_enabled', True)
    monkeypatch.setattr(settings, 'investigation_openai_api_key', SecretStr('synthetic-test-key'))
    # Test-only replacements cannot bypass the production price or stress gates.
    monkeypatch.setattr(experiment_executor, 'text', lambda query: sql_text(
        "SELECT '0013'" if query == 'select version_num from alembic_version'
        else 'SELECT NULL' if not is_postgres and query == 'select current_database()' else query))
    calls = []
    def fake_response(request):
        calls.append(request)
        with pytest.raises(OSError, match='evaluation_network_blocked'):
            socket.getaddrinfo('api.openai.com', 443)
        if case == 'timeout':
            raise httpx.ReadTimeout('synthetic timeout')
        if case == 'malformed':
            return httpx.Response(200, content=b'{')
        draft = valid_output(request)
        if case == 'foreign_citation':
            draft['hypotheses'][0]['evidence'][0]['chunk_id'] = str(uuid4())
        return response(json.dumps(draft))
    model = experiment_executor.ApprovedLiveModel(root=ROOT, experiment_id=item['experiment'], job_id=item['job'],
        approval_id=approval_id, manifest_sha256=digest(canonical(item['manifest'])), api_key='synthetic-test-key',
        count_id=count_id, account=FAKE_ACCOUNT, project=FAKE_PROJECT, transport=httpx.MockTransport(fake_response))
    with network_fence(factory.kw['bind'].url.port or 0):
        if is_postgres:
            barrier = Barrier(2)
            def deliver():
                barrier.wait(timeout=10)
                process_report(item['job'], factory, github_auth, model)
            with ThreadPoolExecutor(max_workers=2) as pool:
                list(pool.map(lambda _: deliver(), range(2)))
        else:
            process_report(item['job'], factory, github_auth, model)
        process_report(item['job'], factory, github_auth, model)
    with factory() as db:
        assert db.get(InvestigationReportJob, item['job']).status == ('completed' if case == 'success' else 'failed')
        assert db.get(InvestigationExecutorApproval, approval_id).state == 'consumed'
        count = db.get(InvestigationProviderTokenCount, count_id)
        assert count.status == 'consumed' and count.generation_approval_id == approval_id
        assert count.fee_state == 'uncertain' and count.fee_reserved_microusd == 100_000
        assert db.scalar(select(InvestigationTokenCount)) is None
        reservation = db.scalar(select(InvestigationUsageReservation))
        assert reservation.reserved_microusd == 5_815_551
        assert reservation.state == ('uncertain' if case in ('timeout', 'malformed') else 'known')
        assert len(db.scalars(select(InvestigationRealReport)).all()) == (1 if case == 'success' else 0)
    assert len(calls) == 1
