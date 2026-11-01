import hashlib
import json
import os
import runpy
import socket
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.domain.models import (CodeChunk, CodeSnapshot, IndexedFile, Installation,
    InvestigationExecutorApproval, InvestigationExperiment, InvestigationJob, InvestigationRealReport,
    InvestigationReportJob, InvestigationUsageReservation, Repository, now)
from app.evaluation.experiment_executor import (ApprovedFakeModel, ApprovedLiveModel, canonical, create_fake_approval,
    digest, disclosure, execute_fake, isolated_port, prepare_review, read_private, record_live_approval,
    require_fake_configuration, template, write_private)
from app.evaluation.provider_harness import COMMIT, EXPECTED_PATH, REPOSITORY, load_fixture, network_fence
from app.modules.github.issue_context import build_context
from app.modules.investigation.openai_provider import OpenAIInvestigationModel
from app.modules.investigation.report_model import ModelError, build_package, model_request
from app.modules.investigation.reporting import evidence_inputs
from app.modules.investigation.retrieval import Candidate, fingerprint_chunk
from app.modules.investigation.usage_ledger import MODEL, reserve
from app.workers.tasks import process_investigation
from test_auth_enrollment import csrf, github_auth as github_auth, sign_in
from test_investigation_evidence import submit
from test_investigation_reports import report_url, request_report
from test_real_report_foundation import add_experiment, response

ROOT = Path(__file__).resolve().parents[3]


def setup_fixture(client, factory, github, monkeypatch):
    _, case, source, chunks, _, _ = load_fixture(ROOT)
    github.repositories = lambda token, installation: ([{'id': 902, 'full_name': REPOSITORY, 'private': False}]
        if github.include_repository else [])
    sign_in(client)
    assert client.post('/v1/installations/901/enroll', headers=csrf(client)).status_code == 200
    assert client.post('/v1/installations/901/repositories/902/select', headers=csrf(client)).status_code == 200
    issue = {'id': 990, 'number': 5, 'title': case['title'], 'body': case['body'], 'state': 'open',
             'created_at': '2026-01-01T00:00:00Z', 'updated_at': '2026-01-01T00:00:00Z',
             'comments': 0, 'labels': []}
    github.issue = lambda *args: dict(issue)
    github.issue_comments = lambda *args: []
    with factory.begin() as db:
        repo = db.get(Repository, 902)
        snapshot = CodeSnapshot(id=str(uuid4()), repository_id=902, tenant_id=repo.tenant_id,
                                commit_sha=COMMIT, published=True)
        db.add(snapshot)
        db.flush()
        file = IndexedFile(id=str(uuid4()), snapshot_id=snapshot.id, repository_id=902,
                           tenant_id=repo.tenant_id, path=EXPECTED_PATH,
                           content_hash=hashlib.sha256(source).hexdigest())
        db.add(file)
        db.flush()
        chunk = next(x for x in chunks if x.symbol == 'valid_signature')
        row = CodeChunk(id=str(uuid4()), file_id=file.id, repository_id=902, tenant_id=repo.tenant_id,
                        symbol=chunk.symbol, start_line=chunk.start_line, end_line=chunk.end_line, source_text=chunk.text)
        db.add(row)
        snapshot_id, chunk_id = snapshot.id, row.id

    def retrieve(_factory, **kwargs):
        with factory() as db:
            row = db.get(CodeChunk, chunk_id)
            file = db.get(IndexedFile, row.file_id)
            query = kwargs['queries'][0]
            return [Candidate(row.id, file.id, file.path, row.symbol, row.start_line, row.end_line,
                fingerprint_chunk(row, file), query.id, hashlib.sha256(query.text.encode()).hexdigest(), 1, 0)]
    monkeypatch.setattr('app.modules.investigation.retrieval.retrieve_candidates', retrieve)
    parent_id = submit(client)
    process_investigation(parent_id, factory, github)
    job_id = request_report(client, parent_id)
    experiment_id = add_experiment(factory, job_id)
    with factory() as db:
        parent, snapshot = db.get(InvestigationJob, parent_id), db.get(CodeSnapshot, snapshot_id)
        evidence = evidence_inputs(db, parent, snapshot)
    context = build_context(issue, [], 902, REPOSITORY, 5, get_settings())
    package = build_package(investigation_id=parent_id, repository_id=902, issue_id=990, issue_number=5,
        context=context, snapshot_id=snapshot_id, commit_sha=COMMIT, evidence=evidence)
    payload, manifest = disclosure(ROOT, model_request(package), experiment_id=experiment_id, job_id=job_id)
    approval_id = create_fake_approval(factory, experiment_id=experiment_id, job_id=job_id,
                                       manifest=manifest, expires_at=now() + timedelta(minutes=30))
    return {'parent': parent_id, 'job': job_id, 'experiment': experiment_id, 'snapshot': snapshot_id,
            'chunk': chunk_id, 'payload': payload, 'manifest': manifest, 'approval': approval_id}


