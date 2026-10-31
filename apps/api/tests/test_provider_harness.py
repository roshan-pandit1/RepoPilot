import json
import hashlib
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import make_url

from app.evaluation.provider_harness import (CASE_ID, COMMIT, DATASET_HASH, EXPECTED_PATH, load_fixture,
    network_fence, preview_payload, safe_url)
from app.modules.investigation.openai_provider import build_responses_payload
from app.modules.investigation.report_model import model_request
from app.modules.investigation.usage_ledger import INPUT_WINDOW, OUTPUT_LIMIT, upper_cost
from test_report_model import package


@pytest.mark.parametrize('url,run_id', [
    ('postgresql+psycopg://repopilot_fixture:x@127.0.0.1:5432/repopilot', 'a' * 16),
    ('postgresql+psycopg://repopilot_fixture:x@remote.invalid:5432/repopilot_5b2a_' + 'a' * 16, 'a' * 16),
    ('postgresql+psycopg://repopilot_fixture:x@127.0.0.1:5432/repopilot_5b2a_' + 'b' * 16, 'a' * 16),
    ('postgresql+psycopg://repopilot_fixture:x@127.0.0.1:5432/repopilot_5b2a_' + 'a' * 16 + '?host=remote', 'a' * 16),
    ('sqlite://', 'a' * 16),
])
def test_harness_refuses_unrelated_database(url, run_id):
    with pytest.raises(ValueError):
        safe_url(url, run_id)


def test_network_fence_blocks_dns_and_direct_connections():
    with network_fence(54321):
        with pytest.raises(OSError, match='evaluation_network_blocked'):
            socket.getaddrinfo('api.openai.com', 443)
        with socket.socket() as probe, pytest.raises(OSError, match='evaluation_network_blocked'):
            probe.connect(('127.0.0.1', 443))
        with socket.socket() as probe, pytest.raises(OSError, match='evaluation_network_blocked'):
            probe.connect(('1.1.1.1', 443))
        with socket.socket(type=socket.SOCK_DGRAM) as probe, pytest.raises(OSError, match='evaluation_network_blocked'):
            probe.sendto(b'x', ('1.1.1.1', 443))


def test_reviewed_budget_covers_maximum_request():
    assert upper_cost(INPUT_WINDOW, OUTPUT_LIMIT) == 5_815_551
    assert upper_cost(INPUT_WINDOW, OUTPUT_LIMIT) < 6_000_000 < 10_000_000


def test_fixture_uses_the_reviewed_committed_source():
    root = Path(__file__).resolve().parents[3]
    dataset, case, source, chunks, entry, omitted = load_fixture(root)
    assert dataset['commit_sha'] == COMMIT and case['issue_id'] == CASE_ID
    assert entry.path == EXPECTED_PATH and len(DATASET_HASH) == 64 and source
    assert any(chunk.symbol == 'valid_signature' and chunk.start_line <= 6 <= 8 <= chunk.end_line
               for chunk in chunks)
    assert omitted > 0


def test_preview_contains_metadata_and_hash_only():
    request = model_request(package())
    payload = build_responses_payload(request, 2048)
    evidence = [{'chunk_id': request.untrusted_data.evidence[0].chunk_id}]
    preview = preview_payload(payload, run_id='a' * 16, database='fixture', snapshot_id='fixture', evidence=evidence)
    rendered = json.dumps(preview)
    assert preview['input_token_upper_bound'] == 1_050_000 and preview['output_token_limit'] == 2048
    assert preview['exact_input_tokens'] is None and preview['evidence_count'] == 1
    assert 'fake-secret-value' not in rendered
    assert request.untrusted_data.title not in rendered
    assert request.untrusted_data.evidence[0].excerpt not in rendered
    assert preview['request_sha256'] == preview_payload(payload, run_id='a' * 16, database='fixture',
        snapshot_id='fixture', evidence=evidence)['request_sha256']


