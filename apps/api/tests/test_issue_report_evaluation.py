"""4F provenance, scoring and report checks without creating a source snapshot."""
import json
import logging
import math
from copy import deepcopy
from pathlib import Path

import pytest
import httpx

from app.evaluation.issue_report import assess_report, model_grounding_probes, score_retrieval, verify_dataset
from app.evaluation.issue_report_disposable import COMMIT, main as disposable_main, quiet_fixture_http_logs
from app.modules.ingestion.citations import github_citation
from app.modules.investigation.report_model import build_package
from test_auth_enrollment import github_auth as github_auth, sign_in

ROOT = Path(__file__).resolve().parents[3]
DATASET = json.loads((ROOT / 'apps/api/evaluation/issue-report-v1.json').read_text())
SNAPSHOT = '11111111-1111-4111-8111-111111111111'
JOB = '33333333-3333-4333-8333-333333333333'
CHUNK = '22222222-2222-4222-8222-222222222222'


def evidence():
    label = DATASET['cases'][0]['relevance'][0]
    return {'chunk_id': CHUNK, 'rank': 1, **label, 'commit_sha': DATASET['commit_sha'],
            'url': github_citation(DATASET['repository'], DATASET['commit_sha'], label['path'],
                                   label['start_line'], label['end_line'])}


def small_dataset():
    return {**DATASET, 'cases': [DATASET['cases'][0], DATASET['cases'][1], DATASET['cases'][-2]]}


def responses():
    return [{'issue_id': case['issue_id'], 'snapshot_id': SNAPSHOT, 'commit_sha': DATASET['commit_sha'],
             'items': [evidence()] if index == 0 else [], 'retrieval_status': 'ready' if index == 0 else 'no_matches',
             'latency_ms': index + 1} for index, case in enumerate(small_dataset()['cases'])]


def test_labels_match_actual_commit_and_single_chunk():
    result = verify_dataset(DATASET, ROOT)
    assert (result['cases'], result['scored_cases'], result['unscored_cases'], result['labels']) == (19, 16, 3, 23)
    assert result['commit_sha'] == DATASET['commit_sha'] and result['source_tree_sha'] == DATASET['source_tree_sha']


def test_retrieval_scores_are_macro_averages_and_exclude_unscored_cases():
    report = score_retrieval(small_dataset(), responses(), snapshot_id=SNAPSHOT)
    assert report['scored_cases'] == 2 and report['unscored_cases'] == 1
    assert report['recall'] == {'1': .5, '3': .5, '5': .5, '10': .5}
    assert report['mrr'] == .5 and report['labeled_hit_at_10'] == 1
    assert report['zero_result_cases'] == 2 and report['cases'][2]['scores'] is None


def test_recall_counts_all_reviewed_labels_not_just_first_hit():
    case = next(case for case in DATASET['cases'] if case['issue_id'] == 'repository_access')
    label = case['relevance'][0]
    item = {'chunk_id': CHUNK, 'rank': 1, **label, 'commit_sha': DATASET['commit_sha'],
            'url': github_citation(DATASET['repository'], DATASET['commit_sha'], label['path'],
                                   label['start_line'], label['end_line'])}
    result = {'issue_id': case['issue_id'], 'snapshot_id': SNAPSHOT, 'commit_sha': DATASET['commit_sha'],
              'items': [item], 'retrieval_status': 'ready', 'latency_ms': 1}
    score = score_retrieval({**DATASET, 'cases': [case]}, [result], snapshot_id=SNAPSHOT)
    assert score['labeled_hit_at_10'] == 1 and score['mrr'] == 1
    assert score['recall'] == {'1': .5, '3': .5, '5': .5, '10': .5}
    assert score['ndcg_at_10'] == pytest.approx(1 / (1 + 1 / math.log2(3)))


