"""Isolated synthetic report evaluation. This module has no real-provider execution mode."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import socket
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

COMMIT = '30705da4c044192cab4ac207e253ab8e8a1bd100'
TREE = 'beac4e3116133a810f679761e17a7441fa77c2d7'
DATASET_HASH = '416cbf9e46b9399cf78d118f581a882d16cf512da439d352d3af29674c447bf6'
CASE_ID = 'signature_exact'
REPOSITORY = 'roshan-pandit1/RepoPilot'
EXPECTED_PATH = 'apps/api/app/modules/github/security.py'


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def safe_url(raw, run_id):
    require(bool(re.fullmatch(r'[0-9a-f]{16}', run_id or '')), 'invalid_run_id')
    try:
        url = make_url(raw)
    except Exception:
        raise ValueError('invalid_disposable_database') from None
    require(url.get_backend_name() == 'postgresql' and url.host == '127.0.0.1'
            and url.username == 'repopilot_fixture' and url.port and not url.query
            and url.database == f'repopilot_5b2a_{run_id}', 'invalid_disposable_database')
    return url


@contextmanager
def network_fence(db_port):
    """Block Python network access except the dedicated loopback PostgreSQL port."""
    connect, connect_ex, lookup = socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo
    sendto = socket.socket.sendto
    sendmsg = getattr(socket.socket, 'sendmsg', None)
    def allowed(address):
        return isinstance(address, tuple) and len(address) >= 2 and address[0] == '127.0.0.1' and address[1] == db_port
    def guarded_connect(sock, address):
        if not allowed(address):
            raise OSError('evaluation_network_blocked')
        return connect(sock, address)
    def guarded_connect_ex(sock, address):
        if not allowed(address):
            raise OSError('evaluation_network_blocked')
        return connect_ex(sock, address)
    def guarded_lookup(host, port, *args, **kwargs):
        if host != '127.0.0.1' or str(port) != str(db_port):
            raise OSError('evaluation_network_blocked')
        return lookup(host, port, *args, **kwargs)
    def guarded_sendto(sock, *args):
        if not args or not allowed(args[-1]):
            raise OSError('evaluation_network_blocked')
        return sendto(sock, *args)
    def blocked_sendmsg(*args, **kwargs):
        raise OSError('evaluation_network_blocked')
    socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo = guarded_connect, guarded_connect_ex, guarded_lookup
    socket.socket.sendto = guarded_sendto
    if sendmsg is not None:
        socket.socket.sendmsg = blocked_sendmsg
    try:
        yield
    finally:
        socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo = connect, connect_ex, lookup
        socket.socket.sendto = sendto
        if sendmsg is not None:
            socket.socket.sendmsg = sendmsg


def load_fixture(root):
    from app.evaluation.git_source import GitSource
    from app.evaluation.verify_labels import valid_label
    from app.modules.ingestion.code_chunking import chunk_python
    from app.modules.ingestion.code_selection import contains_sensitive_source, decode_source
    from app.modules.ingestion.code_snapshot import plan_snapshot
    raw = (root / 'apps/api/evaluation/issue-report-v1.json').read_bytes()
    require(hashlib.sha256(raw).hexdigest() == DATASET_HASH, 'dataset_hash_mismatch')
    dataset = json.loads(raw)
    require(dataset.get('commit_sha') == COMMIT and dataset.get('source_tree_sha') == TREE
            and dataset.get('repository') == REPOSITORY, 'dataset_provenance_mismatch')
    cases = [case for case in dataset['cases'] if case.get('issue_id') == CASE_ID]
    require(len(cases) == 1, 'fixture_missing')
    case = cases[0]
    require(case['source_commit'] == COMMIT and case['score_retrieval'] is True
            and case['relevance'] == [{'path': EXPECTED_PATH, 'symbol': 'valid_signature',
                                       'start_line': 6, 'end_line': 8}], 'fixture_label_changed')
    source = GitSource(root, COMMIT, REPOSITORY)
    require(source._git('rev-parse', f'{COMMIT}^{{tree}}').decode().strip() == TREE, 'tree_mismatch')
    plan = plan_snapshot(source, '', REPOSITORY)
    files = [item for item in plan.files if item.path == EXPECTED_PATH]
    require(len(files) == 1, 'fixture_source_unavailable')
    file = files[0]
    raw_source = source.blob('', REPOSITORY, file.blob_sha, file.size)
    content = decode_source(raw_source, 100_000)
    require(content is not None and not contains_sensitive_source(content)
            and valid_label(content, case['relevance'][0]), 'fixture_label_invalid')
    chunks = chunk_python(content)
    matches = [chunk for chunk in chunks if chunk.symbol == 'valid_signature'
               and chunk.start_line <= 6 <= 8 <= chunk.end_line]
    require(len(matches) == 1, 'fixture_chunk_missing')
    return dataset, case, raw_source, chunks, file, len(plan.files) - 1 + plan.skipped_files


def preview_payload(payload, *, run_id, database, snapshot_id, evidence):
    """Metadata and a hash only; no issue text, source, headers or credentials."""
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode()
    data = json.loads(payload['input'][0]['content'])
    return {'run_id': run_id, 'database': database, 'source_commit': COMMIT, 'snapshot_id': snapshot_id,
        'case_id': CASE_ID, 'request_sha256': hashlib.sha256(encoded).hexdigest(),
        'canonical_request_bytes': len(encoded), 'request_fields': sorted(payload),
        'untrusted_fields': sorted(data), 'title_bytes': len(data['title'].encode()),
        'body_bytes': len(data['body'].encode()), 'comment_count': len(data['comments']),
        'evidence_count': len(data['evidence']),
        'evidence': [{'chunk_id': row['chunk_id'], 'path': row['path'], 'symbol': row['symbol'],
                      'start_line': row['start_line'], 'end_line': row['end_line'],
                      'excerpt_bytes': len(row['excerpt'].encode())} for row in data['evidence']],
        'expected_evidence_ids': [item['chunk_id'] for item in evidence],
        'input_token_upper_bound': 1_050_000, 'output_token_limit': payload['max_output_tokens'],
        'exact_input_tokens': None, 'exact_input_tokens_note': 'Not measured; no provider token-count request made.'}


def write_new(path, contents):
    with path.open('x', encoding='utf-8') as stream:
        stream.write(contents)


def main():
    if not __debug__:
        raise SystemExit('Optimized Python is not permitted.')
    run_id = os.environ.get('REPOPILOT_5B2A_RUN_ID', '')
    url = safe_url(os.environ.get('DATABASE_URL', ''), run_id)
    require(os.environ.get('INVESTIGATION_PROVIDER') == 'mock'
            and os.environ.get('INVESTIGATION_REAL_ENABLED') == 'false'
            and os.environ.get('INVESTIGATION_PAID_BACKGROUND_ENABLED') == 'false'
            and os.environ.get('EMBEDDING_PROVIDER') == 'disabled'
            and not os.environ.get('INVESTIGATION_OPENAI_API_KEY'), 'unsafe_evaluation_configuration')
    root = Path(os.environ['REPOPILOT_GIT_ROOT']).resolve()
    output = root / 'apps/api/evaluation' / f'5b2a-{run_id}'
    summary_path = output.parent / f'5b2a-{run_id}-pytest.json'
    summary = json.loads(summary_path.read_text())
    require(summary.get('run_id') == run_id and summary.get('database') == url.database
            and summary.get('exit_code') == 0 and summary.get('skipped') == 0
            and summary.get('collected', 0) >= 300, 'test_summary_unavailable')
    for suffix in ('.json', '.md', '-preview.json'):
        require(not Path(str(output) + suffix).exists(), 'output_exists')
    # Git is restricted to local objects; a missing object must never trigger a fetch.
    os.environ.update(GIT_TERMINAL_PROMPT='0', GIT_NO_LAZY_FETCH='1', GIT_ALLOW_PROTOCOL='',
                      GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                      GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='protocol.allow', GIT_CONFIG_VALUE_0='never')
    os.environ.update(APP_ENV='test', DEMO_AUTH_ENABLED='false', DEMO_API_TOKEN='',
        GITHUB_OAUTH_ENABLED='true', GITHUB_APP_ID='123', GITHUB_CLIENT_ID='fixture',
        GITHUB_CLIENT_SECRET='fixture-oauth-secret-039f02476aa047cbb762e9d4',
        GITHUB_CALLBACK_URL='http://localhost:3000/api/auth/callback', WEB_ORIGIN='http://localhost:3000',
        GITHUB_WEBHOOK_SECRET='fixture-' + 'x' * 40, EMBEDDING_ALLOW_PAID='false',
        EMBEDDING_API_KEY='', REDIS_URL='redis://127.0.0.1:6379/0')
    from cryptography.fernet import Fernet
    os.environ['GITHUB_TOKEN_ENCRYPTION_KEY'] = Fernet.generate_key().decode()
    for name in ('httpx', 'httpx2'):
        logging.getLogger(name).setLevel(logging.WARNING)
    with network_fence(url.port):
        return _evaluate(root, url, run_id, output, summary)


def _evaluate(root, url, run_id, output, summary):
    url = safe_url(url, run_id)
    from fastapi.testclient import TestClient
    from app.core.config import get_settings
    from app.domain.models import (CodeChunk, CodeSnapshot, IndexedFile, InvestigationExperiment,
        InvestigationJob, InvestigationProviderSelection, InvestigationRealReport, InvestigationReportJob,
        InvestigationReportOutbox, InvestigationUsageReservation, Repository, now)
    from app.evaluation.issue_report import assess_report
    from app.evaluation.retrieval import citation_valid, match_label
    from app.infra.database import get_db
    from app.main import app
    from app.modules.github.client import get_github_client
    from app.modules.github.issue_context import build_context
    from app.modules.investigation.openai_provider import OpenAIInvestigationModel, build_responses_payload
    from app.modules.investigation.report_model import build_package, model_request
    from app.modules.investigation.report_worker import process_report
    from app.modules.investigation.reporting import evidence_inputs
    from app.modules.investigation.usage_ledger import INPUT_WINDOW, MODEL, OUTPUT_LIMIT, upper_cost
    from app.workers.tasks import process_investigation

    get_settings.cache_clear()
    dataset, case, source_bytes, chunks, source_file, omitted = load_fixture(root)
    engine = create_engine(url, hide_parameters=True)
    try:
        with engine.connect() as db:
            database = db.execute(text('select current_database()')).scalar_one()
            revision = db.execute(text('select version_num from alembic_version')).scalar_one()
            require(database == url.database and revision == '0010', 'wrong_database_or_revision')
            preparer = engine.dialect.identifier_preparer
            for table in inspect(db).get_table_names(schema='public'):
                if table != 'alembic_version':
                    require(db.execute(text('SELECT count(*) FROM public.' + preparer.quote(table))).scalar_one() == 0,
                            'disposable_database_not_empty')
        factory = sessionmaker(engine, expire_on_commit=False)
        sys.path.insert(0, str(root / 'apps/api/tests'))
        from test_auth_enrollment import FakeGitHub, csrf, sign_in

        class FixtureGitHub(FakeGitHub):
            def repositories(self, token, installation_id):
                require(installation_id == 901, 'fixture_installation_mismatch')
                return ([{'id': 902, 'full_name': REPOSITORY, 'private': False}]
                        if self.include_repository else [])

        github = FixtureGitHub()
        issue = {'id': 990, 'number': 5, 'title': case['title'], 'body': case['body'], 'state': 'open',
                 'created_at': '2026-01-01T00:00:00Z', 'updated_at': '2026-01-01T00:00:00Z',
                 'comments': 0, 'labels': []}
        github.issue = lambda *args: dict(issue)
        github.issue_comments = lambda *args: []
        def db_session():
            with factory() as db:
                yield db
        app.dependency_overrides[get_db] = db_session
        app.dependency_overrides[get_github_client] = lambda: github
        with TestClient(app) as client:
            unauth = client.get('/v1/repositories/902/investigations/11111111-1111-4111-8111-111111111111/report')
            require(unauth.status_code == 401, 'unauthenticated_access_allowed')
            sign_in(client)
            require(client.post('/v1/installations/901/enroll', headers=csrf(client)).status_code == 200,
                    'fixture_enrollment_failed')
            require(client.post('/v1/installations/901/repositories/902/select', headers=csrf(client)).status_code == 200,
                    'fixture_selection_failed')
            snapshot_id, file_id = str(uuid4()), str(uuid4())
            with factory.begin() as db:
                repo = db.get(Repository, 902)
                require(repo and repo.full_name == REPOSITORY, 'fixture_repository_mismatch')
                tenant_id = repo.tenant_id
                db.add(CodeSnapshot(id=snapshot_id, repository_id=repo.id, tenant_id=tenant_id,
                    commit_sha=COMMIT, published=True, file_count=1, chunk_count=len(chunks), skipped_count=omitted))
                db.flush()
                db.add(IndexedFile(id=file_id, snapshot_id=snapshot_id, repository_id=repo.id, tenant_id=tenant_id,
                    path=EXPECTED_PATH, content_hash=hashlib.sha256(source_bytes).hexdigest()))
                db.flush()
                for chunk in chunks:
                    db.add(CodeChunk(id=str(uuid4()), file_id=file_id, repository_id=repo.id, tenant_id=tenant_id,
                        symbol=chunk.symbol, start_line=chunk.start_line, end_line=chunk.end_line, source_text=chunk.text))
            submitted = client.post('/v1/repositories/902/issues/5/investigations', headers=csrf(client))
            require(submitted.status_code == 202, 'fixture_investigation_failed')
            parent_id = submitted.json()['job_id']
            process_investigation(parent_id, factory, github)
            status = client.get(f'/v1/repositories/902/investigations/{parent_id}')
            evidence_response = client.get(f'/v1/repositories/902/investigations/{parent_id}/evidence')
            require(status.status_code == 200 and evidence_response.status_code == 200, 'fixture_evidence_unavailable')
            job, evidence_result = status.json(), evidence_response.json()
            evidence = evidence_result['items']
            require(job['status'] == 'completed' and job['snapshot_id'] == snapshot_id
                    and evidence_result['commit_sha'] == COMMIT and evidence_result['snapshot_id'] == snapshot_id
                    and bool(evidence) and all(citation_valid(item, REPOSITORY, COMMIT) for item in evidence)
                    and any(match_label(item, case['relevance'][0]) for item in evidence), 'fixture_retrieval_mismatch')
            lines = source_bytes.decode('utf-8').splitlines(keepends=True)
            with factory() as db:
                for item in evidence:
                    chunk = db.get(CodeChunk, item['chunk_id'])
                    require(chunk and item['path'] == EXPECTED_PATH and chunk.file_id == file_id
                            and chunk.source_text == ''.join(lines[chunk.start_line - 1:chunk.end_line])
                            and (item['start_line'], item['end_line']) == (chunk.start_line, chunk.end_line),
                            'fixture_chunk_mismatch')
                parent = db.get(InvestigationJob, parent_id)
                snapshot = db.get(CodeSnapshot, snapshot_id)
                evidence_rows = evidence_inputs(db, parent, snapshot)
            report_url = f'/v1/repositories/902/investigations/{parent_id}/report'
            submitted = client.post(report_url, headers=csrf(client))
            require(submitted.status_code == 202, 'fixture_report_job_failed')
            report_job_id = submitted.json()['report_job_id']
            experiment_id = str(uuid4())
            with factory.begin() as db:
                db.add(InvestigationExperiment(id=experiment_id, tenant_id=tenant_id, enabled=True,
                    mode='simulated', provider='openai', model=MODEL, budget_microusd=10_000_000,
                    investigation_budget_microusd=6_000_000, max_input_tokens=INPUT_WINDOW,
                    max_output_tokens=OUTPUT_LIMIT, max_concurrent=1, max_requests=1,
                    pricing_checked_at=now(), expires_at=now() + timedelta(hours=1)))
                db.flush()
                db.add(InvestigationProviderSelection(job_id=report_job_id, repository_id=902,
                    tenant_id=tenant_id, experiment_id=experiment_id))
            previews = []
            def fake_response(request):
                payload = json.loads(request.content)
                data = json.loads(payload['input'][0]['content'])
                context = build_context(issue, [], 902, REPOSITORY, 5, get_settings())
                context['retrieved_at'] = datetime.fromisoformat(data['issue_retrieved_at'])
                package = build_package(investigation_id=parent_id, repository_id=902, issue_id=990,
                    issue_number=5, context=context, snapshot_id=snapshot_id, commit_sha=COMMIT, evidence=evidence_rows)
                require(payload == build_responses_payload(model_request(package), OUTPUT_LIMIT), 'request_projection_mismatch')
                require('tools' not in payload and payload['service_tier'] == 'default'
                        and payload['prompt_cache_options'] == {'ttl': '30m'}, 'unsafe_provider_request')
                candidates = [item for item in data['evidence'] if item['path'] == EXPECTED_PATH
                              and item['symbol'] == 'valid_signature']
                require(len(candidates) == 1, 'labeled_evidence_not_in_input')
                selected = candidates[0]
                previews.append(preview_payload(payload, run_id=run_id, database=database,
                                                snapshot_id=snapshot_id, evidence=evidence))
                reference = {key: selected[key] for key in ('chunk_id', 'snapshot_id', 'commit_sha', 'start_line', 'end_line')}
                draft = {'summary': 'Synthetic fixture for signature verification.',
                    'hypotheses': [{'title': 'Possible verification area',
                        'explanation': 'Inspect the selected comparison and reproduce the failure.',
                        'observations': ['The selected code compares a computed value.'],
                        'missing_or_contradictory': ['No failure reproduction was supplied.'],
                        'evidence': [reference], 'contradictory_evidence': []}],
                    'missing_evidence': ['No actual failure has been established.'],
                    'next_steps': ['Reproduce the issue with controlled input.'],
                    'warnings': ['Synthetic fake response; no model reasoning was performed.']}
                return httpx.Response(200, json={'model': MODEL, 'service_tier': 'default', 'status': 'completed',
                    'usage': {'input_tokens': 1200, 'output_tokens': 250},
                    'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(draft)}]}]})
            model = OpenAIInvestigationModel('5b2a-fake-credential', transport=httpx.MockTransport(fake_response))
            process_report(report_job_id, factory, github, model)
            process_report(report_job_id, factory, github, model)
            response = client.get(report_url)
            require(response.status_code == 200 and len(previews) == 1, 'report_or_idempotency_failed')
            assessment = assess_report(response.json(), investigation_id=parent_id, repository_id=902,
                snapshot_id=snapshot_id, commit=COMMIT, evidence=evidence, issue_id=990, issue_number=5,
                expected_provider='openai', expected_model=MODEL)
            require(assessment['schema_valid'] and assessment['provenance_valid']
                    and assessment['support_labels_valid'] and assessment['references'] > 0
                    and assessment['references'] == assessment['valid_references'], 'report_grounding_failed')
            with factory() as db:
                task = db.get(InvestigationReportJob, report_job_id)
                outbox = db.get(InvestigationReportOutbox, report_job_id)
                usage = db.scalar(select(InvestigationUsageReservation).where(InvestigationUsageReservation.job_id == report_job_id))
                reports = db.scalars(select(InvestigationRealReport).where(InvestigationRealReport.report_job_id == report_job_id)).all()
                require(task.status == 'completed' and task.attempts == 1 and outbox.status == 'processed'
                        and len(reports) == 1 and usage and usage.mode == 'simulated' and usage.state == 'known'
                        and usage.reserved_microusd == upper_cost(INPUT_WINDOW, OUTPUT_LIMIT)
                        and usage.accounted_microusd == upper_cost(1200, 250), 'ledger_or_publication_failed')
                report_id = reports[0].id
                ledger = {'mode': usage.mode, 'state': usage.state, 'reserved_microusd': usage.reserved_microusd,
                          'simulated_input_tokens': usage.input_tokens, 'simulated_output_tokens': usage.output_tokens,
                          'simulated_accounted_microusd': usage.accounted_microusd, 'actual_cost_microusd': None}
            github.include_repository = False
            revoked = client.get(report_url).status_code
            require(revoked == 404, 'revoked_report_visible')
            github.include_repository = True
            client.cookies.clear()
            require(client.get(report_url).status_code == 401, 'anonymous_report_visible')
        app.dependency_overrides.clear()
        preview = previews[0]
        paths = [
            'apps/api/app/evaluation/provider_harness.py',
            'apps/api/app/evaluation/issue_report.py',
            'apps/api/app/evaluation/git_source.py',
            'apps/api/app/modules/investigation/openai_provider.py',
            'apps/api/app/modules/investigation/usage_ledger.py',
            'apps/api/app/modules/investigation/report_model.py',
            'apps/api/app/modules/investigation/report_worker.py',
            'apps/api/app/modules/investigation/retrieval.py',
            'apps/api/app/modules/ingestion/code_chunking.py',
            'apps/api/alembic/versions/0010_investigation_budget.py',
            'apps/api/tests/test_real_report_foundation.py',
            'apps/api/tests/test_provider_harness.py',
        ]
        implementation = {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in paths}
        head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], timeout=30).decode().strip()
        report = {'run_id': run_id, 'database': database, 'migration': revision,
            'evaluated_at': datetime.now().astimezone().isoformat(), 'case_id': CASE_ID,
            'dataset': dataset['version'], 'dataset_sha256': DATASET_HASH, 'source_commit': COMMIT,
            'source_tree': TREE, 'source_blob': source_file.blob_sha, 'snapshot_id': snapshot_id,
            'snapshot_scope': 'synthetic partial snapshot containing only the labeled source file',
            'omitted_eligible_files': omitted, 'investigation_id': parent_id, 'report_job_id': report_job_id,
            'report_id': report_id, 'worker_attempts': 1, 'fake_http_requests': 1,
            'provider': 'openai', 'model': MODEL, 'transport': 'httpx.MockTransport', 'ledger': ledger,
            'report_checks': assessment, 'evidence_count': len(evidence), 'labeled_evidence_available': True,
            'revoked_http': revoked, 'anonymous_http': 401, 'pytest': summary,
            'preview_sha256': preview['request_sha256'], 'evaluator_head': head,
            'implementation_sha256': implementation, 'log': f'5b2a-{run_id}.log',
            'limitations': ['Synthetic case and partial snapshot; retrieval quality is not measured.',
                'Fake response is not real model reasoning or a diagnosis.',
                'No provider request or actual provider cost was incurred.']}
        markdown = (f"# Sprint 5B2A isolated fake-provider evaluation\n\nRun: {run_id}; database: {database}\n\n"
            f"Case: {CASE_ID}; commit: {COMMIT}; snapshot: {snapshot_id}\n\n"
            f"Partial snapshot: one source file; {omitted} eligible files omitted.\n\n"
            f"Evidence: {len(evidence)}; valid report citations: {assessment['valid_references']}/{assessment['references']}.\n\n"
            f"Fake requests: 1; report attempts: 1; simulated reservation: ${ledger['reserved_microusd'] / 1_000_000:.6f}.\n\n"
            f"Simulated usage: {ledger['simulated_input_tokens']} input and {ledger['simulated_output_tokens']} output tokens.\n\n"
            f"Provider regression cases: {len(summary['provider_cases'])} passed; details in JSON and the run log.\n\n"
            "No real model call, actual provider cost or reasoning-quality score is represented.\n")
        write_new(Path(str(output) + '-preview.json'), json.dumps(preview, indent=2) + '\n')
        write_new(Path(str(output) + '.json'), json.dumps(report, indent=2) + '\n')
        write_new(Path(str(output) + '.md'), markdown)
        print(f'Evaluation complete: run={run_id}; database={database}; snapshot={snapshot_id}; '
              f'evidence={len(evidence)}; valid_citations={assessment["valid_references"]}/{assessment["references"]}.')
        print(f'Artifacts: {output}.json, {output}.md, {output}-preview.json')
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


if __name__ == '__main__':
    main()