def test_fixture_workflow_with_fake_sqlite_retrieval(tmp_path, monkeypatch):
    """Exercise assembly and fake HTTP; real PostgreSQL lexical retrieval is checked separately."""
    from app.core.config import get_settings
    from app.domain.models import CodeChunk, IndexedFile
    from app.evaluation import provider_harness
    from app.modules.investigation.retrieval import Candidate, fingerprint_chunk

    root = Path(__file__).resolve().parents[3]
    database = tmp_path / 'fixture.db'
    raw_url = f'sqlite:///{database}'
    env = {**os.environ, 'APP_ENV': 'test', 'DATABASE_URL': raw_url,
           'GITHUB_WEBHOOK_SECRET': 'fixture-' + 'x' * 40, 'GITHUB_OAUTH_ENABLED': 'false',
           'DEMO_AUTH_ENABLED': 'false', 'EMBEDDING_PROVIDER': 'disabled'}
    subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=root / 'apps/api',
                   env=env, capture_output=True, text=True, check=True)
    for name, value in {'APP_ENV': 'test', 'DATABASE_URL': raw_url, 'DEMO_AUTH_ENABLED': 'false',
        'GITHUB_WEBHOOK_SECRET': 'fixture-' + 'x' * 40, 'GITHUB_OAUTH_ENABLED': 'true',
        'GITHUB_APP_ID': '123', 'GITHUB_CLIENT_ID': 'fixture', 'GITHUB_CLIENT_SECRET': 'fixture-oauth-secret',
        'GITHUB_TOKEN_ENCRYPTION_KEY': Fernet.generate_key().decode(),
        'GITHUB_CALLBACK_URL': 'http://localhost:3000/api/auth/callback', 'WEB_ORIGIN': 'http://localhost:3000',
        'INVESTIGATION_PROVIDER': 'mock', 'INVESTIGATION_REAL_ENABLED': 'false',
        'INVESTIGATION_PAID_BACKGROUND_ENABLED': 'false', 'EMBEDDING_PROVIDER': 'disabled'}.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv('INVESTIGATION_OPENAI_API_KEY', raising=False)
    monkeypatch.setattr(provider_harness, 'safe_url', lambda url, run_id: url)
    class EmptyInspector:
        def get_table_names(self, schema=None):
            return []
    monkeypatch.setattr(provider_harness, 'inspect', lambda db: EmptyInspector())
    def sqlite_engine(url, **kwargs):
        engine = create_engine(url, **kwargs)
        @event.listens_for(engine, 'connect')
        def add_database_name(connection, record):
            connection.create_function('current_database', 0, lambda: url.database)
        return engine
    monkeypatch.setattr(provider_harness, 'create_engine', sqlite_engine)
    def fake_retrieval(factory, **kwargs):
        with factory() as db:
            chunk = db.scalar(select(CodeChunk).where(CodeChunk.symbol == 'valid_signature'))
            file = db.get(IndexedFile, chunk.file_id)
            query = kwargs['queries'][0]
            return [Candidate(chunk.id, file.id, file.path, chunk.symbol, chunk.start_line, chunk.end_line,
                fingerprint_chunk(chunk, file), query.id, hashlib.sha256(query.text.encode()).hexdigest(), 1, 0)]
    monkeypatch.setattr('app.modules.investigation.retrieval.retrieve_candidates', fake_retrieval)
    get_settings.cache_clear()
    try:
        with network_fence(54321):
            provider_harness._evaluate(root, make_url(raw_url), 'a' * 16, tmp_path / 'result',
                {'run_id': 'a' * 16, 'database': str(database), 'exit_code': 0, 'skipped': 0,
                 'collected': 300, 'provider_cases': {'fixture': 'passed'}})
    finally:
        get_settings.cache_clear()
    result = json.loads((tmp_path / 'result.json').read_text())
    preview = json.loads((tmp_path / 'result-preview.json').read_text())
    assert result['transport'] == 'httpx.MockTransport' and result['ledger']['mode'] == 'simulated'
    assert result['report_checks']['valid_references'] == result['report_checks']['references'] == 1
    assert result['snapshot_scope'].startswith('synthetic partial') and result['revoked_http'] == 404
    assert preview['request_sha256'] == result['preview_sha256']
    assert 'fixture-oauth-secret' not in json.dumps(result) + json.dumps(preview)