def valid_output(request):
    data = json.loads(json.loads(request.content)['input'][0]['content'])
    item = data['evidence'][0]
    ref = {key: item[key] for key in ('chunk_id', 'snapshot_id', 'commit_sha', 'start_line', 'end_line')}
    return {'summary': 'A signature verification issue was reported.', 'hypotheses': [{
        'title': 'Possible verification mismatch', 'explanation': 'Inspect the selected comparison.',
        'observations': ['The selected function compares values.'],
        'missing_or_contradictory': ['The reported failure is not reproduced.'],
        'evidence': [ref], 'contradictory_evidence': []}],
        'missing_evidence': ['A reproduction is required.'], 'next_steps': ['Reproduce the failure.'],
        'warnings': ['Synthetic fake response only.']}


def run_fake(factory, github, item, handler, *, manifest=None, approval=None, experiment=None):
    return execute_fake(factory, root=ROOT, job_id=item['job'], experiment_id=experiment or item['experiment'],
        approval_id=approval or item['approval'], manifest=manifest or item['manifest'],
        transport=httpx.MockTransport(handler), github=github)


def test_template_is_source_bound_private_and_offline(tmp_path):
    with network_fence(0):
        payload, manifest = template(ROOT)
        with pytest.raises(OSError, match='evaluation_network_blocked'):
            socket.getaddrinfo('api.openai.com', 443)
    assert manifest['source_commit'] == COMMIT and manifest['fixture_id'] == 'signature_exact'
    assert {(e['start_line'], e['end_line']) for e in manifest['evidence']} == {(1, 5), (6, 8)}
    assert manifest['request_sha256'] == digest(canonical(payload))
    assert payload['max_output_tokens'] == 2048 and 'tools' not in payload
    assert payload['prompt_cache_options'] == {'ttl': '30m'} and payload['store'] is False
    assert manifest['reservation_microusd'] == 5_815_551
    private = tmp_path / 'private'
    private.mkdir(mode=0o700)
    write_private(private, payload, manifest)
    assert (private / 'request.json').stat().st_mode & 0o777 == 0o600
    assert (private / 'manifest.json').stat().st_mode & 0o777 == 0o600
    assert digest((private / 'request.json').read_bytes()) == manifest['request_sha256']
    assert 'signature verification' not in (private / 'manifest.json').read_text()
    with pytest.raises(FileExistsError):
        write_private(private, payload, manifest)
    os.chmod(private, 0o755)
    with pytest.raises(ValueError, match='review_directory_not_private'):
        write_private(private, payload, manifest)


