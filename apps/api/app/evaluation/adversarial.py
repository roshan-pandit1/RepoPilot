"""Reproducible synthetic security-boundary checks for the local mock report model."""
import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from app.modules.ingestion.citations import github_citation
from app.modules.investigation.report_model import (REPORT_INSTRUCTIONS, ModelError, ModelResult,
    MockInvestigationModel, build_package, execute_model, model_request, validate_draft)

JOB = '33333333-3333-4333-8333-333333333333'
SNAPSHOT = '11111111-1111-4111-8111-111111111111'
CHUNK = '22222222-2222-4222-8222-222222222222'
COMMIT = 'a' * 40
FOREIGN = '44444444-4444-4444-8444-444444444444'


def fixture_input(case=None):
    case = case or {}
    context = {'title': 'Investigate the fixture', 'body': 'A test issue.', 'labels': [], 'comments': [], 'truncation': {}}
    source = 'def demo():\n    return 1\n'
    path, symbol = 'src/demo.py', 'demo'
    payload = case.get('payload', '') * case.get('repeat', 1)
    surface = case.get('surface')
    if surface in {'title', 'body'}:
        context[surface] = payload
    elif surface == 'comment':
        context['comments'] = [{'body': payload}]
    elif surface == 'label':
        context['labels'] = [payload]
    elif surface == 'source':
        source = payload
    elif surface == 'path':
        path = payload
    elif surface == 'symbol':
        symbol = payload
    elif surface is not None:
        raise ValueError('unknown_fixture_surface')
    evidence = [{'chunk_id': CHUNK, 'path': path, 'symbol': symbol, 'start_line': 1, 'end_line': 2,
                 'citation': github_citation('alice/public', COMMIT, path, 1, 2), 'source_text': source}]
    return build_package(investigation_id=JOB, repository_id=902, issue_id=990, issue_number=5,
        context=context, snapshot_id=SNAPSHOT, commit_sha=COMMIT, evidence=evidence)


def evaluate_case(case):
    """Run a named fixture through the real projection and validation; never evaluate fixture text."""
    if case['kind'] == 'input':
        request = fixture_input(case)
        envelope = model_request(request)
        serialized = json.loads(json.dumps(asdict(envelope), ensure_ascii=True))
        if (envelope.instructions != REPORT_INSTRUCTIONS or envelope.instructions.allowed_tools
                or not envelope.untrusted_data.content_is_untrusted
                or set(serialized) != {'instructions', 'untrusted_data'}):
            raise AssertionError('control_boundary_changed')
        actual, _ = execute_model(MockInvestigationModel(), request)
        baseline, _ = execute_model(MockInvestigationModel(), fixture_input())
        if actual != baseline:
            raise AssertionError('mock_output_changed')
        if case.get('repeat', 1) > 1 and not request.truncated:
            raise AssertionError('truncation_missing')
        return 'isolated'
    if case['kind'] != 'output':
        raise ValueError('unknown_fixture_kind')
    request = fixture_input()
    model = MockInvestigationModel()
    output = json.loads(model.generate(model_request(request), timeout_seconds=2).raw_json)
    reference = output['hypotheses'][0]['evidence'][0]
    attack = case['attack']
    if attack == 'text':
        output['summary'] = case['payload']
    elif attack == 'escaped_unicode':
        output['summary'] = '\ud800'
    elif attack == 'repository':
        output['repository_id'] = '999'
    elif attack == 'tool':
        output['tool_calls'] = [{'name': 'shell'}]
    elif attack == 'chunk':
        reference['chunk_id'] = FOREIGN
    elif attack == 'snapshot':
        reference['snapshot_id'] = FOREIGN
    elif attack == 'commit':
        reference['commit_sha'] = 'b' * 40
    elif attack == 'line':
        reference['end_line'] = 999
    elif attack == 'duplicate':
        output['hypotheses'][0]['contradictory_evidence'] = [reference.copy()]
    elif attack == 'url':
        reference['url'] = 'https://attacker.invalid/'
    elif attack not in {'malformed', 'unicode', 'duplicate_key', 'oversized'}:
        raise ValueError('unknown_fixture_attack')
    raw = {'malformed': '{', 'unicode': '\ud800', 'duplicate_key': '{"summary":"a","summary":"b"}',
           'oversized': 'x' * 16_001}.get(attack, json.dumps(output))
    try:
        validate_draft(ModelResult(raw), request)
    except ModelError as exc:
        if str(exc) != case['error']:
            raise AssertionError('wrong_rejection') from None
        return str(exc)
    raise AssertionError('malicious_output_accepted')


def evaluate(dataset_bytes):
    dataset = json.loads(dataset_bytes)
    cases = dataset['cases']
    if dataset.get('version') != 'adversarial-report-v1' or not cases:
        raise ValueError('invalid_dataset')
    identifiers = [case['id'] for case in cases]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError('duplicate_case')
    rows = []
    for case in cases:
        try:
            outcome = evaluate_case(case)
            rows.append({'id': case['id'], 'kind': case['kind'], 'status': 'pass', 'outcome': outcome})
        except (AssertionError, KeyError, TypeError, ValueError, ModelError):
            rows.append({'id': case.get('id', 'invalid'), 'kind': case.get('kind', 'invalid'),
                         'status': 'fail', 'outcome': 'boundary_check_failed'})
    return {'dataset': dataset['version'], 'dataset_sha256': hashlib.sha256(dataset_bytes).hexdigest(),
            'model': 'mock/deterministic-v1', 'control_policy': REPORT_INSTRUCTIONS.version,
            'case_count': len(rows), 'passed': sum(row['status'] == 'pass' for row in rows),
            'failed': sum(row['status'] != 'pass' for row in rows), 'cases': rows,
            'limitations': 'Synthetic mock boundary checks only; no real LLM or prompt-injection resistance claim.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=Path('evaluation/adversarial-report-v1.json'))
    parser.add_argument('--output', type=Path, default=Path('evaluation/4e-security-evaluation'))
    args = parser.parse_args()
    result = evaluate(args.dataset.read_bytes())
    args.output.with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
    lines = ['# Mock report security evaluation', '', f"Dataset: {result['dataset']}",
             f"Dataset SHA-256: {result['dataset_sha256']}", f"Policy: {result['control_policy']}",
             f"Cases passed: {result['passed']}/{result['case_count']}; failed: {result['failed']}", '',
             '| Case | Kind | Status | Outcome |', '| --- | --- | --- | --- |']
    lines.extend(f"| {row['id']} | {row['kind']} | {row['status']} | {row['outcome']} |" for row in result['cases'])
    lines.extend(['', '## Enforced boundaries', '',
        '- Fixed application-owned instructions are separate from the bounded untrusted data object.',
        '- The mock has no tools or network interface; evidence is checked before invocation and output validation.',
        '- Explicit role, command and URL attacks in this fixture are rejected as model output.',
        '', '## Limits', '',
        '- These synthetic cases do not measure a real model or prove resistance to prompt injection.',
        '- Pattern filters and best-effort redaction can miss attacks or secrets and can reject benign text.',
        '- Database tenant/snapshot, revocation and retry checks are separate pytest integration tests.',
        '- No real-provider, live-job, external-link, load or production-readiness claim is made.'])
    args.output.with_suffix('.md').write_text('\n'.join(lines) + '\n')
    print(f"Adversarial fixture checks: {result['passed']}/{result['case_count']} passed")
    if result['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
