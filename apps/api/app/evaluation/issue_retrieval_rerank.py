"""Re-score recorded, Git-verified retrieval candidates without touching PostgreSQL."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

from app.evaluation.compare_issue_retrieval import compare, markdown
from app.evaluation.git_source import GitSource
from app.evaluation.issue_report import score_retrieval, verify_dataset
from app.evaluation.issue_retrieval_candidates import protected_symbol_rerank
from app.evaluation.issue_retrieval_replay import _safe_output
from app.evaluation.retrieval import citation_valid, percentile


def main() -> None:
    dataset_path = Path('evaluation/issue-report-v1.json')
    baseline_path = Path('evaluation/5c1-baseline-eda70e4b43a14eb6.json')
    candidate_path = Path('evaluation/5c1-body-1fdf3b79925eaede.json')
    raw = dataset_path.read_bytes()
    dataset = json.loads(raw)
    baseline = json.loads(baseline_path.read_bytes())
    candidate = json.loads(candidate_path.read_bytes())
    compare(baseline, candidate)
    if hashlib.sha256(raw).hexdigest() != baseline['dataset_sha256']:
        raise ValueError('evaluation_dataset_mismatch')
    root = Path('../..').resolve()
    verified = verify_dataset(dataset, root)
    source = GitSource(root, dataset['commit_sha'], dataset['repository'])
    entries = {entry['path']: entry for entry in source.entries}
    cases = {case['issue_id']: case for case in dataset['cases']}
    old = {row['issue_id']: row for row in baseline['retrieval']['cases']}
    new = {row['issue_id']: row for row in candidate['retrieval']['cases']}
    if set(cases) != set(old) or set(cases) != set(new):
        raise ValueError('evaluation_case_set_mismatch')
    results, timings, cache = [], [], {}
    for case_id, case in cases.items():
        before, expanded = old[case_id], new[case_id]
        started = time.perf_counter()
        items = protected_symbol_rerank(case['title'], case['body'], before['evidence'], expanded['evidence'])
        timings.append((time.perf_counter() - started) * 1000)
        for item in items:
            entry = entries.get(item['path'])
            if not entry or not citation_valid(item, dataset['repository'], dataset['commit_sha']):
                raise ValueError('evaluation_citation_mismatch')
            if item['path'] not in cache:
                cache[item['path']] = source.blob('', dataset['repository'], entry['sha'], entry['size'])
            lines = cache[item['path']].decode('utf-8').splitlines()
            if not 1 <= item['start_line'] <= item['end_line'] <= len(lines):
                raise ValueError('evaluation_citation_mismatch')
        results.append({'issue_id': case_id, 'snapshot_id': candidate['snapshot_id'],
            'commit_sha': dataset['commit_sha'], 'items': items,
            'retrieval_status': 'ready' if items else expanded['retrieval_status'],
            # This is the measured expanded retrieval time; rerank time is reported separately.
            'latency_ms': expanded['latency_ms'], 'query_version': 'evaluation-protected-symbol',
            'query_input_truncated': expanded['query_input_truncated'], 'queries': expanded['queries']})
    retrieval = score_retrieval(dataset, results, snapshot_id=candidate['snapshot_id'])
    run_id = secrets.token_hex(8)
    implementation = dict(candidate['implementation_sha256'])
    implementation['app/evaluation/issue_retrieval_candidates.py'] = hashlib.sha256(
        Path('app/evaluation/issue_retrieval_candidates.py').read_bytes()).hexdigest()
    implementation['app/evaluation/issue_retrieval_rerank.py'] = hashlib.sha256(
        Path('app/evaluation/issue_retrieval_rerank.py').read_bytes()).hexdigest()
    report = {**candidate, 'version': '5c1-rerank-v1', 'run_id': run_id,
        'evaluated_at': datetime.now(timezone.utc).isoformat(), 'source_tree_sha': verified['source_tree_sha'],
        'implementation_sha256': implementation,
        'retrieval_configuration': {**candidate['retrieval_configuration'], 'strategy': 'evaluation-protected-symbol'},
        'execution': 'offline rerank of previously Git-verified PostgreSQL retrieval results',
        'latency_note': 'Retrieval latency is inherited from the body-query run and excludes reranking.',
        'rerank_latency_p50_ms': percentile(timings, .5), 'rerank_latency_p95_ms': percentile(timings, .95),
        'input_artifact_sha256': {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                                  for path in (baseline_path, candidate_path)},
        'citation_checks': {'locally_matched': retrieval['evidence_items'], 'mismatches': 0},
        'retrieval': retrieval, 'limitations': ['Reranked previously verified, bounded candidate sets; no new database query.',
            'Candidate selection used this small synthetic benchmark and may overfit.',
            'Retrieval latency is inherited from the body-query run; rerank time is separate.',
            'Incomplete relevance labels are not exhaustive; no root-cause accuracy is measured.']}
    prefix = Path(f'evaluation/5c1-protected-symbol-{run_id}')
    _safe_output(prefix.with_suffix('.json'), json.dumps(report, indent=2) + '\n')
    comparison = compare(baseline, report)
    comparison['latency_note'] = report['latency_note']
    comparison['rerank_latency_p50_ms'] = report['rerank_latency_p50_ms']
    comparison['rerank_latency_p95_ms'] = report['rerank_latency_p95_ms']
    comparison_prefix = Path(f'evaluation/5c1-comparison-protected-symbol-{run_id}')
    _safe_output(comparison_prefix.with_suffix('.json'), json.dumps(comparison, indent=2) + '\n')
    _safe_output(comparison_prefix.with_suffix('.md'), markdown(comparison))
    print(markdown(comparison))
    print(f"Rerank-only p50/p95: {report['rerank_latency_p50_ms']:.3f}/{report['rerank_latency_p95_ms']:.3f} ms")
    print(f'Results saved: {prefix}.json and {comparison_prefix}.json/.md')


if __name__ == '__main__':
    os.environ.setdefault('GIT_TERMINAL_PROMPT', '0')
    main()