def test_executor_success_is_grounded_one_use_and_secret_safe(client, factory, github_auth, monkeypatch, caplog):
    from app.evaluation import experiment_executor
    caplog.set_level('INFO')
    item = setup_fixture(client, factory, github_auth, monkeypatch)
    instances = []
    class TrackingModel(ApprovedFakeModel):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            instances.append(self)
    monkeypatch.setattr(experiment_executor, 'ApprovedFakeModel', TrackingModel)
    calls = []
    def handler(request):
        calls.append(request)
        with pytest.raises(OSError, match='evaluation_network_blocked'):
            socket.getaddrinfo('api.openai.com', 443)
        assert digest(canonical(json.loads(request.content))) == item['manifest']['request_sha256']
        assert digest(request.content) == item['manifest']['request_sha256']
        return response(json.dumps(valid_output(request)))
    run_fake(factory, github_auth, item, handler)
    with pytest.raises(ModelError, match='approval_invalid'):
        run_fake(factory, github_auth, item, handler)
    with factory() as db:
        job = db.get(InvestigationReportJob, item['job'])
        approval = db.get(InvestigationExecutorApproval, item['approval'])
        usage = db.scalar(select(InvestigationUsageReservation))
        reports = db.scalars(select(InvestigationRealReport)).all()
        assert job.status == 'completed' and job.attempts == 1
        assert approval.state == 'consumed' and approval.consumed_at is not None
        assert usage.state == 'known' and usage.mode == 'simulated' and usage.reserved_microusd == 5_815_551
        assert len(reports) == 1 and reports[0].cost_microusd is None
    assert len(calls) == 1
    assert len(instances) == 1 and instances[0]._transport is None
    result = client.get(report_url(item['parent']))
    assert result.status_code == 200
    assert result.json()['report']['hypotheses'][0]['evidence'][0]['chunk_id'] == item['chunk']
    assert 'sensitive-github-token' not in caplog.text and 'synthetic-fake-only-key' not in caplog.text
    assert item['payload']['input'][0]['content'] not in caplog.text


@pytest.mark.parametrize('upstream_id,expected', [
    ('req_0123456789abcdef0123456789abcdef', 'req_0123456789abcdef0123456789abcdef'),
    ('req_synthetic-secret-value', None),
])
def test_provider_observability_is_correlated_and_secret_safe(upstream_id, expected,
        client, factory, github_auth, monkeypatch):
    from app.modules.investigation import openai_provider
    item = setup_fixture(client, factory, github_auth, monkeypatch)
    events = []
    monkeypatch.setattr(openai_provider.event_logger, 'info', lambda message: events.append(json.loads(message)))
    def handler(request):
        assert request.headers['x-client-request-id'] == item['job']
        assert set(request.headers) == {'host', 'accept', 'accept-encoding', 'connection', 'user-agent',
                                        'authorization', 'content-type', 'x-client-request-id', 'content-length'}
        result = response(json.dumps(valid_output(request)))
        result.headers['x-request-id'] = upstream_id
        return result
    run_fake(factory, github_auth, item, handler)
    header_event = next(event for event in events if event['event'] == 'model_http_response')
    model_event = next(event for event in events if event['event'] == 'model_response_identity')
    assert header_event['client_request_id'] == item['job'] and header_event['http_status'] == 200
    assert header_event.get('provider_request_id') == expected
    assert model_event['requested_model'] == model_event['returned_model'] == MODEL
    serialized = json.dumps(events)
    assert 'synthetic-secret-value' not in serialized and 'synthetic-fake-only-key' not in serialized
    assert item['payload']['input'][0]['content'] not in serialized


def test_real_job_review_is_reconstructed_and_revocation_checked(client, factory, github_auth, monkeypatch, tmp_path):
    item = setup_fixture(client, factory, github_auth, monkeypatch)
    payload, manifest = prepare_review(factory, ROOT, experiment_id=item['experiment'], job_id=item['job'])
    assert payload == item['payload'] and manifest == item['manifest']
    private = tmp_path / 'private'
    private.mkdir(mode=0o700)
    write_private(private, payload, manifest)
    assert read_private(private, ROOT, experiment_id=item['experiment'], job_id=item['job']) == (payload, manifest)
    changed = deepcopy(payload)
    changed['model'] = 'another-model'
    (private / 'request.json').write_bytes(canonical(changed))
    with pytest.raises(ValueError, match='review_mismatch'):
        read_private(private, ROOT, experiment_id=item['experiment'], job_id=item['job'])
    with factory.begin() as db:
        db.get(Installation, 901).active = False
    with pytest.raises(ModelError, match='approval_invalid'):
        prepare_review(factory, ROOT, experiment_id=item['experiment'], job_id=item['job'])


