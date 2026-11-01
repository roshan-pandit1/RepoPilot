"""Compare source- and snapshot-matched issue-retrieval reports."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def compare(before: dict, after: dict) -> dict:
    """Compare the existing scorer's output without treating unlabeled cases as negatives."""
    for key in ('dataset', 'dataset_sha256', 'source_commit', 'source_tree_sha', 'snapshot_id', 'database'):
        if before.get(key) is None or before.get(key) != after.get(key):
            raise ValueError(f'evaluation_provenance_mismatch:{key}')
    limits = ('query_limit', 'per_query', 'evidence_limit', 'statement_timeout_seconds')
    a_config, b_config = before['retrieval_configuration'], after['retrieval_configuration']
    if any(a_config.get(k) is None or a_config.get(k) != b_config.get(k) for k in limits):
        raise ValueError('evaluation_budget_mismatch')
    for report in (before, after):
        check = report['citation_checks']
        if check['mismatches'] != 0 or check['locally_matched'] != report['retrieval']['evidence_items']:
            raise ValueError('evaluation_citation_mismatch')
    a, b = before['retrieval'], after['retrieval']
    old = {row['issue_id']: row for row in a['cases']}
    new = {row['issue_id']: row for row in b['cases']}
    if (len(old) != len(a['cases']) or len(new) != len(b['cases']) or set(old) != set(new)
            or any((old[key]['scored'], old[key]['category'], old[key]['answerability'])
                   != (new[key]['scored'], new[key]['category'], new[key]['answerability']) for key in old)):
        raise ValueError('evaluation_case_set_mismatch')
    keys = ('recall', 'mrr', 'ndcg_at_10', 'labeled_hit_at_10', 'zero_result_cases',
            'evidence_items', 'latency_p50_ms', 'latency_p95_ms')
    return {'dataset': before['dataset'], 'dataset_sha256': before['dataset_sha256'],
        'source_commit': before['source_commit'], 'source_tree_sha': before['source_tree_sha'],
        'snapshot_id': before['snapshot_id'], 'database': before['database'],
        'before_run': before['run_id'], 'after_run': after['run_id'],
        'implementation_changes': sorted(key for key in set(before.get('implementation_sha256', {}))
            | set(after.get('implementation_sha256', {}))
            if before.get('implementation_sha256', {}).get(key) != after.get('implementation_sha256', {}).get(key)),
        'before_strategy': a_config['strategy'], 'after_strategy': b_config['strategy'],
        'before': {key: a[key] for key in keys}, 'after': {key: b[key] for key in keys},
        'cases': [{'issue_id': key, 'category': old[key]['category'], 'scored': old[key]['scored'],
                   'before_ranks': old[key]['scores']['relevant_ranks'] if old[key]['scores'] else None,
                   'after_ranks': new[key]['scores']['relevant_ranks'] if new[key]['scores'] else None,
                   'before_evidence': old[key]['evidence_count'], 'after_evidence': new[key]['evidence_count']}
                  for key in old]}


def markdown(report: dict) -> str:
    before, after = report['before'], report['after']
    lines = ['# Sprint 5C1 issue-retrieval comparison', '',
        f"Dataset: {report['dataset']} ({report['dataset_sha256']})",
        f"Commit: {report['source_commit']}; snapshot: {report['snapshot_id']}; database: {report['database']}",
        f"Runs: {report['before_run']} ({report['before_strategy']}) and "
        f"{report['after_run']} ({report['after_strategy']})", '',
        'Implementation files with different or newly recorded hashes: '
        + (', '.join(report['implementation_changes']) or 'none'), '',
        '| Metric | Baseline | Candidate |', '| --- | ---: | ---: |']
    for cutoff in (1, 3, 5, 10):
        lines.append(f"| Recall@{cutoff} | {before['recall'][str(cutoff)]:.4f} | {after['recall'][str(cutoff)]:.4f} |")
    for label, key in (('MRR', 'mrr'), ('nDCG@10', 'ndcg_at_10'), ('Labeled hits@10', 'labeled_hit_at_10'),
                       ('Zero-result cases', 'zero_result_cases'), ('Evidence items', 'evidence_items'),
                       ('Direct retrieval p50 ms', 'latency_p50_ms'), ('Direct retrieval p95 ms', 'latency_p95_ms')):
        lines.append(f'| {label} | {before[key]:.4f} | {after[key]:.4f} |')
    lines += ['', '| Case | Baseline labeled ranks | Candidate labeled ranks |', '| --- | --- | --- |']
    for row in report['cases']:
        a = ', '.join(map(str, row['before_ranks'])) or 'none' if row['before_ranks'] is not None else 'unscored'
        b = ', '.join(map(str, row['after_ranks'])) or 'none' if row['after_ranks'] is not None else 'unscored'
        lines.append(f"| {row['issue_id']} | {a} | {b} |")
    lines += ['', 'Incomplete synthetic labels; unlabeled candidates are not confirmed irrelevant.',
              'Latency measures direct retrieval and is not an end-to-end or load benchmark.']
    if report.get('latency_note'):
        lines.append(report['latency_note'])
    return '\n'.join(lines) + '\n'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = compare(json.loads(args.before.read_bytes()), json.loads(args.after.read_bytes()))
    for suffix, content in (('.json', json.dumps(result, indent=2) + '\n'), ('.md', markdown(result))):
        with args.output.with_suffix(suffix).open('x', encoding='utf-8') as stream:
            stream.write(content)


if __name__ == '__main__':
    main()
