"""Read-only replay of the existing 4F synthetic snapshot; never creates jobs or snapshots."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.domain.models import CodeChunk, CodeSnapshot, IndexedFile, Repository
from app.evaluation.git_source import GitSource
from app.evaluation.issue_report import score_retrieval, verify_dataset
from app.evaluation.issue_retrieval_candidates import STRATEGIES, candidate_queries
from app.modules.ingestion.citations import github_citation
from app.modules.investigation.query_builder import build_queries_for_version
from app.modules.investigation.retrieval import fingerprint_chunk, retrieve_candidates

COMMIT = '30705da4c044192cab4ac207e253ab8e8a1bd100'
DATASET_HASH = '416cbf9e46b9399cf78d118f581a882d16cf512da439d352d3af29674c447bf6'
DATABASE = 'repopilot_4f_disposable_4f762b71ae8d9569'
SNAPSHOT = '1a8e0d9e-1cf1-4e0a-9cac-f8ced23f1694'
REPOSITORY_ID = 902


def replay_queries(strategy: str, title: str, body: str):
    """Use the worker's versioned query builder when measuring production behavior."""
    if strategy == 'production-v2':
        return build_queries_for_version('terms-v2', title, body, [], 3)
    return candidate_queries(strategy, title, body, [], 3)


def fixture_metadata(suffix: str, report: dict):
    """Validate a newly created 4F fixture before opening its database."""
    if not re.fullmatch(r'[0-9a-f]{16}', suffix):
        raise ValueError('invalid_fixture_suffix')
    database = f'repopilot_4f_disposable_{suffix}'
    if (report.get('database') != database or report.get('dataset_sha256') != DATASET_HASH
            or report.get('source_commit') != COMMIT or report.get('migration') != '0013'):
        raise ValueError('fixture_provenance_mismatch')
    snapshot_id = report.get('snapshot_id', '')
    if not isinstance(snapshot_id, str) or not re.fullmatch(
            r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', snapshot_id):
        raise ValueError('invalid_fixture_snapshot')
    values = report.get('snapshot_counts', {})
    counts = tuple(values.get(key) for key in ('files', 'chunks', 'skipped_files'))
    if any(type(value) is not int or value < 0 for value in counts):
        raise ValueError('invalid_fixture_counts')
    return database, snapshot_id, counts


def assert_readonly_sql(statement: str) -> None:
    """Only statements needed by this replay are allowed through SQLAlchemy."""
    normalized = ' '.join(statement.lower().split())
    if (not (normalized.startswith('select ') or normalized.startswith('show ')
             or normalized == "set local statement_timeout = '3s'")
            or re.search(r'\b(for\s+(?:update|share)|insert|update|delete|create|alter|drop|truncate)\b', normalized)):
        raise RuntimeError('read_only_replay_statement_rejected')


def _safe_output(path: Path, data: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        stream.write(data)


def main() -> None:
    if not __debug__:
        raise SystemExit('Optimized Python disables evaluation safeguards.')
    run_id = os.environ.get('REPOPILOT_5C1_RUN_ID', '')
    if not re.fullmatch(r'[0-9a-f]{16}', run_id):
        raise SystemExit('Invalid run identifier.')
    strategy = os.environ.get('REPOPILOT_5C1_STRATEGY', 'baseline')
    if strategy not in (*STRATEGIES, 'production-v2'):
        raise SystemExit('Invalid retrieval strategy.')
    database, snapshot_id, revision = DATABASE, SNAPSHOT, '0009'
    counts = (104, 889, 1)
    suffix = os.environ.get('REPOPILOT_5C1_FIXTURE_SUFFIX', '')
    if suffix:
        if not re.fullmatch(r'[0-9a-f]{16}', suffix):
            raise SystemExit('Invalid fixture suffix.')
        report = json.loads(Path(f'evaluation/4f-issue-report-v1-{suffix}.json').read_bytes())
        database, snapshot_id, counts = fixture_metadata(suffix, report)
        revision = '0013'
    url = make_url(os.environ['DATABASE_URL'])
    if (url.get_backend_name() != 'postgresql' or url.host != '127.0.0.1' or not url.port
            or url.username != 'repopilot_fixture' or url.database != database or url.query):
        raise SystemExit('Refusing unexpected database target.')
    dataset_path = Path('evaluation/issue-report-v1.json')
    raw = dataset_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != DATASET_HASH:
        raise SystemExit('Dataset hash mismatch.')
    dataset = json.loads(raw)
    root = Path('../..').resolve()
    provenance = verify_dataset(dataset, root)
    if dataset['commit_sha'] != COMMIT or provenance['commit_sha'] != COMMIT:
        raise SystemExit('Source commit mismatch.')
    if suffix and report.get('source_tree_sha') != provenance['source_tree_sha']:
        raise SystemExit('Fixture source tree mismatch.')
    source = GitSource(root, COMMIT, dataset['repository'])
    entries = {entry['path']: entry for entry in source.entries}
    engine = create_engine(url, hide_parameters=True,
        connect_args={'options': '-c default_transaction_read_only=on -c statement_timeout=3000'})

    @event.listens_for(engine, 'before_cursor_execute')
    def only_read(_conn, _cursor, statement, _parameters, _context, _many):
        assert_readonly_sql(statement)

    with engine.connect() as conn:
        if (conn.execute(text('show transaction_read_only')).scalar_one() != 'on'
                or conn.execute(text('select current_database()')).scalar_one() != database
                or conn.execute(text('select version_num from alembic_version')).scalar_one() != revision):
            raise SystemExit('Unexpected database, revision or read-only state.')
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        snapshot = db.get(CodeSnapshot, snapshot_id)
        repo = db.get(Repository, REPOSITORY_ID)
        if (not snapshot or not repo or not snapshot.published or not repo.enabled
                or snapshot.repository_id != REPOSITORY_ID or snapshot.tenant_id != repo.tenant_id
                or snapshot.commit_sha != COMMIT or repo.full_name != dataset['repository']
                or (snapshot.file_count, snapshot.chunk_count, snapshot.skipped_count) != counts):
            raise SystemExit('Retained snapshot does not match the recorded 4F fixture.')
        tenant_id = snapshot.tenant_id

    results, cache = [], {}
    for case in dataset['cases']:
        queries = replay_queries(strategy, case['title'], case['body'][:4000])
        started = time.perf_counter()
        candidates = retrieve_candidates(factory, queries=queries, snapshot_id=snapshot_id,
            repository_id=REPOSITORY_ID, tenant_id=tenant_id, commit=COMMIT,
            full_name=dataset['repository'], per_query_limit=10, evidence_limit=20,
            ranking_context=(case['title'], case['body'][:4000]) if strategy == 'production-v2' else None)
        elapsed = (time.perf_counter() - started) * 1000
        items = []
        with factory() as db:
            for rank, candidate in enumerate(candidates, 1):
                chunk = db.get(CodeChunk, candidate.chunk_id)
                file = db.get(IndexedFile, candidate.file_id)
                if (not chunk or not file or chunk.file_id != file.id or file.snapshot_id != snapshot_id
                        or chunk.tenant_id != tenant_id or file.tenant_id != tenant_id
                        or chunk.repository_id != REPOSITORY_ID or file.repository_id != REPOSITORY_ID
                        or candidate.chunk_fingerprint != fingerprint_chunk(chunk, file)
                        or (file.path, chunk.symbol, chunk.start_line, chunk.end_line)
                        != (candidate.path, candidate.symbol, candidate.start_line, candidate.end_line)):
                    raise SystemExit('Snapshot evidence ownership or fingerprint mismatch.')
                entry = entries.get(file.path)
                if not entry:
                    raise SystemExit('Evidence path absent from committed Git tree.')
                if file.path not in cache:
                    cache[file.path] = source.blob('', dataset['repository'], entry['sha'], entry['size'])
                source_bytes = cache[file.path]
                lines = source_bytes.decode('utf-8').splitlines(keepends=True)
                if (hashlib.sha256(source_bytes).hexdigest() != file.content_hash
                        or not 1 <= chunk.start_line <= chunk.end_line <= len(lines)
                        or chunk.source_text != ''.join(lines[chunk.start_line - 1:chunk.end_line])):
                    raise SystemExit('Evidence does not match committed Git source.')
                items.append({'chunk_id': chunk.id, 'rank': rank, 'query_id': candidate.query_id,
                    'query_hash': candidate.query_hash, 'query_rank': candidate.query_rank, 'method': 'keyword',
                    'path': file.path, 'symbol': chunk.symbol, 'start_line': chunk.start_line,
                    'end_line': chunk.end_line, 'commit_sha': COMMIT,
                    'url': github_citation(dataset['repository'], COMMIT, file.path, chunk.start_line, chunk.end_line)})
        results.append({'issue_id': case['issue_id'], 'snapshot_id': snapshot_id, 'commit_sha': COMMIT,
            'retrieval_status': 'ready' if items else ('no_matches' if queries else 'no_usable_queries'),
            'items': items, 'latency_ms': round(elapsed, 3),
            'query_version': ('terms-v1' if strategy == 'baseline' else 'terms-v2' if strategy == 'production-v2'
                              else f'evaluation-{strategy}'),
            'query_input_truncated': len(case['body']) > 4000,
            'queries': [{'id': q.id, 'sha256': hashlib.sha256(q.text.encode()).hexdigest()} for q in queries]})
    retrieval = score_retrieval(dataset, results, snapshot_id=snapshot_id)
    files = ('app/modules/investigation/query_builder.py', 'app/modules/investigation/retrieval.py',
             'app/modules/ingestion/keyword_search.py', 'app/evaluation/retrieval.py',
             'app/evaluation/issue_report.py', 'app/evaluation/issue_retrieval_replay.py',
             'app/evaluation/issue_retrieval_candidates.py', 'app/modules/investigation/ranking.py')
    implementation = {name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in files}
    report = {'version': '5c1-baseline-v1', 'run_id': run_id, 'dataset': dataset['version'],
        'dataset_sha256': DATASET_HASH, 'source_commit': COMMIT, 'source_tree_sha': provenance['source_tree_sha'],
        'snapshot_id': snapshot_id, 'database': database, 'migration': revision,
        'evaluated_at': datetime.now(timezone.utc).isoformat(), 'implementation_sha256': implementation,
        'retrieval_configuration': {'strategy': ('terms-v1' if strategy == 'baseline' else
                                                  'terms-v2' if strategy == 'production-v2' else f'evaluation-{strategy}'),
                                    'query_limit': 3, 'per_query': 10,
                                    'evidence_limit': 20, 'statement_timeout_seconds': 3},
        'execution': 'read-only retained disposable PostgreSQL snapshot; direct retrieval; no API or worker',
        'citation_checks': {'locally_matched': retrieval['evidence_items'], 'mismatches': 0},
        'retrieval': retrieval, 'limitations': ['Incomplete synthetic labels; unlabeled results are not judged.',
            'Latency measures direct retrieval only; it is not an end-to-end or load benchmark.',
            'Authentication and worker behavior require separate regression tests.']}
    recalls = ' / '.join(f"{retrieval['recall'][str(k)]:.4f}" for k in (1, 3, 5, 10))
    lines = [f'# Sprint 5C1 {strategy} retrieval', '', f'Run: {run_id}; database: {database}; snapshot: {snapshot_id}',
        f"Dataset: {dataset['version']} ({DATASET_HASH}); commit: {COMMIT}; Git tree: {provenance['source_tree_sha']}",
        f'Recall@1/3/5/10: {recalls}',
        f"MRR: {retrieval['mrr']:.4f}; nDCG@10: {retrieval['ndcg_at_10']:.4f}; "
        f"labeled hits@10: {retrieval['labeled_hit_at_10']}/{retrieval['scored_cases']}",
        f"Direct retrieval p50/p95: {retrieval['latency_p50_ms']:.3f}/{retrieval['latency_p95_ms']:.3f} ms",
        f"Locally verified citations: {retrieval['evidence_items']}/{retrieval['evidence_items']}", '',
        '| Case | Outcome | Labeled ranks |', '| --- | --- | --- |']
    lines.extend(f"| {row['issue_id']} | {row['outcome']} | "
        f"{', '.join(map(str, row['scores']['relevant_ranks'])) if row['scores'] else 'unscored'} |"
        for row in retrieval['cases'])
    lines += ['', *report['limitations']]
    prefix = Path('evaluation') / f'5c1-{strategy}-{run_id}'
    _safe_output(prefix.with_suffix('.json'), json.dumps(report, indent=2) + '\n')
    _safe_output(prefix.with_suffix('.md'), '\n'.join(lines) + '\n')
    print('\n'.join(lines[:8]))
    print(f'Read-only {strategy} evaluation saved: {prefix}.json and {prefix}.md')


if __name__ == '__main__':
    main()