@pytest.mark.parametrize('variant', ['missing', 'expired', 'wrong_experiment', 'wrong_model',
    'wrong_fixture', 'wrong_commit', 'manifest_mismatch'])
def test_approval_rejection_precedes_worker_claim(variant, client, factory, github_auth, monkeypatch):
    item = setup_fixture(client, factory, github_auth, monkeypatch)
    approval, experiment, manifest = item['approval'], item['experiment'], deepcopy(item['manifest'])
    if variant == 'missing':
        approval = str(uuid4())
    elif variant == 'expired':
        with factory.begin() as db:
            db.get(InvestigationExecutorApproval, approval).expires_at = now() - timedelta(seconds=1)
    elif variant == 'wrong_experiment':
        experiment = str(uuid4())
    elif variant == 'wrong_model':
        manifest['model'] = 'different-model'
    elif variant == 'wrong_fixture':
        manifest['fixture_id'] = 'other'
    elif variant == 'wrong_commit':
        manifest['source_commit'] = 'a' * 40
    else:
        manifest['request_sha256'] = 'f' * 64
    calls = []
    with pytest.raises(ModelError, match='approval_invalid'):
        run_fake(factory, github_auth, item, lambda req: calls.append(req),
                 manifest=manifest, approval=approval, experiment=experiment)
    with factory() as db:
        assert db.get(InvestigationReportJob, item['job']).attempts == 0
        assert db.scalar(select(InvestigationUsageReservation)) is None
    assert not calls


def test_budget_exhaustion_and_revocation_prevent_send(client, factory, github_auth, monkeypatch):
    item = setup_fixture(client, factory, github_auth, monkeypatch)
    with factory.begin() as db:
        db.get(InvestigationExperiment, item['experiment']).budget_microusd = 1
    calls = []
    run_fake(factory, github_auth, item, lambda req: calls.append(req))
    with factory() as db:
        assert db.get(InvestigationReportJob, item['job']).error_code == 'budget_exhausted'
        assert db.get(InvestigationExecutorApproval, item['approval']).state == 'ready'
        assert db.scalar(select(InvestigationUsageReservation)) is None
    assert not calls


def test_revocation_prevents_approval_consumption(client, factory, github_auth, monkeypatch):
    item = setup_fixture(client, factory, github_auth, monkeypatch)
    github_auth.include_repository = False
    calls = []
    run_fake(factory, github_auth, item, lambda req: calls.append(req))
    with factory() as db:
        assert db.get(InvestigationReportJob, item['job']).status == 'cancelled'
        assert db.get(InvestigationExecutorApproval, item['approval']).state == 'ready'
    assert not calls


@pytest.mark.parametrize('failure', ['timeout', 'missing_usage', 'invalid', 'refusal', 'incomplete', 'foreign'])
def test_failed_fake_response_never_retries_or_publishes(failure, client, factory, github_auth, monkeypatch):
    item = setup_fixture(client, factory, github_auth, monkeypatch)
    calls = []
    def handler(request):
        calls.append(request)
        if failure == 'timeout':
            raise httpx.ReadTimeout('synthetic')
        if failure in ('refusal', 'incomplete'):
            return httpx.Response(200, json={'model': MODEL, 'service_tier': 'default',
                'status': 'incomplete' if failure == 'incomplete' else 'completed',
                'usage': {'input_tokens': 1200, 'output_tokens': 250},
                'output': [{'type': 'message', 'content': [{'type': 'refusal', 'refusal': 'fixture'}]}]})
        output = valid_output(request)
        if failure == 'foreign':
            output['hypotheses'][0]['evidence'][0]['chunk_id'] = str(uuid4())
        return response('{' if failure == 'invalid' else json.dumps(output), usage=failure != 'missing_usage')
    run_fake(factory, github_auth, item, handler)
    with pytest.raises(ModelError, match='approval_invalid'):
        run_fake(factory, github_auth, item, handler)
    with factory() as db:
        assert db.get(InvestigationReportJob, item['job']).status == 'failed'
        assert db.get(InvestigationExecutorApproval, item['approval']).state == 'consumed'
        usage = db.scalar(select(InvestigationUsageReservation))
        assert usage.state == ('uncertain' if failure in ('timeout', 'missing_usage') else 'known')
        assert db.scalar(select(InvestigationRealReport)) is None
    assert len(calls) == 1