def test_query_provenance_counts_retained_results_without_exposing_query_text():
    rows = responses()
    rows[0]['queries'] = [{'id': 'identifier_1', 'sha256': 'a' * 64}]
    rows[0]['items'][0]['query_id'] = 'identifier_1'
    result = score_retrieval(small_dataset(), rows, snapshot_id=SNAPSHOT)['cases'][0]
    assert result['queries'] == [{'id': 'identifier_1', 'sha256': 'a' * 64,
                                  'retained_evidence': 1, 'labeled_retained_ranks': [1]}]
    rows[0]['items'][0]['query_id'] = 'unknown'
    with pytest.raises(ValueError, match='unknown_evidence_query'):
        score_retrieval(small_dataset(), rows, snapshot_id=SNAPSHOT)


@pytest.mark.parametrize('fault', ['snapshot', 'commit', 'citation', 'duplicate', 'rank', 'latency', 'case'])
def test_mixed_or_malformed_run_is_rejected(fault):
    rows = deepcopy(responses())
    if fault == 'snapshot':
        rows[0]['snapshot_id'] = '44444444-4444-4444-8444-444444444444'
    elif fault == 'commit':
        rows[0]['commit_sha'] = 'b' * 40
    elif fault == 'citation':
        rows[0]['items'][0]['url'] = 'https://attacker.invalid/'
    elif fault == 'duplicate':
        rows[0]['items'].append(rows[0]['items'][0])
    elif fault == 'rank':
        rows[0]['items'][0]['rank'] = 2
    elif fault == 'latency':
        rows[0]['latency_ms'] = -1
    else:
        rows[0]['issue_id'] = rows[1]['issue_id']
    with pytest.raises(ValueError):
        score_retrieval(small_dataset(), rows, snapshot_id=SNAPSHOT)


def test_changed_commit_or_label_cannot_pass_provenance():
    changed = deepcopy(DATASET)
    changed['source_tree_sha'] = 'b' * 40
    with pytest.raises(ValueError, match='git_tree_mismatch'):
        verify_dataset(changed, ROOT)
    changed = deepcopy(DATASET)
    changed['cases'][0]['relevance'][0]['end_line'] = 9999
    with pytest.raises(ValueError, match='unmatched_label'):
        verify_dataset(changed, ROOT)


def report_envelope():
    item = evidence()
    ref = {key: item[key] for key in ('chunk_id', 'path', 'symbol', 'start_line', 'end_line', 'url')}
    ref.update(snapshot_id=SNAPSHOT, commit_sha=DATASET['commit_sha'])
    hypothesis = {'title': 'Possible area', 'explanation': 'A mock fixture.', 'observations': [],
        'missing_or_contradictory': [], 'evidence': [ref], 'contradictory_evidence': [],
        'support_status': 'speculative', 'uncertainty': 'high'}
    timestamp = '2026-01-01T00:00:00Z'
    report = {'investigation_id': JOB, 'repository_id': '902', 'issue_id': '990', 'issue_number': 5,
        'snapshot_id': SNAPSHOT, 'commit_sha': DATASET['commit_sha'], 'provider': 'mock',
        'model': 'deterministic-v1', 'status': 'completed',
        'disclaimer': 'Deterministic mock output; not AI reasoning or a diagnosis.',
        'summary': 'Mock only.', 'hypotheses': [hypothesis], 'missing_evidence': ['More information needed.'],
        'next_steps': [], 'warnings': [], 'input_truncated': False, 'snapshot_partial': False,
        'input_tokens': None, 'output_tokens': None, 'cost_microusd': 0, 'created_at': timestamp}
    return {'report_job_id': '44444444-4444-4444-8444-444444444444', 'status': 'completed', 'attempts': 1,
            'error_code': None, 'created_at': timestamp, 'started_at': timestamp, 'completed_at': timestamp,
            'report': report}


