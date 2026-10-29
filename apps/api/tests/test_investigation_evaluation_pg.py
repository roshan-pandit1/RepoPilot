"""Actual PostgreSQL retrieval over a disposable snapshot reconstructed from Git objects."""
import hashlib
import json
import os
import statistics
import time
from pathlib import Path

import pytest

from app.domain.models import CodeChunk, IndexedFile, Repository
from app.evaluation.git_source import GitSource
from app.evaluation.retrieval import citation_valid, match_label, percentile
from app.modules.ingestion.code_collect import collect_source
from app.modules.ingestion.code_persistence import publish_snapshot
from app.modules.ingestion.code_snapshot import plan_snapshot
from app.workers.tasks import process_investigation
from test_auth_enrollment import csrf, github_auth as github_auth
from test_issue_context import STAMP, setup_issue


def test_evidence_quality_against_git_commit_postgres(client, factory, github_auth):
    if factory.kw['bind'].dialect.name != 'postgresql':
        pytest.skip('PostgreSQL full-text search is required')
    root = Path(__file__).resolve().parents[3]
    dataset_path = root / 'apps/api/evaluation/investigation-evidence-v1.json'
    dataset_bytes = dataset_path.read_bytes()
    dataset = json.loads(dataset_bytes)
    setup_issue(client, github_auth)
    source = GitSource(root, dataset['source_commit'], 'alice/public')
    collection = collect_source(source, '', 'alice/public', plan_snapshot(source, '', 'alice/public'))
    with factory.begin() as db:
        repo = db.get(Repository, 902)
        snapshot = publish_snapshot(db, repo, plan_snapshot(source, '', 'alice/public'), collection)
        snapshot_id = snapshot.id
        tenant = repo.tenant_id
    entries = {entry['path']: entry for entry in source.entries}
    collected = [{'path': f.path, 'symbol': c.symbol, 'start_line': c.start_line, 'end_line': c.end_line}
                 for f in collection.files for c in f.chunks if c.text.strip()]
    assert all(any(match_label(row, label) for row in collected)
               for case in dataset['cases'] for label in case['labels'])
    rows, invalid = [], 0
    for index, case in enumerate(dataset['cases']):
        number = 300 + index
        github_auth.issue = lambda token, name, num, case=case: {
            'id': 99000 + num, 'number': num, 'title': case['title'], 'body': case['body'],
            'state': 'open', 'created_at': STAMP, 'updated_at': STAMP, 'comments': 0, 'labels': []}
        github_auth.issue_comments = lambda *args: []
        response = client.post(f'/v1/repositories/902/issues/{number}/investigations', headers=csrf(client))
        assert response.status_code == 202
        job = response.json()['job_id']
        start = time.perf_counter()
        process_investigation(job, factory, github_auth)
        elapsed = (time.perf_counter() - start) * 1000
        status = client.get(f'/v1/repositories/902/investigations/{job}').json()
        assert status['status'] == 'completed' and status['snapshot_id'] == snapshot_id
        evidence_response = client.get(f'/v1/repositories/902/investigations/{job}/evidence')
        assert evidence_response.status_code == 200
        evidence = evidence_response.json()
        assert evidence['commit_sha'] == dataset['source_commit'] and evidence['snapshot_id'] == snapshot_id
        assert len(evidence['items']) <= 20
        assert [item['rank'] for item in evidence['items']] == list(range(1, len(evidence['items']) + 1))
        assert len({item['chunk_id'] for item in evidence['items']}) == len(evidence['items'])
        hits = [i + 1 for i, item in enumerate(evidence['items'][:10])
                if any(match_label(item, label) for label in case['labels'])]
        for item in evidence['items']:
            entry = entries[item['path']]
            source_bytes = source.blob('', 'alice/public', entry['sha'], entry['size'])
            lines = source_bytes.decode().splitlines(keepends=True)
            with factory() as db:
                chunk = db.get(CodeChunk, item['chunk_id'])
                file = db.get(IndexedFile, chunk.file_id)
                good = (citation_valid(item, 'alice/public', dataset['source_commit'])
                        and file.path == item['path'] and chunk.symbol == item['symbol']
                        and chunk.start_line == item['start_line'] and chunk.end_line == item['end_line']
                        and file.snapshot_id == snapshot_id and file.tenant_id == tenant
                        and chunk.source_text == ''.join(lines[item['start_line'] - 1:item['end_line']])
                        and 1 <= item['start_line'] <= item['end_line'] <= len(lines))
            invalid += not good
        if case['kind'] == 'no_query':
            assert evidence['retrieval_status'] == 'no_usable_queries' and not evidence['items']
        if case['kind'] == 'no_match':
            assert evidence['retrieval_status'] == 'no_matches' and not evidence['items']
        rows.append({'id': case['id'], 'kind': case['kind'], 'relevant_ranks_at_10': hits,
                     'evidence_count': evidence['evidence_count'], 'retrieval_status': evidence['retrieval_status'],
                     'latency_ms': round(elapsed, 3)})
    assert invalid == 0
    # The reviewed exact-function case must retrieve its target at rank one.
    assert rows[0]['id'] == 'identifier' and rows[0]['relevant_ranks_at_10'] == [1]
    # Exercise the actual shared PostgreSQL expression with an injection-shaped bound value.
    from app.modules.investigation.query_builder import RetrievalQuery
    from app.modules.investigation.retrieval import retrieve_candidates
    retrieve_candidates(factory, queries=[RetrievalQuery('injection', "'; DROP TABLE repositories; --")],
        snapshot_id=snapshot_id, repository_id=902, tenant_id=tenant, commit=dataset['source_commit'],
        full_name='alice/public', per_query_limit=10, evidence_limit=20)
    with factory() as db:
        assert db.get(Repository, 902) is not None
    positive = [row for row in rows if row['kind'] == 'positive']
    report = {'dataset': 'investigation-evidence-v1', 'dataset_sha256': hashlib.sha256(dataset_bytes).hexdigest(),
              'source_commit': dataset['source_commit'], 'snapshot_id': snapshot_id, 'files': len(collection.files),
              'chunks': len(collected), 'mode': 'keyword', 'execution': 'PostgreSQL and direct worker with mocked GitHub',
              'positive_cases': len(positive), 'positive_hit_at_10': sum(bool(row['relevant_ranks_at_10']) for row in positive),
              'negative_or_no_query_cases': len(rows) - len(positive), 'citation_chunk_mismatches': invalid,
              'evidence_count': sum(row['evidence_count'] for row in rows),
              'latency_p50_ms': statistics.median(row['latency_ms'] for row in rows),
              'latency_p95_ms': percentile([row['latency_ms'] for row in rows], .95), 'cases': rows,
              'limitations': 'Synthetic cases and incomplete labels; Git objects checked locally, remote citation resolution not checked; direct worker, no real Celery or semantic quality.'}
    prefix = os.environ.get('REPOPILOT_4C_EVAL_PREFIX')
    if prefix:
        output = Path(prefix)
        output.with_suffix('.json').write_text(json.dumps(report, indent=2) + '\n')
        lines = ['# Investigation evidence evaluation', '', f"Source commit: {report['source_commit']}",
                 f"Positive labeled top-10 hits: {report['positive_hit_at_10']} / {report['positive_cases']}",
                 f"Evidence items: {report['evidence_count']}; local Git chunk mismatches: {invalid}",
                 f"Direct-worker latency p50/p95: {report['latency_p50_ms']:.3f}/{report['latency_p95_ms']:.3f} ms",
                 '', '| Case | Relevant ranks | Evidence | Status |', '| --- | --- | ---: | --- |']
        lines += [f"| {row['id']} | {', '.join(map(str, row['relevant_ranks_at_10'])) or 'none'} | {row['evidence_count']} | {row['retrieval_status']} |" for row in rows]
        output.with_suffix('.md').write_text('\n'.join(lines) + '\n\n' + report['limitations'] + '\n')
    print('4C evaluation: ' + json.dumps(report))