def test_input_drift_and_forged_manifest_cannot_send(client, factory, github_auth, monkeypatch):
    item = setup_fixture(client, factory, github_auth, monkeypatch)
    original = github_auth.issue
    github_auth.issue = lambda *args: {**original(*args), 'title': 'Changed after review'}
    calls = []
    run_fake(factory, github_auth, item, lambda req: calls.append(req))
    with factory() as db:
        assert db.get(InvestigationReportJob, item['job']).status == 'failed'
        assert db.get(InvestigationExecutorApproval, item['approval']).state == 'ready'
        assert db.scalar(select(InvestigationUsageReservation)).state == 'reserved'
    assert not calls


def test_approval_expiring_after_preflight_rolls_back_send_marker(client, factory, github_auth, monkeypatch):
    item = setup_fixture(client, factory, github_auth, monkeypatch)
    original = github_auth.issue
    def expire(*args):
        with factory.begin() as db:
            db.get(InvestigationExecutorApproval, item['approval']).expires_at = now() - timedelta(seconds=1)
        return original(*args)
    github_auth.issue = expire
    calls = []
    run_fake(factory, github_auth, item, lambda req: calls.append(req))
    with factory() as db:
        assert db.get(InvestigationExecutorApproval, item['approval']).state == 'ready'
        assert db.scalar(select(InvestigationUsageReservation)).state == 'reserved'
        assert db.get(InvestigationReportJob, item['job']).status == 'failed'
    assert not calls


def test_crash_after_send_consumes_approval_and_holds_full_reservation(client, factory, github_auth, monkeypatch):
    item = setup_fixture(client, factory, github_auth, monkeypatch)
    calls = []
    def crash(request):
        calls.append(request)
        raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        run_fake(factory, github_auth, item, crash)
    with pytest.raises(ModelError, match='approval_invalid'):
        run_fake(factory, github_auth, item, crash)
    with factory() as db:
        assert db.get(InvestigationExecutorApproval, item['approval']).state == 'consumed'
        usage = db.scalar(select(InvestigationUsageReservation))
        assert usage.state == 'uncertain' and usage.reserved_microusd == 5_815_551
        assert db.scalar(select(InvestigationRealReport)) is None
    assert len(calls) == 1


def test_actual_mode_cannot_create_executor_approval(client, factory, github_auth, monkeypatch):
    item = setup_fixture(client, factory, github_auth, monkeypatch)
    with factory.begin() as db:
        db.get(InvestigationExperiment, item['experiment']).mode = 'actual'
    with pytest.raises(ModelError, match='approval_invalid'):
        create_fake_approval(factory, experiment_id=item['experiment'], job_id=item['job'],
                             manifest=item['manifest'], expires_at=now() + timedelta(minutes=10))


def test_forged_database_manifest_hash_cannot_authorize_different_fixture(client, factory, github_auth, monkeypatch):
    item = setup_fixture(client, factory, github_auth, monkeypatch)
    forged = deepcopy(item['manifest'])
    forged['fixture_id'] = 'other'
    with factory.begin() as db:
        db.get(InvestigationExecutorApproval, item['approval']).manifest_sha256 = digest(canonical(forged))
    calls = []
    run_fake(factory, github_auth, item, lambda req: calls.append(req), manifest=forged)
    with factory() as db:
        assert db.get(InvestigationReportJob, item['job']).status == 'failed'
        assert db.get(InvestigationExecutorApproval, item['approval']).state == 'ready'
    assert not calls


