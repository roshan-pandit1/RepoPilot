import json
import math
from pathlib import Path

import pytest

from app.evaluation.retrieval import citation_valid, evaluate, main, markdown, match_label, measure_query
from app.evaluation.compare_reports import compare
from app.modules.ingestion.code_chunking import chunk_python


def test_whitespace_chunks_preserve_gaps_and_exact_line_slices():
    source = 'def one():\n    return 1\n\n\ndef two():\n    return 2\n'
    chunks = chunk_python(source)
    assert [chunk.symbol for chunk in chunks] == ['one', None, 'two']
    assert not chunks[1].text.strip()
    assert all(chunk.text == ''.join(source.splitlines(keepends=True)[chunk.start_line - 1:chunk.end_line]) for chunk in chunks)
    assert chunk_python('') == []
    assert chunk_python('\n \n')[0].text.strip() == ''


def test_matching_requires_complete_label_symbol_and_path():
    label = {'path': 'x.py', 'symbol': 'f', 'start_line': 3, 'end_line': 5}
    result = {'path': 'x.py', 'symbol': 'f', 'start_line': 2, 'end_line': 4}
    assert not match_label(result, label)
    assert match_label({**result, 'end_line': 5}, label)
    assert not match_label({**result, 'end_line': 5, 'symbol': 'g'}, label)


def test_metrics_deduplicate_labels_and_calculate_recall_mrr_ndcg():
    labels = [{'path': 'a', 'symbol': 'a', 'start_line': 1, 'end_line': 1},
              {'path': 'b', 'symbol': 'b', 'start_line': 2, 'end_line': 2}]
    a = {'path': 'a', 'symbol': 'a', 'start_line': 1, 'end_line': 1}
    b = {'path': 'b', 'symbol': 'b', 'start_line': 2, 'end_line': 3}
    result = measure_query(labels, [{}, a, a, b])
    assert result['recall'] == {'1': 0, '3': .5, '5': 1, '10': 1}
    assert result['reciprocal_rank'] == .5
    assert result['relevant_ranks'] == [2, 4]
    assert math.isclose(result['ndcg_at_10'], (1 / math.log2(3) + 1 / math.log2(5)) / (1 + 1 / math.log2(3)))


def test_citation_and_commit_mismatch_rejected():
    sha = 'a' * 40
    item = {'path': 'src/my file.py', 'start_line': 2, 'end_line': 3, 'commit_sha': sha,
            'url': f'https://github.com/alice/repo/blob/{sha}/src/my%20file.py#L2-L3'}
    assert citation_valid(item, 'alice/repo', sha)
    assert not citation_valid({**item, 'url': item['url'] + 'x'}, 'alice/repo', sha)
    assert not citation_valid({**item, 'commit_sha': 'b' * 40}, 'alice/repo', sha)


def test_aggregate_includes_fallback_citations_and_safe_metadata():
    sha = 'a' * 40
    label = {'path': 'a.py', 'symbol': 'f', 'start_line': 1, 'end_line': 1}
    dataset = {'commit_sha': sha, 'repository': 'alice/repo', 'queries': [{'id': 'q', 'question': 'where', 'relevance': [label]}]}
    item = {**label, 'commit_sha': sha, 'url': f'https://github.com/alice/repo/blob/{sha}/a.py#L1-L1', 'snippet': 'PRIVATE SOURCE'}
    response = {'items': [item], 'commit_sha': sha, 'mode': 'keyword', 'fallback_reason': 'not_ready'}
    report = evaluate(dataset, {(mode, 'q'): (response, 10.0) for mode in ('keyword', 'semantic', 'hybrid')}, {'provider': 'fake'})
    assert report['modes']['hybrid']['fallback_count'] == 1
    assert report['modes']['keyword']['recall']['1'] == 1
    assert 'PRIVATE SOURCE' not in json.dumps(report)
    assert 'MECHANICAL TEST ONLY' in markdown(report)
    assert 'PRIVATE SOURCE' not in markdown(report)
    compared = compare(report, report)
    assert compared['modes']['keyword']['before']['zero_results'] == 0
    other = {**report, 'configuration': {'provider': 'different'}}
    with pytest.raises(ValueError, match='Embedding configuration'):
        compare(report, other)
    response['commit_sha'] = 'b' * 40
    with pytest.raises(ValueError, match='Snapshot commit'):
        evaluate(dataset, {(mode, 'q'): (response, 10.0) for mode in ('keyword', 'semantic', 'hybrid')}, {})


def test_benchmark_labels_have_bounded_symbol_anchors():
    root = Path(__file__).resolve().parents[1]
    dataset = json.loads((root / 'evaluation/repopilot-6349190.json').read_text())
    assert len(dataset['queries']) == 20
    assert len({query['id'] for query in dataset['queries']}) == 20
    for query in dataset['queries']:
        for label in query['relevance']:
            assert label['path'].startswith('apps/api/app/')
            assert label['symbol'] and label['start_line'] == label['end_line'] > 0


def test_browser_capture_produces_sanitized_reports_without_credentials(tmp_path, monkeypatch):
    sha = 'a' * 40
    label = {'path': 'a.py', 'symbol': 'f', 'start_line': 1, 'end_line': 1}
    dataset = {'commit_sha': sha, 'repository': 'alice/repo', 'queries': [{'id': 'q', 'question': 'where', 'relevance': [label]}]}
    capture = {'commit_sha': sha, 'repository': 'alice/repo', 'repository_id': '42', 'provider': 'fake',
               'queries': [{'mode': mode, 'id': 'q', 'latency_ms': 3, 'response': {
                   'commit_sha': sha, 'mode': mode, 'items': [], 'fallback_reason': None}}
                   for mode in ('keyword', 'semantic', 'hybrid')]}
    dataset_file, capture_file, output = tmp_path / 'dataset.json', tmp_path / 'capture.json', tmp_path / 'report'
    dataset_file.write_text(json.dumps(dataset))
    capture_file.write_text(json.dumps(capture))
    monkeypatch.setattr('sys.argv', ['eval', '--dataset', str(dataset_file), '--repository-id', '42',
                                    '--capture', str(capture_file), '--output', str(output)])
    main()
    assert json.loads(output.with_suffix('.json').read_text())['modes']['keyword']['no_relevant'] == 1
    assert 'MECHANICAL TEST ONLY' in output.with_suffix('.md').read_text()
