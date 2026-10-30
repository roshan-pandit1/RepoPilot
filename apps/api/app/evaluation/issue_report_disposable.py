"""Approved-only issue/report evaluation in a fresh, dedicated PostgreSQL database."""
import hashlib
import json
import logging
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

COMMIT = '30705da4c044192cab4ac207e253ab8e8a1bd100'
DATASET_HASH = '416cbf9e46b9399cf78d118f581a882d16cf512da439d352d3af29674c447bf6'


def quiet_fixture_http_logs():
    """Do not log even disposable OAuth callback query parameters."""
    # Starlette's current TestClient uses httpx2; other supported versions use httpx.
    for name in ('httpx', 'httpx2'):
        logging.getLogger(name).setLevel(logging.WARNING)


def main():
    if not __debug__:
        raise SystemExit('Optimized Python disables required evaluation safety checks.')
    if os.environ.get('REPOPILOT_4F_APPROVED_COMMIT') != COMMIT:
        raise SystemExit('Separate approval for the exact 4F disposable source snapshot is required.')
    url = make_url(os.environ['DATABASE_URL'])
    if (url.get_backend_name() != 'postgresql' or url.host != '127.0.0.1' or url.query
            or not url.database or not url.database.startswith('repopilot_4f_disposable_')
            or url.database != os.environ.get('REPOPILOT_4F_DB')):
        raise SystemExit('Refusing non-dedicated local PostgreSQL target.')
    dataset_path = Path('evaluation/issue-report-v1.json')
    raw = dataset_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != DATASET_HASH:
        raise SystemExit('Dataset hash mismatch.')
    dataset = json.loads(raw)
    if dataset['commit_sha'] != COMMIT:
        raise SystemExit('Dataset commit mismatch.')
    prefix = Path(os.environ['REPOPILOT_4F_OUTPUT'])
    if prefix.with_suffix('.json').exists() or prefix.with_suffix('.md').exists():
        raise SystemExit('Output already exists; refusing to mix or overwrite runs.')
    os.environ.update(APP_ENV='test', DEMO_AUTH_ENABLED='false', DEMO_API_TOKEN='', EMBEDDING_PROVIDER='disabled',
        EMBEDDING_API_KEY='', REDIS_URL='redis://127.0.0.1:6379/0',
        EMBEDDING_ALLOW_PAID='false', GITHUB_OAUTH_ENABLED='true', GITHUB_APP_ID='123',
        GITHUB_CLIENT_ID='fixture', GITHUB_CLIENT_SECRET='fixture-oauth-secret-039f02476aa047cbb762e9d4',
        GITHUB_CALLBACK_URL='http://localhost:3000/api/auth/callback',
        WEB_ORIGIN='http://localhost:3000', GITHUB_WEBHOOK_SECRET='fixture-' + 'x' * 40,
        INVESTIGATION_QUERY_LIMIT='3', INVESTIGATION_PER_QUERY_LIMIT='10', INVESTIGATION_EVIDENCE_LIMIT='20')
    from cryptography.fernet import Fernet
    os.environ['GITHUB_TOKEN_ENCRYPTION_KEY'] = Fernet.generate_key().decode()
    from fastapi.testclient import TestClient
    from app.core.config import get_settings
    from app.domain.models import (CodeChunk, CodeSnapshot, IndexedFile, IndexJob, InvestigationJob,
        InvestigationReport, InvestigationReportJob, InvestigationReportOutbox)
    from app.evaluation.git_source import GitSource
    from app.evaluation.issue_report import assess_report, model_grounding_probes, score_retrieval, verify_dataset
    from app.evaluation.retrieval import citation_valid, match_label
    from app.infra.database import get_db
    from app.main import app
    from app.modules.github.client import get_github_client
    from app.modules.investigation.query_builder import build_queries
    from app.modules.investigation.report_model import build_package
    from app.modules.investigation.report_worker import process_report
    from app.modules.investigation.reporting import evidence_inputs
    from app.workers.tasks import process_index, process_investigation

    # The fixture OAuth callback contains one-time test state; do not log request URLs.
    quiet_fixture_http_logs()
    get_settings.cache_clear()
    root = Path(os.environ['REPOPILOT_GIT_ROOT']).resolve()
    provenance = verify_dataset(dataset, root)
    source = GitSource(root, COMMIT, dataset['repository'])
    engine = create_engine(url, hide_parameters=True)
    with engine.connect() as db:
        database, address, port = db.execute(text('select current_database(), inet_server_addr()::text, inet_server_port()')).one()
        revision = db.execute(text('select version_num from alembic_version')).scalar_one()
        if database != url.database or revision != '0009':
            raise SystemExit('Wrong database or migration revision.')
        if db.execute(text('select count(*) from code_snapshots')).scalar_one() != 0:
            raise SystemExit('Database already contains a source snapshot.')
        server_version = db.execute(text('show server_version')).scalar_one()
    print(f'Confirmed empty disposable source database: {database}; server={address}:{port}; revision={revision}')
    factory = sessionmaker(engine, expire_on_commit=False)
    sys.path.insert(0, str(Path('tests').resolve()))
    from test_auth_enrollment import FakeGitHub, csrf, sign_in

    class FixtureGitHub(FakeGitHub):
        def repositories(self, token, installation_id):
            assert installation_id == 901
            return ([{'id': 902, 'full_name': dataset['repository'], 'private': False}]
                    if self.include_repository else [])

    github = FixtureGitHub()
    def get_session():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = get_session
    app.dependency_overrides[get_github_client] = lambda: github
    entries = {entry['path']: entry for entry in source.entries}
    results, report_rows, probes = [], [], None
    with TestClient(app) as client:
        unauthenticated = client.get('/v1/repositories/902/investigations/'
                                     '11111111-1111-4111-8111-111111111111/report').status_code
        assert unauthenticated == 401
        sign_in(client)
        assert client.post('/v1/installations/901/enroll', headers=csrf(client)).status_code == 200
        assert client.post('/v1/installations/901/repositories/902/select', headers=csrf(client)).status_code == 200
        created = client.post('/v1/repositories/902/index', headers=csrf(client))
        assert created.status_code == 202
        index_job = created.json()['job_id']
        # The existing worker applies source selection, chunking, authorization and publication.
        process_index(index_job, factory, github, source)
        with factory() as db:
            job = db.get(IndexJob, index_job)
            assert job.status in {'completed', 'partial'}
            snapshot = db.scalar(select(CodeSnapshot).where(CodeSnapshot.published.is_(True)))
            assert snapshot and snapshot.commit_sha == COMMIT and snapshot.repository_id == 902
            snapshot_id, tenant = snapshot.id, snapshot.tenant_id
            snapshot_counts = {'files': snapshot.file_count, 'chunks': snapshot.chunk_count,
                               'skipped_files': snapshot.skipped_count}
            published = db.execute(select(CodeChunk, IndexedFile).join(IndexedFile, CodeChunk.file_id == IndexedFile.id)
                                   .where(IndexedFile.snapshot_id == snapshot_id)).all()
            assert len(published) == snapshot.chunk_count
            locations = [{'path': file.path, 'symbol': chunk.symbol, 'start_line': chunk.start_line,
                          'end_line': chunk.end_line} for chunk, file in published]
            assert all(any(match_label(item, label) for item in locations)
                       for case in dataset['cases'] for label in case['relevance'])
        print(f'Published disposable snapshot {snapshot_id}; commit={COMMIT}; counts={snapshot_counts}')
        for offset, case in enumerate(dataset['cases']):
            number, issue_id = 400 + offset, 100_000 + offset
            github.issue = lambda token, name, num, case=case, issue_id=issue_id: {
                'id': issue_id, 'number': num, 'title': case['title'], 'body': case['body'], 'state': 'open',
                'created_at': '2026-01-01T00:00:00Z', 'updated_at': '2026-01-01T00:00:00Z',
                'comments': 0, 'labels': []}
            github.issue_comments = lambda *args: []
            submitted = client.post(f'/v1/repositories/902/issues/{number}/investigations', headers=csrf(client))
            assert submitted.status_code == 202
            investigation = submitted.json()['job_id']
            started = time.perf_counter()
            process_investigation(investigation, factory, github)
            elapsed = (time.perf_counter() - started) * 1000
            status_response = client.get(f'/v1/repositories/902/investigations/{investigation}')
            assert status_response.status_code == 200
            status = status_response.json()
            assert status['status'] == 'completed' and status['snapshot_id'] == snapshot_id
            response = client.get(f'/v1/repositories/902/investigations/{investigation}/evidence')
            assert response.status_code == 200
            data = response.json()
            assert data['snapshot_id'] == snapshot_id and data['commit_sha'] == COMMIT
            for item in data['items']:
                assert citation_valid(item, dataset['repository'], COMMIT)
                entry = entries[item['path']]
                source_bytes = source.blob('', dataset['repository'], entry['sha'], entry['size'])
                lines = source_bytes.decode('utf-8').splitlines(keepends=True)
                with factory() as db:
                    chunk = db.get(CodeChunk, item['chunk_id'])
                    file = db.get(IndexedFile, chunk.file_id) if chunk else None
                    assert chunk and file and file.snapshot_id == snapshot_id
                    assert chunk.tenant_id == file.tenant_id == tenant and chunk.repository_id == file.repository_id == 902
                    assert hashlib.sha256(source_bytes).hexdigest() == file.content_hash
                    assert file.path == item['path'] and chunk.symbol == item['symbol']
                    assert (chunk.start_line, chunk.end_line) == (item['start_line'], item['end_line'])
                    assert 1 <= chunk.start_line <= chunk.end_line <= len(lines)
                    assert chunk.source_text == ''.join(lines[chunk.start_line - 1:chunk.end_line])
            limits = status['retrieval_limits']
            queries = build_queries(case['title'], case['body'][:limits['body_chars']], [], limits['queries'])
            results.append({'issue_id': case['issue_id'], 'snapshot_id': snapshot_id, 'commit_sha': COMMIT,
                'retrieval_status': data['retrieval_status'], 'items': data['items'], 'latency_ms': round(elapsed, 3),
                'query_version': data['query_version'], 'query_input_truncated': data['query_input_truncated'],
                'queries': [{'id': query.id, 'sha256': hashlib.sha256(query.text.encode()).hexdigest()}
                            for query in queries]})
            report_url = f'/v1/repositories/902/investigations/{investigation}/report'
            queued = client.post(report_url, headers=csrf(client))
            assert queued.status_code == 202
            report_job = queued.json()['report_job_id']
            process_report(report_job, factory, github)
            process_report(report_job, factory, github)
            report_response = client.get(report_url)
            assert report_response.status_code == 200
            check = assess_report(report_response.json(), investigation_id=investigation, repository_id=902,
                snapshot_id=snapshot_id, commit=COMMIT, evidence=data['items'], issue_id=issue_id, issue_number=number)
            with factory() as db:
                task = db.get(InvestigationReportJob, report_job)
                outbox = db.get(InvestigationReportOutbox, report_job)
                reports = db.scalars(select(InvestigationReport).where(InvestigationReport.report_job_id == report_job)).all()
                idempotent = bool(task and task.status == 'completed' and task.attempts == 1
                                  and outbox and outbox.status == 'processed' and len(reports) == 1)
                original = db.get(InvestigationJob, investigation)
                assert original and original.status == 'completed' and original.snapshot_id == snapshot_id
                if probes is None and len(data['items']) >= 2:
                    package = build_package(investigation_id=investigation, repository_id=902,
                        issue_id=issue_id, issue_number=number, context={'title': case['title'], 'body': case['body']},
                        snapshot_id=snapshot_id, commit_sha=COMMIT,
                        evidence=evidence_inputs(db, original, db.get(CodeSnapshot, snapshot_id)))
                    probes = model_grounding_probes(package)
            report_rows.append({'issue_id': case['issue_id'], 'investigation_id': investigation,
                                'report_job_id': report_job, **check, 'idempotent': idempotent})
        retrieval = score_retrieval(dataset, results, snapshot_id=snapshot_id)
        github.include_repository = False
        revoked = client.get(report_url).status_code
        github.include_repository = True
        with factory.begin() as db:
            db.get(CodeSnapshot, snapshot_id).published = False
        unavailable = client.get(f'/v1/repositories/902/investigations/{investigation}/evidence').status_code
        with factory.begin() as db:
            db.get(CodeSnapshot, snapshot_id).published = True
        assert client.post('/v1/auth/logout', headers=csrf(client)).status_code == 200
        github.user_id = github.account_id = 78
        sign_in(client)
        other_tenant = client.get(report_url).status_code
    app.dependency_overrides.clear()
    refs = sum(row['references'] for row in report_rows)
    valid_refs = sum(row['valid_references'] for row in report_rows)
    empty = [row for row in report_rows if row['empty_evidence_abstention'] is not None]
    mechanics = {'cases': len(report_rows), 'schema_valid': sum(row['schema_valid'] for row in report_rows),
        'provenance_valid': sum(row['provenance_valid'] for row in report_rows),
        'references': refs, 'valid_references': valid_refs,
        'valid_reference_rate': valid_refs / refs if refs else None,
        'support_labels_valid': sum(row['support_labels_valid'] for row in report_rows),
        'empty_evidence_cases': len(empty), 'empty_evidence_abstentions': sum(row['empty_evidence_abstention'] for row in empty),
        'idempotent_replays': sum(row['idempotent'] for row in report_rows), 'cases_detail': report_rows}
    code_paths = ['apps/api/app/evaluation/issue_report.py', 'apps/api/app/evaluation/issue_report_disposable.py',
        'apps/api/app/evaluation/git_source.py', 'apps/api/app/evaluation/retrieval.py',
        'apps/api/app/evaluation/verify_labels.py', 'apps/api/app/workers/tasks.py', 'apps/api/app/core/config.py',
        'apps/api/app/domain/models.py',
        'apps/api/app/modules/investigation/query_builder.py', 'apps/api/app/modules/investigation/retrieval.py',
        'apps/api/app/modules/investigation/routes.py', 'apps/api/app/modules/investigation/report_model.py',
        'apps/api/app/modules/investigation/report_worker.py', 'apps/api/app/modules/investigation/reporting.py',
        'apps/api/app/modules/investigation/report_routes.py', 'apps/api/app/modules/ingestion/keyword_search.py',
        'apps/api/app/modules/ingestion/code_collect.py', 'apps/api/app/modules/ingestion/code_chunking.py',
        'apps/api/app/modules/ingestion/code_persistence.py', 'apps/api/app/modules/ingestion/code_selection.py',
        'apps/api/app/modules/ingestion/code_snapshot.py', 'apps/api/app/modules/ingestion/citations.py',
        'apps/api/tests/test_auth_enrollment.py']
    implementation = {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in code_paths}
    head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    from importlib.metadata import version
    settings = get_settings()
    report = {'dataset': dataset['version'], 'dataset_sha256': DATASET_HASH, 'source_commit': COMMIT,
        'source_tree_sha': provenance['source_tree_sha'], 'snapshot_id': snapshot_id, 'database': database,
        'database_server': {'address': address, 'port': port, 'version': server_version}, 'migration': revision,
        'snapshot_counts': snapshot_counts, 'evaluated_at': datetime.now(timezone.utc).isoformat(),
        'execution': 'disposable PostgreSQL, authorized test client, fake GitHub, direct workers',
        'retrieval_configuration': {'mode': 'keyword', 'query_limit': settings.investigation_query_limit,
                                    'per_query': settings.investigation_per_query_limit,
                                    'evidence_limit': settings.investigation_evidence_limit,
                                    'statement_timeout_seconds': 3},
        'model': 'mock/deterministic-v1', 'evaluator_head': head, 'implementation_sha256': implementation,
        'runtime_versions': {'python': platform.python_version(), 'sqlalchemy': version('sqlalchemy'),
                             'pydantic': version('pydantic'), 'psycopg': version('psycopg')},
        'retrieval': retrieval, 'citation_checks': {'locally_matched': retrieval['evidence_items'], 'mismatches': 0},
        'report_mechanics': mechanics, 'grounding_probes': probes,
        'security_checks': {'unauthenticated_http': unauthenticated, 'revoked_report_http': revoked,
                            'unpublished_snapshot_http': unavailable, 'other_tenant_http': other_tenant},
        'limitations': ['Synthetic issues and incomplete labels; unlabeled results are not necessarily irrelevant.',
            'Negative and insufficient cases are unscored.', 'Direct workers and mocked GitHub, not real Celery or AI reasoning.',
            'Citations checked against local Git blobs; remote GitHub resolution was not checked.']}
    if not (unauthenticated == 401 and revoked == 404 and unavailable == 409 and other_tenant == 404):
        raise RuntimeError('Security checks did not pass.')
    prefix.with_suffix('.json').write_text(json.dumps(report, indent=2) + '\n')
    recalls = retrieval['recall']
    lines = ['# Issue-to-code and mock-report evaluation', '', f"Dataset: {report['dataset']} ({DATASET_HASH})",
        f"Commit: {COMMIT}; Git tree: {report['source_tree_sha']}; snapshot: {snapshot_id}",
        f"Database: {database}; evaluation time: {report['evaluated_at']}",
        f"Scored/unscored: {retrieval['scored_cases']}/{retrieval['unscored_cases']}",
        f"Recall@1/3/5/10: {recalls['1']:.3f}/{recalls['3']:.3f}/{recalls['5']:.3f}/{recalls['10']:.3f}",
        f"MRR: {retrieval['mrr']:.3f}; nDCG@10: {retrieval['ndcg_at_10']:.3f}; labeled hits@10: {retrieval['labeled_hit_at_10']}/{retrieval['scored_cases']}",
        f"Zero-result cases: {retrieval['zero_result_cases']}; evidence items: {retrieval['evidence_items']}",
        f"Direct-worker p50/p95: {retrieval['latency_p50_ms']:.3f}/{retrieval['latency_p95_ms']:.3f} ms",
        f"Reports: {mechanics['schema_valid']}/{mechanics['cases']} schema-valid; {valid_refs}/{refs} references valid; {mechanics['idempotent_replays']}/{mechanics['cases']} duplicate replays idempotent",
        f"Grounding probes: {sum(probes.values())}/{len(probes)} passed" if probes is not None else 'Grounding probes: not exercised (fewer than two evidence items)',
        '', '| Case | Category | Outcome | Relevant ranks | Evidence |', '| --- | --- | --- | --- | ---: |']
    for row in retrieval['cases']:
        ranks = ', '.join(map(str, row['scores']['relevant_ranks'])) if row['scores'] else 'unscored'
        lines.append(f"| {row['issue_id']} | {row['category']} | {row['outcome']} | {ranks or 'none'} | {row['evidence_count']} |")
    lines.extend(['', *report['limitations']])
    prefix.with_suffix('.md').write_text('\n'.join(lines) + '\n')
    print(f"Evaluation saved to {prefix}.json and {prefix}.md; snapshot={snapshot_id}")
    if (not probes or not all(probes.values()) or mechanics['schema_valid'] != mechanics['cases']
            or mechanics['provenance_valid'] != mechanics['cases'] or valid_refs != refs
            or mechanics['support_labels_valid'] != mechanics['cases']
            or mechanics['empty_evidence_abstentions'] != mechanics['empty_evidence_cases']
            or mechanics['idempotent_replays'] != mechanics['cases']):
        raise SystemExit('Evaluation produced a mechanical failure or an unexercised grounding probe.')


if __name__ == '__main__':
    main()
