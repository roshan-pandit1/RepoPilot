"""Offline accounting, exact-request bounds and fail-closed paid-execution checks."""
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from app.evaluation.experiment_executor import (canonical, digest, execute_live, read_private,
    record_live_approval, template, write_private)
from app.evaluation.provider_harness import network_fence
from app.modules.investigation import openai_provider
from app.modules.investigation.report_model import ModelError, model_request
from app.modules.investigation.usage_ledger import (INPUT_WINDOW, OUTPUT_LIMIT,
    require_stress_capacity, require_verified_actual_pricing, stress_reservation, upper_cost)
from test_report_model import package

ROOT = Path(__file__).resolve().parents[3]


def test_additional_uplifts_are_compounded_and_rounded_up():
    base = upper_cost(INPUT_WINDOW, OUTPUT_LIMIT)
    assert base == 5_815_551
    # Exact dollars are 6.3971061 and 7.03681671; the ledger uses whole microdollars.
    assert stress_reservation(base, 1) == 6_397_107
    assert stress_reservation(base, 2) == 7_036_817
    assert stress_reservation(4_958_677, 2) <= 6_000_000
    assert stress_reservation(4_958_678, 2) > 6_000_000


@pytest.mark.parametrize('amount,uplifts', [(-1, 1), (1, -1), (1, 3), (True, 1), (1, True)])
def test_stress_calculation_rejects_invalid_amounts(amount, uplifts):
    with pytest.raises(ModelError, match='budget_unavailable'):
        stress_reservation(amount, uplifts)


def test_stress_capacity_rejects_per_investigation_or_experiment_excess():
    with pytest.raises(ModelError, match='budget_exhausted'):
        require_stress_capacity(5_815_551, 6_000_000, 10_000_000)
    with pytest.raises(ModelError, match='budget_exhausted'):
        require_stress_capacity(5_815_551, 10_000_000, 6_000_000)
    require_stress_capacity(4_958_677, 6_000_000, 10_000_000)


def test_stress_capacity_fails_closed_for_value_beyond_postgres_bigint():
    maximum_bigint = 2**63 - 1
    assert stress_reservation(maximum_bigint, 2) > maximum_bigint
    with pytest.raises(ModelError, match='budget_exhausted'):
        require_stress_capacity(maximum_bigint, 6_000_000, 10_000_000)


def test_unknown_account_pricing_blocks_actual_approval_and_execution_without_database():
    with pytest.raises(ModelError, match='pricing_unverified'):
        require_verified_actual_pricing()
    with pytest.raises(ModelError, match='pricing_unverified'):
        record_live_approval(None, ROOT, experiment_id='', job_id='', directory='', request_hash='',
                             manifest_hash='', screening_acknowledged=True, pricing_acknowledged=True)
    with pytest.raises(ModelError, match='pricing_unverified'):
        execute_live(None, ROOT, experiment_id='', job_id='', approval_id='', directory='')


def test_serialized_request_limit_is_exact_and_checked_before_send():
    request = model_request(package(False))
    original = openai_provider.build_responses_payload(request, OUTPUT_LIMIT)
    size = len(openai_provider.canonical_payload_bytes(original))
    padding = openai_provider.MAX_REQUEST_BYTES - size
    assert padding > 0
    at_limit = replace(request, untrusted_data=replace(
        request.untrusted_data, body=request.untrusted_data.body + 'x' * padding))
    payload = openai_provider.build_responses_payload(at_limit, OUTPUT_LIMIT)
    assert len(openai_provider.canonical_payload_bytes(payload)) == openai_provider.MAX_REQUEST_BYTES
    over_limit = replace(at_limit, untrusted_data=replace(at_limit.untrusted_data, body=at_limit.untrusted_data.body + 'x'))
    with pytest.raises(ModelError, match='model_input_invalid'):
        openai_provider.build_responses_payload(over_limit, OUTPUT_LIMIT)


@pytest.mark.parametrize('part', ['instructions', 'schema'])
def test_request_limit_counts_instructions_and_output_schema(part, monkeypatch):
    request = model_request(package(False))
    if part == 'instructions':
        controls = replace(request.instructions, rules=request.instructions.rules + ('x' * 8192,))
        monkeypatch.setattr(openai_provider, 'REPORT_INSTRUCTIONS', controls)
        request = replace(request, instructions=controls)
    else:
        monkeypatch.setattr(openai_provider, 'strict_schema', lambda: {'type': 'object', 'description': 'x' * 8192})
    with pytest.raises(ModelError, match='model_input_invalid'):
        openai_provider.build_responses_payload(request, OUTPUT_LIMIT)


@pytest.mark.parametrize('change', ['issue', 'source', 'instructions', 'schema'])
def test_changed_request_content_invalidates_review(change, tmp_path):
    with network_fence(0):
        payload, manifest = template(ROOT)
    changed = deepcopy(payload)
    if change in {'issue', 'source'}:
        content = json.loads(changed['input'][0]['content'])
        if change == 'issue':
            content['body'] += ' changed'
        else:
            content['evidence'][0]['excerpt'] += ' changed'
        changed['input'][0]['content'] = json.dumps(content, ensure_ascii=True, separators=(',', ':'))
    elif change == 'instructions':
        changed['instructions'] += ' changed'
    else:
        changed['text']['format']['schema']['description'] = 'changed'
    assert digest(canonical(changed)) != manifest['request_sha256']
    private = tmp_path / 'review'
    private.mkdir(mode=0o700)
    write_private(private, changed, manifest)
    with network_fence(0), pytest.raises((ValueError, ModelError)):
        read_private(private, ROOT, experiment_id=manifest['experiment_id'], job_id=manifest['report_job_id'])


def test_preexisting_disclosure_manifest_is_not_reusable(tmp_path):
    with network_fence(0):
        payload, manifest = template(ROOT)
    old = deepcopy(manifest)
    del old['request_byte_limit'], old['actual_pricing_state']
    private = tmp_path / 'review'
    private.mkdir(mode=0o700)
    write_private(private, payload, old)
    with network_fence(0), pytest.raises(ValueError, match='review_mismatch'):
        read_private(private, ROOT, experiment_id=manifest['experiment_id'], job_id=manifest['report_job_id'])
