"""Build and validate report evidence using the existing 4C evidence authority."""
import json
from app.modules.ingestion.citations import github_citation
from app.modules.investigation.retrieval import InvalidEvidence, fingerprint_chunk, load_verified_evidence
from app.modules.investigation.report_model import (MAX_EVIDENCE, EvidenceInput, InvestigationInput,
                                                     ModelError, ModelResult, validate_draft)


def evidence_inputs(db, parent, snapshot):
    try:
        rows = load_verified_evidence(db, parent, snapshot)
        return [{'chunk_id': chunk.id, 'path': file.path, 'symbol': chunk.symbol,
                 'start_line': chunk.start_line, 'end_line': chunk.end_line,
                 'source_text': chunk.source_text, 'fingerprint': fingerprint_chunk(chunk, file),
                 'citation': github_citation(parent.source_repository_name, snapshot.commit_sha,
                                             file.path, chunk.start_line, chunk.end_line)}
                for _, chunk, file in rows]
    except (InvalidEvidence, ValueError):
        raise ModelError('evidence_unavailable') from None


def render_report_payload(payload, *, parent, evidence):
    """Revalidate saved references and reconstruct URLs from verified evidence on every read."""
    if not isinstance(payload, dict) or not isinstance(payload.get('hypotheses'), list) or not all(
            isinstance(item, dict) for item in payload['hypotheses']):
        raise ModelError('report_unavailable')
    safe_draft = {**payload, 'hypotheses': [
        {key: value for key, value in hypothesis.items() if key not in {'support_status', 'uncertainty'}}
        for hypothesis in payload.get('hypotheses', [])]}
    allowed = evidence[:MAX_EVIDENCE]
    request = InvestigationInput(investigation_id=parent.id, repository_id=str(parent.repository_id),
        issue_id=str(parent.issue_id), issue_number=parent.issue_number, title='', body='', labels=(), comments=(),
        snapshot_id=parent.snapshot_id, commit_sha=parent.snapshot_commit_sha, truncated=False,
        evidence=tuple(EvidenceInput(chunk_id=row['chunk_id'], snapshot_id=parent.snapshot_id,
            commit_sha=parent.snapshot_commit_sha, path=row['path'], symbol=row['symbol'],
            start_line=row['start_line'], end_line=row['end_line'], citation=row['citation'], excerpt='')
            for row in allowed))
    try:
        validated = validate_draft(ModelResult(json.dumps(safe_draft)), request)
    except (ValueError, TypeError, ModelError):
        raise ModelError('report_unavailable') from None
    evidence_by_id = {row['chunk_id']: row for row in allowed}
    for hypothesis in validated['hypotheses']:
        for reference in [*hypothesis['evidence'], *hypothesis['contradictory_evidence']]:
            row = evidence_by_id[reference['chunk_id']]
            reference.update(path=row['path'], symbol=row['symbol'], url=row['citation'])
    if len(json.dumps(validated, ensure_ascii=True).encode()) > 60_000:
        raise ModelError('report_unavailable')
    return validated
