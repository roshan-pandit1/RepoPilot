"""Offline CIE evaluation of the retained Git-verified 5C1 candidate set."""
import argparse
import hashlib
import json
import re
import secrets
import time
import tracemalloc
from pathlib import Path

from app.evaluation.compare_issue_retrieval import compare, markdown
from app.evaluation.git_source import GitSource
from app.evaluation.issue_report import score_retrieval, verify_dataset
from app.evaluation.issue_retrieval_replay import COMMIT, DATASET_HASH, _safe_output
from app.evaluation.retrieval import citation_valid, percentile
from app.modules.ingestion.code_selection import contains_sensitive_source
from app.modules.investigation.code_intelligence import analyze, run_bounded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', default='evaluation/5c1-production-v2-3d44ea7dbd159dd9.json')
    args = parser.parse_args()
    dataset_path = Path('evaluation/issue-report-v1.json')
    baseline_path = Path(args.baseline)
    if baseline_path.parent != Path('evaluation') or not re.fullmatch(r'5c1-production-v2-[0-9a-f]{16}\.json', baseline_path.name):
        raise ValueError('invalid_baseline_path')
    raw, prior_raw = dataset_path.read_bytes(), baseline_path.read_bytes()
    dataset, baseline = json.loads(raw), json.loads(prior_raw)
    if (hashlib.sha256(raw).hexdigest() != DATASET_HASH or dataset['commit_sha'] != COMMIT
            or dataset['repository'] != 'roshan-pandit1/RepoPilot'
            or baseline['dataset_sha256'] != DATASET_HASH or baseline['source_commit'] != COMMIT
            or baseline['retrieval_configuration']['strategy'] != 'terms-v2'
            or baseline['citation_checks']['mismatches'] != 0
            or baseline['citation_checks']['locally_matched'] != baseline['retrieval']['evidence_items']):
        raise ValueError('baseline_provenance_mismatch')
    root = Path('../..').resolve()
    provenance = verify_dataset(dataset, root)
    if provenance['source_tree_sha'] != baseline['source_tree_sha']:
        raise ValueError('source_tree_mismatch')
    source = GitSource(root, COMMIT, dataset['repository'])
    entries = {entry['path']: entry for entry in source.entries}
    cases = {case['issue_id']: case for case in dataset['cases']}
    rows = baseline['retrieval']['cases']
    if set(cases) != {row['issue_id'] for row in rows} or len(rows) != len(cases):
        raise ValueError('case_set_mismatch')
    cache, results, timings, coverage, case_stats, max_input = {}, [], [], [], [], None
    for row in rows:
        case, evidence, chunks = cases[row['issue_id']], row['evidence'], []
        for item in evidence:
            entry = entries.get(item['path'])
            if not entry or not citation_valid(item, dataset['repository'], COMMIT):
                raise ValueError('invalid_citation')
            if item['path'] not in cache:
                cache[item['path']] = source.blob('', dataset['repository'], entry['sha'], entry['size']).decode('utf-8').splitlines(keepends=True)
            lines = cache[item['path']]
            if not 1 <= item['start_line'] <= item['end_line'] <= len(lines):
                raise ValueError('invalid_citation_range')
            text = ''.join(lines[item['start_line'] - 1:item['end_line']])
            if contains_sensitive_source(text):
                raise ValueError('screened_source')
            chunks.append({**item, 'source': text})
        started = time.perf_counter()
        output = analyze(case['title'], case['body'], chunks)
        timings.append((time.perf_counter() - started) * 1000)
        coverage.append(not output['abstained'])
        lookup = {item['chunk_id']: item for item in evidence}
        ranked = [{**lookup[x['chunk_id']], 'rank': rank} for rank, x in enumerate(output['candidate_ranking'], 1)]
        if set(lookup) != {item['chunk_id'] for item in ranked}:
            raise ValueError('candidate_set_changed')
        results.append({'issue_id': row['issue_id'], 'snapshot_id': baseline['snapshot_id'],
            'commit_sha': COMMIT, 'items': ranked, 'retrieval_status': row['retrieval_status'],
            'latency_ms': row['latency_ms'], 'query_version': 'cie-v1-offline',
            'query_input_truncated': row['query_input_truncated'], 'queries': row['queries']})
        case_stats.append({'issue_id': row['issue_id'], 'findings': len(output['findings']),
                           'abstained': output['abstained'], 'bytes_parsed': output['bytes_parsed'],
                           'positions_changed': sum(before['chunk_id'] != after['chunk_id']
                                                    for before, after in zip(evidence, ranked, strict=True))})
        if max_input is None or sum(len(x['source']) for x in chunks) > max_input[0]:
            max_input = (sum(len(x['source']) for x in chunks), case, chunks)
    retrieval = score_retrieval(dataset, results, snapshot_id=baseline['snapshot_id'])
    tracemalloc.start()
    analyze(max_input[1]['title'], max_input[1]['body'], max_input[2])
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    started = time.perf_counter()
    run_bounded(max_input[1]['title'], max_input[1]['body'], max_input[2])
    bounded_sample_ms = (time.perf_counter() - started) * 1000
    run = secrets.token_hex(8)
    engine_hash = hashlib.sha256(Path('app/modules/investigation/code_intelligence.py').read_bytes()).hexdigest()
    candidate = {**baseline, 'run_id': run, 'retrieval': retrieval,
                 'implementation_sha256': {**baseline['implementation_sha256'],
                                           'app/modules/investigation/code_intelligence.py': engine_hash},
                 'retrieval_configuration': {**baseline['retrieval_configuration'], 'strategy': 'cie-v1-offline'},
                 'citation_checks': {'locally_matched': retrieval['evidence_items'], 'mismatches': 0}}
    comparison = compare(baseline, candidate)
    comparison['latency_note'] = 'Retrieval latency is inherited from the earlier terms-v2 run; CIE analysis is timed separately.'
    report = {'run_id': run, 'baseline_sha256': hashlib.sha256(prior_raw).hexdigest(),
        'engine_sha256': engine_hash,
        'dataset_sha256': DATASET_HASH, 'commit': COMMIT, 'snapshot_id': baseline['snapshot_id'],
        'execution': 'offline rerank of saved Git-verified evidence using pinned local Git blobs; no database replay',
        'analysis_p50_ms': percentile(timings, .5), 'analysis_p95_ms': percentile(timings, .95),
        'sample_peak_python_bytes': peak, 'bounded_process_sample_ms': bounded_sample_ms,
        'cases_with_findings': sum(coverage), 'cases': len(coverage),
        'abstention_rate': (len(coverage) - sum(coverage)) / len(coverage),
        'case_stats': case_stats, 'comparison': comparison}
    prefix = Path(f'evaluation/cie-v1-offline-{run}')
    _safe_output(prefix.with_suffix('.json'), json.dumps(report, indent=2) + '\n')
    _safe_output(prefix.with_suffix('.md'), markdown(comparison) + '\n' +
        f"Offline CIE analysis p50/p95: {report['analysis_p50_ms']:.3f}/{report['analysis_p95_ms']:.3f} ms.\n" +
        f"One bounded-process sample: {bounded_sample_ms:.3f} ms.\n" +
        f"Findings: {sum(coverage)}/{len(coverage)} cases. Sample traced Python peak: {peak} bytes.\n")
    print(markdown(comparison))
    print(f"Offline analysis p50/p95 {report['analysis_p50_ms']:.3f}/{report['analysis_p95_ms']:.3f} ms; "
          f"bounded-process sample {bounded_sample_ms:.3f} ms; findings {sum(coverage)}/{len(coverage)}; "
          f"sample traced peak {peak} bytes. Saved {prefix}.")


if __name__ == '__main__':
    main()
