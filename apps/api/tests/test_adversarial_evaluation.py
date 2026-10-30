"""Versioned synthetic attacks exercise the real mock-model boundary."""
import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from app.evaluation.adversarial import evaluate, evaluate_case, fixture_input
from app.modules.investigation.report_model import (MAX_CONTEXT_BYTES, REPORT_INSTRUCTIONS, ModelError, ModelResult,
    MockInvestigationModel, model_request, validate_draft)

DATASET_PATH = Path(__file__).resolve().parents[1] / 'evaluation/adversarial-report-v1.json'
DATASET = json.loads(DATASET_PATH.read_bytes())


@pytest.mark.parametrize('case', DATASET['cases'], ids=lambda case: case['id'])
def test_adversarial_fixture_case(case):
    outcome = evaluate_case(case)
    assert outcome == ('isolated' if case['kind'] == 'input' else case['error'])


def test_dataset_report_is_reproducible_and_does_not_include_attack_text():
    data = DATASET_PATH.read_bytes()
    first, second = evaluate(data), evaluate(data)
    assert first == second and first['failed'] == 0 and first['passed'] == len(DATASET['cases'])
    assert first['dataset_sha256'] and first['control_policy'] == 'mock-report-policy-v1'
    for case in DATASET['cases']:
        if 'payload' in case:
            assert case['payload'] not in json.dumps(first)


def test_control_envelope_is_immutable_and_rejects_untrusted_policy_spoofing():
    data = fixture_input()
    envelope = model_request(data)
    assert envelope.instructions == REPORT_INSTRUCTIONS and envelope.instructions.allowed_tools == ()
    with pytest.raises(FrozenInstanceError):
        envelope.instructions.version = 'attacker'
    with pytest.raises(FrozenInstanceError):
        envelope.untrusted_data = data
    with pytest.raises(ModelError, match='model_input_invalid'):
        model_request(replace(data, content_is_untrusted=False))
    with pytest.raises(ModelError, match='context_limit'):
        model_request(replace(data, body='x' * MAX_CONTEXT_BYTES))
    fake = replace(envelope, instructions=replace(REPORT_INSTRUCTIONS, allowed_tools=('shell',)))
    with pytest.raises(ModelError, match='model_input_invalid'):
        MockInvestigationModel().generate(fake, timeout_seconds=2)


@pytest.mark.parametrize('change', ['snapshot', 'commit', 'duplicate', 'invalid_lines'])
def test_evidence_allowlist_itself_must_match_pinned_snapshot(change):
    request = fixture_input()
    raw = MockInvestigationModel().generate(model_request(request), timeout_seconds=2).raw_json
    item = request.evidence[0]
    if change == 'snapshot':
        item = replace(item, snapshot_id='44444444-4444-4444-8444-444444444444')
    elif change == 'commit':
        item = replace(item, commit_sha='b' * 40)
    elif change == 'invalid_lines':
        item = replace(item, start_line=3, end_line=2)
    evidence = (item, item) if change == 'duplicate' else (item,)
    invalid = replace(request, evidence=evidence)
    with pytest.raises(ModelError, match='model_evidence_invalid'):
        model_request(invalid)
    with pytest.raises(ModelError, match='model_evidence_invalid'):
        validate_draft(ModelResult(raw), invalid)
