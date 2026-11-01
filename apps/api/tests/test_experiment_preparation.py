import hashlib
import json
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.domain.models import Base, CodeChunk, IndexedFile
from app.evaluation import experiment_preparation
from app.evaluation.disclosure_screen import screen_exact
from app.evaluation.experiment_executor import canonical, digest, read_private, record_live_approval, template
from app.evaluation.provider_harness import COMMIT, network_fence
from app.modules.investigation.report_model import ModelError
from app.modules.investigation.retrieval import Candidate, fingerprint_chunk

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize('url,run_id', [
    ('sqlite://', 'a' * 16),
    ('postgresql+psycopg://repopilot_fixture:x@127.0.0.1:5432/repopilot', 'a' * 16),
    ('postgresql+psycopg://repopilot_fixture:x@remote.invalid:5432/repopilot_5b2b_' + 'a' * 16, 'a' * 16),
    ('postgresql+psycopg://repopilot_fixture:x@127.0.0.1:5432/repopilot_5b2b_' + 'b' * 16, 'a' * 16),
    ('postgresql+psycopg://repopilot_fixture:x@127.0.0.1:5432/repopilot_5b2b_' + 'a' * 16 + '?host=remote', 'a' * 16),
])
def test_preparation_refuses_unrelated_database(url, run_id):
    with pytest.raises(ValueError):
        experiment_preparation.disposable_url(url, run_id)


@pytest.mark.parametrize('revision,accepted', [
    ('0010', False), ('0011', True), ('0012', True), ('0013', True), ('0014', False),
])
def test_preparation_checks_and_records_supported_database_revision(monkeypatch, revision, accepted):
    engine = create_engine('sqlite://')
    @event.listens_for(engine, 'connect')
    def database_name(connection, record):
        connection.create_function('current_database', 0, lambda: 'disposable-fixture')
    with engine.begin() as db:
        db.execute(text('CREATE TABLE alembic_version (version_num TEXT NOT NULL)'))
        db.execute(text('INSERT INTO alembic_version (version_num) VALUES (:revision)'), {'revision': revision})
    class EmptyInspector:
        def get_table_names(self, schema=None):
            return ['alembic_version']
    monkeypatch.setattr(experiment_preparation, 'inspect', lambda db: EmptyInspector())
    url = make_url('sqlite:///disposable-fixture')
    try:
        if accepted:
            assert experiment_preparation.assert_empty_database(engine, url) == revision
        else:
            with pytest.raises(ValueError, match='unexpected_database'):
                experiment_preparation.assert_empty_database(engine, url)
    finally:
        engine.dispose()


def test_synthetic_preparation_persists_no_approval_or_request(monkeypatch, tmp_path):
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    @event.listens_for(engine, 'connect')
    def foreign_keys(connection, record):
        connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    monkeypatch.setattr(experiment_preparation, 'create_engine', lambda *args, **kwargs: engine)
    monkeypatch.setattr(experiment_preparation, 'assert_empty_database', lambda *args: '0012')
    monkeypatch.setattr(experiment_preparation, 'disposable_url', lambda url, run_id: url)
    for name, value in {'APP_ENV': 'test', 'DATABASE_URL': 'sqlite://', 'DEMO_AUTH_ENABLED': 'false',
        'GITHUB_WEBHOOK_SECRET': 'fixture-' + 'x' * 40, 'GITHUB_OAUTH_ENABLED': 'true',
        'GITHUB_APP_ID': '123', 'GITHUB_CLIENT_ID': 'fixture', 'GITHUB_CLIENT_SECRET': 'fixture-oauth-secret',
        'GITHUB_TOKEN_ENCRYPTION_KEY': Fernet.generate_key().decode(),
        'GITHUB_CALLBACK_URL': 'http://localhost:3000/api/auth/callback', 'WEB_ORIGIN': 'http://localhost:3000',
        'INVESTIGATION_PROVIDER': 'mock', 'INVESTIGATION_REAL_ENABLED': 'false',
        'INVESTIGATION_PAID_BACKGROUND_ENABLED': 'false', 'EMBEDDING_PROVIDER': 'disabled'}.items():
        monkeypatch.setenv(name, value)
    for name in ('INVESTIGATION_OPENAI_API_KEY', 'INVESTIGATION_EXPERIMENT_ID', 'OPENAI_API_KEY', 'EMBEDDING_API_KEY'):
        monkeypatch.delenv(name, raising=False)
    def retrieve(factory, **kwargs):
        with factory() as db:
            chunk = db.scalar(select(CodeChunk).where(CodeChunk.symbol == 'valid_signature'))
            file = db.get(IndexedFile, chunk.file_id)
            query = kwargs['queries'][0]
            return [Candidate(chunk.id, file.id, file.path, chunk.symbol, chunk.start_line, chunk.end_line,
                fingerprint_chunk(chunk, file), query.id, hashlib.sha256(query.text.encode()).hexdigest(), 1, 0)]
    monkeypatch.setattr('app.modules.investigation.retrieval.retrieve_candidates', retrieve)
    def never_call(*args, **kwargs):
        raise AssertionError('provider_must_not_be_called')
    monkeypatch.setattr('app.modules.investigation.openai_provider.OpenAIInvestigationModel._generate_reserved', never_call)
    review = tmp_path / 'review'
    review.mkdir(mode=0o700)
    get_settings.cache_clear()
    try:
        with network_fence(0):
            result = experiment_preparation.stage(ROOT, make_url('sqlite://'), 'a' * 16, review_directory=review)
    finally:
        get_settings.cache_clear()
    assert result['source_commit'] == COMMIT and result['experiment_mode'] == 'simulated'
    assert result['migration'] == '0012'
    assert result['counts'] == {'investigations': 1, 'report_jobs': 1, 'approvals': 0, 'reservations': 0, 'reports': 0}
    assert result['report_job_state'] == 'queued' and len(result['evidence']) == 1
    payload, manifest = read_private(review, ROOT, experiment_id=result['experiment_id'], job_id=result['report_job_id'])
    assert result['request_sha256'] == digest(canonical(payload))
    assert result['manifest_sha256'] == digest(canonical(manifest))
    assert result['investigation_id'] == manifest['investigation_id'] and result['snapshot_id'] == manifest['snapshot_id']
    assert result['disclosure_screening']['request_sha256'] == result['request_sha256']
    assert 'fixture-oauth-secret' not in json.dumps(result) + json.dumps(manifest)


def test_disclosure_screen_uses_committed_source_and_rejects_changed_content():
    with network_fence(0):
        payload, manifest = template(ROOT)
        result = screen_exact(ROOT, payload, manifest)
    assert result['source_sha256'] == 'b49bb45a35edd38fc5bcbf010a692ba3453cc8ec97824c67b9fc1913095e5fcd'
    assert [(item['start_line'], item['end_line']) for item in result['source_ranges']] == [(1, 5), (6, 8)]
    assert not any(count for item in result['screened_patterns'].values() for count in item.values())
    payload['model'] = 'other-model'
    with pytest.raises(ValueError, match='screen_hash_mismatch'):
        screen_exact(ROOT, payload, manifest)


@pytest.mark.parametrize('screening,pricing', [(False, False), (True, False), (False, True)])
def test_paid_approval_fails_before_database_without_explicit_review_acknowledgements(screening, pricing):
    with pytest.raises(ModelError, match='approval_invalid'):
        record_live_approval(None, ROOT, experiment_id='', job_id='', directory='', request_hash='',
                             manifest_hash='', screening_acknowledged=screening, pricing_acknowledged=pricing)