def test_report_grounding_rejects_foreign_or_duplicate_references():
    value = report_envelope()
    def check(report):
        return assess_report(report, investigation_id=JOB, repository_id=902,
            snapshot_id=SNAPSHOT, commit=DATASET['commit_sha'], evidence=[evidence()])
    result = check(value)
    assert result['schema_valid'] and result['provenance_valid'] and result['valid_references'] == 1
    bad = deepcopy(value)
    bad['report']['hypotheses'][0]['evidence'][0]['chunk_id'] = '55555555-5555-4555-8555-555555555555'
    assert check(bad)['valid_references'] == 0
    bad = deepcopy(value)
    bad['report']['hypotheses'][0]['contradictory_evidence'] = deepcopy(bad['report']['hypotheses'][0]['evidence'])
    assert check(bad)['references'] == 2 and check(bad)['valid_references'] == 1
    bad = deepcopy(value)
    bad['report']['snapshot_id'] = '55555555-5555-4555-8555-555555555555'
    assert not check(bad)['provenance_valid']


def test_empty_evidence_abstention_and_unsupported_label():
    value = report_envelope()
    value['report']['hypotheses'] = []
    result = assess_report(value, investigation_id=JOB, repository_id=902, snapshot_id=SNAPSHOT,
                           commit=DATASET['commit_sha'], evidence=[])
    assert result['schema_valid'] and result['empty_evidence_abstention']
    value['report']['hypotheses'] = [report_envelope()['report']['hypotheses'][0]]
    value['report']['hypotheses'][0]['evidence'] = []
    value['report']['hypotheses'][0]['support_status'] = 'unsupported'
    result = assess_report(value, investigation_id=JOB, repository_id=902, snapshot_id=SNAPSHOT,
                           commit=DATASET['commit_sha'], evidence=[])
    assert result['support_labels_valid'] and not result['empty_evidence_abstention']


def test_grounding_probes_measure_rejection_and_contradictory_references():
    def item(chunk_id, start):
        return {'chunk_id': chunk_id, 'path': 'src/example.py', 'symbol': 'example',
                'start_line': start, 'end_line': start + 1, 'source_text': 'def example():\n    pass\n',
                'citation': github_citation(DATASET['repository'], DATASET['commit_sha'],
                                            'src/example.py', start, start + 1)}
    package = build_package(investigation_id=JOB, repository_id=902, issue_id=990, issue_number=5,
        context={'title': 'A synthetic issue', 'body': 'An example'}, snapshot_id=SNAPSHOT,
        commit_sha=DATASET['commit_sha'], evidence=[item(CHUNK, 1),
            item('55555555-5555-4555-8555-555555555555', 3)])
    result = model_grounding_probes(package)
    assert len(result) == 10 and all(result.values())


def test_disposable_runner_rejects_missing_approval_and_normal_database(monkeypatch):
    monkeypatch.delenv('REPOPILOT_4F_APPROVED_COMMIT', raising=False)
    with pytest.raises(SystemExit, match='Separate approval'):
        disposable_main()
    monkeypatch.setenv('REPOPILOT_4F_APPROVED_COMMIT', COMMIT)
    monkeypatch.setenv('DATABASE_URL', 'postgresql://fixture:fixture@127.0.0.1/repopilot')
    monkeypatch.setenv('REPOPILOT_4F_DB', 'repopilot')
    with pytest.raises(SystemExit, match='Refusing non-dedicated'):
        disposable_main()
    monkeypatch.setenv('DATABASE_URL', 'postgresql://fixture:fixture@127.0.0.1/'
                        'repopilot_4f_disposable_test?host=example.invalid')
    monkeypatch.setenv('REPOPILOT_4F_DB', 'repopilot_4f_disposable_test')
    with pytest.raises(SystemExit, match='Refusing non-dedicated'):
        disposable_main()


def test_disposable_runner_suppresses_fixture_callback_query_logging(caplog, monkeypatch, client, github_auth):
    for name in ('httpx', 'httpx2'):
        logger = logging.getLogger(name)
        monkeypatch.setattr(logger, 'level', logger.level)
    caplog.set_level(logging.INFO)
    quiet_fixture_http_logs()
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200))) as probe:
        assert probe.get('https://fixture.invalid/callback?state=synthetic').status_code == 200
    sign_in(client)
    assert not any('state=synthetic' in record.getMessage() for record in caplog.records)
    assert not any('/v1/auth/github/callback?' in record.getMessage() for record in caplog.records)