@pytest.mark.parametrize('mock_transport', [False, True])
def test_actual_transport_is_unconditionally_blocked_before_network(mock_transport):
    class Row:
        job_id = 'job'
        state = 'reserved'
        lease_token = 'lease'
        max_output_tokens = 2048
        mode = 'actual'
        experiment_id = 'experiment'
    class DB:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def get(self, *args): return Row()
    from test_report_model import package
    transport = httpx.MockTransport(lambda request: pytest.fail('must not send')) if mock_transport else None
    adapter = OpenAIInvestigationModel('synthetic-key', transport=transport)
    with pytest.raises(ModelError, match='model_not_enabled'):
        adapter._generate_reserved(model_request(package()), factory=DB, job_id='job',
                                   lease='lease', reservation_id='reservation')


def test_fake_mode_refuses_unrelated_or_non_mock_transport(client, factory, github_auth, monkeypatch):
    item = setup_fixture(client, factory, github_auth, monkeypatch)
    with pytest.raises(ModelError, match='approval_invalid'):
        execute_fake(factory, root=ROOT, job_id=item['job'], experiment_id=item['experiment'],
                     approval_id=item['approval'], manifest=item['manifest'], transport=None, github=github_auth)
    class Factory:
        kw = {'bind': type('Engine', (), {'url': factory.kw['bind'].url.set(database='normal_application')})()}
    with pytest.raises(ModelError, match='approval_invalid'):
        isolated_port(Factory())


@pytest.mark.parametrize('key,value', [('INVESTIGATION_PROVIDER', 'openai'),
    ('INVESTIGATION_REAL_ENABLED', 'true'), ('INVESTIGATION_PAID_BACKGROUND_ENABLED', 'true'),
    ('INVESTIGATION_OPENAI_API_KEY', 'synthetic-key'), ('OPENAI_API_KEY', 'synthetic-key'),
    ('INVESTIGATION_OPENAI_ORGANIZATION', 'synthetic-org'), ('INVESTIGATION_OPENAI_PROJECT', 'synthetic-project'),
    ('INVESTIGATION_COUNT_EXTERNAL_ENABLED', 'true'),
    ('INVESTIGATION_EXPERIMENT_ID', 'synthetic'), ('EMBEDDING_PROVIDER', 'openai'),
    ('EMBEDDING_ALLOW_PAID', 'true'), ('EMBEDDING_API_KEY', 'synthetic-key')])
def test_fake_executor_rejects_paid_configuration(key, value, monkeypatch):
    monkeypatch.setenv(key, value)
    with pytest.raises(ModelError, match='model_not_enabled'):
        require_fake_configuration()


def test_no_live_cli_mode(monkeypatch):
    from app.evaluation.experiment_executor import main
    monkeypatch.setattr('sys.argv', ['experiment_executor', '--live'])
    with pytest.raises(SystemExit) as result:
        main()
    assert result.value.code != 0


def test_module_entry_uses_canonical_executor_classes(monkeypatch):
    from app.evaluation import experiment_executor
    calls = []
    monkeypatch.setattr(experiment_executor, 'main', lambda: calls.append(experiment_executor.ApprovedLiveModel))
    with pytest.warns(RuntimeWarning, match='found in sys.modules'):
        runpy.run_module('app.evaluation.experiment_executor', run_name='__main__')
    assert calls == [experiment_executor.ApprovedLiveModel]


