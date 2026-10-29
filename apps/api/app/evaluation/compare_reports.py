"""Compare two sanitized, commit-matched retrieval evaluation reports."""
import argparse
import json
from pathlib import Path


def compare(before, after):
    if (before['repository'], before['dataset_commit']) != (after['repository'], after['dataset_commit']):
        raise ValueError('Repository or commit mismatch')
    if before['configuration'].get('limit') != after['configuration'].get('limit'):
        raise ValueError('Result limit mismatch')
    for key in ('provider', 'model', 'dimensions', 'embedding_ready'):
        if before['configuration'].get(key) != after['configuration'].get(key):
            raise ValueError('Embedding configuration mismatch')
    comparisons = {}
    for mode in ('keyword', 'semantic', 'hybrid'):
        old, new = before['modes'][mode], after['modes'][mode]
        old_rows = {row['id']: row for row in old['queries']}
        new_rows = {row['id']: row for row in new['queries']}
        if set(old_rows) != set(new_rows) or len(old_rows) != len(old['queries']) or len(new_rows) != len(new['queries']):
            raise ValueError('Question sets differ or have duplicate IDs')
        if any(old_rows[key]['question'] != new_rows[key]['question'] for key in old_rows):
            raise ValueError('Question texts differ')
        comparisons[mode] = {'before': {**{key: old[key] for key in ('recall', 'mrr', 'ndcg_at_10', 'no_relevant', 'fallback_count', 'invalid_citations', 'total_results', 'latency_p50_ms', 'latency_p95_ms')}, 'zero_results': sum(row['returned'] == 0 for row in old['queries'])},
                             'after': {**{key: new[key] for key in ('recall', 'mrr', 'ndcg_at_10', 'no_relevant', 'fallback_count', 'invalid_citations', 'total_results', 'latency_p50_ms', 'latency_p95_ms')}, 'zero_results': sum(row['returned'] == 0 for row in new['queries'])},
                             'queries': [{'id': key, 'before_ranks': old_rows[key]['relevant_ranks'],
                                          'after_ranks': new_rows[key]['relevant_ranks'],
                                          'before_returned': old_rows[key]['returned'],
                                          'after_returned': new_rows[key]['returned']}
                                         for key in old_rows]}
    return {'repository': before['repository'], 'commit_sha': before['dataset_commit'], 'modes': comparisons}


def markdown(result):
    lines = ['# C2 retrieval before and after', '', f"Repository: {result['repository']}; commit: {result['commit_sha']}",
             '', 'Same 20 questions, incomplete definition-anchor labels, and limit 10. Fake semantic and hybrid results are **MECHANICAL TEST ONLY**. Real semantic quality is not measured.',
             'Latencies include authorization and network time; a single run of 20 queries per mode is not a load benchmark.', '']
    for mode, data in result['modes'].items():
        lines += [f'## {mode}', '', '| Metric | Before | After |', '| --- | ---: | ---: |']
        for k in (1, 3, 5, 10):
            lines.append(f"| Recall@{k} | {data['before']['recall'][str(k)]:.3f} | {data['after']['recall'][str(k)]:.3f} |")
        for label, key in [('MRR', 'mrr'), ('nDCG@10', 'ndcg_at_10'), ('Queries with no labeled result', 'no_relevant'), ('Queries with zero results', 'zero_results'), ('Fallbacks', 'fallback_count'), ('Results returned', 'total_results'), ('Invalid citations', 'invalid_citations'), ('p50 ms', 'latency_p50_ms'), ('p95 ms', 'latency_p95_ms')]:
            def fmt(value):
                return str(value) if isinstance(value, int) else f'{value:.3f}'
            lines.append(f"| {label} | {fmt(data['before'][key])} | {fmt(data['after'][key])} |")
        lines += ['', '| Query | Before labeled ranks | After labeled ranks | Before returned | After returned |', '| --- | --- | --- | ---: | ---: |']
        for row in data['queries']:
            a = ', '.join(map(str, row['before_ranks'])) or 'none'
            b = ', '.join(map(str, row['after_ranks'])) or 'none'
            lines.append(f"| {row['id']} | {a} | {b} | {row['before_returned']} | {row['after_returned']} |")
        lines.append('')
    if result['modes']['keyword']['before']['total_results'] == 0:
        lines.append('Before keyword returned zero citations, so its zero invalid count did not validate any citations.')
    lines += ['Citation validation checks URL structure, commit, path and inclusive line fragment; it does not independently open every GitHub link.',
              'Authorization evidence and test counts are recorded separately in docs/verification.md.',
              'Labels are incomplete; the pinned commit predates the indexing, chunking, citation and embedding modules.']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = compare(json.loads(args.before.read_text()), json.loads(args.after.read_text()))
    args.output.with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
    args.output.with_suffix('.md').write_text(markdown(result))


if __name__ == '__main__':
    main()
