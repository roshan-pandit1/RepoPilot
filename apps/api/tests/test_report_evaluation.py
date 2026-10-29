"""Synthetic mock-report mechanics; no claim of model diagnostic accuracy."""
import hashlib
import json
import os
import statistics
import time
from dataclasses import replace
from pathlib import Path

from sqlalchemy import select

from app.domain.models import InvestigationReport, InvestigationReportJob
from app.evaluation.retrieval import citation_valid, percentile
from app.modules.investigation.report_model import (ModelError, ModelResult, MockInvestigationModel,
                                                    build_package, validate_draft)
from app.modules.investigation.report_worker import process_report
from app.modules.ingestion.citations import github_citation
from test_auth_enrollment import github_auth as github_auth
from test_investigation_reports import report_url, request_report, setup_parent
from test_report_model import COMMIT, JOB, SNAPSHOT, package


def test_synthetic_mock_report_evaluation(client, factory, github_auth, monkeypatch):
    api = Path(__file__).resolve().parents[1]
    dataset_bytes = (api / 'evaluation/mock-report-v1.json').read_bytes()
    dataset = json.loads(dataset_bytes)
    rows = []
    for case in dataset['cases']:
        if case['kind'] == 'worker_security':
            continue
        start = time.perf_counter()
        source = package(case['kind'] not in {'no_evidence', 'unsupported'})
        request = build_package(investigation_id=JOB, repository_id=902, issue_id=990, issue_number=5,
            context={'title': case['title'], 'body': case['body'], 'labels': [], 'comments': [], 'truncation': {}},
            snapshot_id=SNAPSHOT, commit_sha=COMMIT, evidence=[{
                'chunk_id': row.chunk_id, 'path': row.path, 'symbol': row.symbol,
                'start_line': row.start_line, 'end_line': row.end_line,
                'citation': row.citation, 'source_text': row.excerpt} for row in source.evidence])
        if case['kind'] in {'ambiguous', 'contradictory'}:
            second = replace(request.evidence[0], chunk_id='55555555-5555-4555-8555-555555555555',
                             path='src/other.py', start_line=6, end_line=7,
                             citation=github_citation('alice/public', COMMIT, 'src/other.py', 6, 7))
            request = replace(request, evidence=(*request.evidence, second))
        for item in request.evidence:
            assert citation_valid({'url': item.citation, 'path': item.path, 'start_line': item.start_line,
                                   'end_line': item.end_line, 'commit_sha': item.commit_sha}, 'alice/public', COMMIT)
        model = MockInvestigationModel()
        raw = model.generate(request, timeout_seconds=2).raw_json
        draft = json.loads(raw)
        if case['kind'] == 'unsupported':
            draft['hypotheses'] = [{'title': 'Possible issue', 'explanation': 'No support is available.',
                'observations': [], 'missing_or_contradictory': ['Evidence missing.'], 'evidence': []}]
        if case['kind'] == 'contradictory':
            second = request.evidence[1]
            draft['hypotheses'][0]['contradictory_evidence'] = [{'chunk_id': second.chunk_id,
                'snapshot_id': SNAPSHOT, 'commit_sha': COMMIT, 'start_line': second.start_line,
                'end_line': second.end_line}]
        if case['kind'] == 'foreign_citation':
            draft['hypotheses'][0]['evidence'][0]['chunk_id'] = '44444444-4444-4444-8444-444444444444'
        raw = '{' if case['kind'] == 'malformed' else json.dumps(draft)
        try:
            result = validate_draft(ModelResult(raw), request)
            outcome = 'valid'
            references = sum(len(h['evidence']) + len(h['contradictory_evidence']) for h in result['hypotheses'])
            if case['kind'] == 'no_evidence':
                assert result['hypotheses'] == []
            if case['kind'] == 'unsupported':
                assert result['hypotheses'][0]['support_status'] == 'unsupported'
            if case['kind'] == 'malicious':
                assert 'token' not in request.body.lower() and request.content_is_untrusted
                assert 'shell command' not in json.dumps(result)
        except ModelError:
            outcome, references = 'rejected', 0
        expected = 'rejected' if case['kind'] in {'malformed', 'foreign_citation'} else 'valid'
        assert outcome == expected
        rows.append({'id': case['id'], 'outcome': outcome, 'validated_references': references,
                     'latency_ms': round((time.perf_counter() - start) * 1000, 3)})
    parent, _, _ = setup_parent(client, factory, github_auth, monkeypatch)
    task = request_report(client, parent)
    assert request_report(client, parent) == task
    process_report(task, factory, github_auth)
    process_report(task, factory, github_auth)
    with factory() as db:
        assert db.get(InvestigationReportJob, task).attempts == 1
        assert len(db.scalars(select(InvestigationReport)).all()) == 1
    github_auth.include_repository = False
    assert client.get(report_url(parent)).status_code == 404
    report = {'dataset': dataset['version'], 'dataset_sha256': hashlib.sha256(dataset_bytes).hexdigest(),
        'mode': 'deterministic mock; synthetic in-process inputs and mocked authorization',
        'model_cases': len(rows), 'valid_reports': sum(r['outcome'] == 'valid' for r in rows),
        'invalid_outputs_rejected': sum(r['outcome'] == 'rejected' for r in rows),
        'validated_evidence_references': sum(r['validated_references'] for r in rows),
        'duplicate_delivery_report_rows': 1, 'duplicate_delivery_worker_attempts': 1,
        'revoked_access_http': 404, 'model_validation_latency_p50_ms': statistics.median(r['latency_ms'] for r in rows),
        'model_validation_latency_p95_ms': percentile([r['latency_ms'] for r in rows], .95),
        'cases': rows, 'limitations': 'Mock mechanics only; synthetic references, no real model reasoning, remote citations, real Celery or performance/load claim.'}
    prefix = os.environ.get('REPOPILOT_4D_EVAL_PREFIX')
    if prefix:
        target = Path(prefix)
        target.with_suffix('.json').write_text(json.dumps(report, indent=2) + '\n')
        lines = ['# Mock report evaluation', '', f"Dataset: {report['dataset']}",
            f"Valid model outputs: {report['valid_reports']}/{report['model_cases']}",
            f"Invalid outputs rejected: {report['invalid_outputs_rejected']}",
            f"Validated synthetic evidence references: {report['validated_evidence_references']}",
            f"Duplicate replay: {report['duplicate_delivery_report_rows']} report, {report['duplicate_delivery_worker_attempts']} worker attempt; revoked access HTTP {report['revoked_access_http']}",
            f"In-process model validation p50/p95: {report['model_validation_latency_p50_ms']:.3f}/{report['model_validation_latency_p95_ms']:.3f} ms", '',
            '| Case | Outcome | References |', '| --- | --- | ---: |']
        lines += [f"| {row['id']} | {row['outcome']} | {row['validated_references']} |" for row in rows]
        target.with_suffix('.md').write_text('\n'.join(lines) + '\n\n' + report['limitations'] + '\n')
    print('Mock report mechanics: ' + json.dumps(report))