def test_postgres_approval_send_marker_is_atomic_under_concurrency(client, factory, github_auth, monkeypatch):
    if factory.kw['bind'].dialect.name != 'postgresql':
        pytest.skip('PostgreSQL row locks required')
    item = setup_fixture(client, factory, github_auth, monkeypatch)
    lease = str(uuid4())
    with factory.begin() as db:
        task = db.get(InvestigationReportJob, item['job'])
        task.status, task.lease_token = 'running', lease
        task.lease_expires_at = now() + timedelta(minutes=4)
    reservation_id, _, _ = reserve(factory, item['job'], lease)
    barrier = Barrier(2)
    def attempt(_):
        model = ApprovedFakeModel(root=ROOT, job_id=item['job'], experiment_id=item['experiment'],
            approval_id=item['approval'], manifest_sha256=digest(canonical(item['manifest'])),
            transport=httpx.MockTransport(lambda request: response('{}')))
        model._expected_request_sha256 = item['manifest']['request_sha256']
        barrier.wait(timeout=10)
        try:
            model._mark_sent(factory, item['job'], lease, reservation_id, item['payload'])
            return 'sent'
        except ModelError:
            return 'rejected'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert sorted(results) == ['rejected', 'sent']
    with factory() as db:
        assert db.get(InvestigationExecutorApproval, item['approval']).state == 'consumed'
        assert db.get(InvestigationUsageReservation, reservation_id).state == 'sent'


def test_postgres_simulated_approval_cannot_authorize_live_model(client, factory, github_auth, monkeypatch, tmp_path):
    if factory.kw['bind'].dialect.name != 'postgresql':
        pytest.skip('PostgreSQL approval and row locks required')
    item = setup_fixture(client, factory, github_auth, monkeypatch)
    private = tmp_path / 'private'
    private.mkdir(mode=0o700)
    write_private(private, item['payload'], item['manifest'])
    with pytest.raises(ModelError, match='pricing_unverified'):
        record_live_approval(factory, ROOT, experiment_id=item['experiment'], job_id=item['job'],
            directory=private, request_hash=item['manifest']['request_sha256'],
            manifest_hash=digest(canonical(item['manifest'])), screening_acknowledged=True,
            pricing_acknowledged=True)
    calls = []
    model = ApprovedLiveModel(root=ROOT, experiment_id=item['experiment'], job_id=item['job'],
        approval_id=item['approval'], manifest_sha256=digest(canonical(item['manifest'])), api_key='synthetic-key',
        transport=httpx.MockTransport(lambda request: calls.append(request)))
    from app.modules.investigation.report_worker import process_report
    with network_fence(factory.kw['bind'].url.port):
        process_report(item['job'], factory, github_auth, model)
    with factory() as db:
        assert db.get(InvestigationExecutorApproval, item['approval']).state == 'ready'
        assert db.scalar(select(InvestigationUsageReservation)).state == 'reserved'
        assert db.scalar(select(InvestigationRealReport)) is None
    assert not calls


def test_postgres_stress_guard_does_not_promote_or_record_paid_approval(client, factory, github_auth, monkeypatch, tmp_path):
    if factory.kw['bind'].dialect.name != 'postgresql':
        pytest.skip('PostgreSQL approval and row locks required')
    from app.evaluation import experiment_executor
    item = setup_fixture(client, factory, github_auth, monkeypatch)
    private = tmp_path / 'private'
    private.mkdir(mode=0o700)
    write_private(private, item['payload'], item['manifest'])
    # Simulate a separately verified pricing gate; the stressed reservation still exceeds $6.
    monkeypatch.setattr(experiment_executor, 'require_verified_actual_pricing', lambda: None)
    with pytest.raises(ModelError, match='budget_exhausted'):
        record_live_approval(factory, ROOT, experiment_id=item['experiment'], job_id=item['job'],
            directory=private, request_hash=item['manifest']['request_sha256'],
            manifest_hash=digest(canonical(item['manifest'])), screening_acknowledged=True,
            pricing_acknowledged=True)
    with factory() as db:
        assert db.get(InvestigationExperiment, item['experiment']).mode == 'simulated'
        approvals = db.scalars(select(InvestigationExecutorApproval)).all()
        assert len(approvals) == 1 and approvals[0].mode == 'simulated' and approvals[0].state == 'ready'
        assert db.scalar(select(InvestigationUsageReservation)) is None
