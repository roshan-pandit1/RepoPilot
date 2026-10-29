#!/bin/bash
# Read-only correlated evidence: pass the job UUID printed by the browser check.
set -euo pipefail
job_id="${1:-}"
if [[ ! "$job_id" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]]; then
  printf 'Usage: bash apps/api/evaluation/investigation-4c-evidence.sh JOB_UUID\n' >&2
  exit 1
fi
cd "$(git rev-parse --show-toplevel)"
docker compose exec -T postgres sh -c 'exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v jobid="$1"' sh "$job_id" <<'SQL'
SELECT j.id, j.repository_id, j.issue_number, j.status, j.attempts, j.error_code,
       j.created_at, j.started_at, j.completed_at, j.operation, j.snapshot_id, j.snapshot_commit_sha, j.retrieval_warning,
       o.status AS outbox_status, o.attempts AS dispatch_attempts
FROM investigation_jobs j JOIN investigation_outbox o ON o.job_id = j.id
WHERE j.id = :'jobid';
SELECT e.rank, e.chunk_id, f.path, c.symbol, c.start_line, c.end_line, e.query_id, e.query_rank, e.method
FROM investigation_evidence e JOIN code_chunks c ON c.id = e.chunk_id
JOIN indexed_files f ON f.id = c.file_id WHERE e.job_id = :'jobid' ORDER BY e.rank;
SQL
# Verify persisted ownership and fingerprints inside the API container. Pipe only hashes and
# citation metadata to the host Git verifier; source text and credentials are never printed.
docker compose exec -T api python - "$job_id" <<'PYVERIFY' | PYTHONPATH="$PWD/apps/api" .venv/bin/python apps/api/evaluation/verify_4c_citations.py "$PWD"
import hashlib, json, sys
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.domain.models import CodeChunk, CodeSnapshot, IndexedFile, InvestigationEvidence, InvestigationJob, InvestigationOutbox
from app.modules.investigation.retrieval import fingerprint_chunk
try:
    settings = get_settings()
    url = make_url(settings.database_url)
    assert settings.app_env == 'development' and url.host == 'postgres' and url.database == 'repopilot'
    with Session(create_engine(url, hide_parameters=True)) as db:
        job = db.get(InvestigationJob, sys.argv[1])
        assert job and job.repository_id == 1435878031 and job.issue_number == 1
        assert job.operation == 'code_evidence' and job.status == 'completed'
        snapshot = db.get(CodeSnapshot, job.snapshot_id)
        outbox = db.get(InvestigationOutbox, job.id)
        assert snapshot and snapshot.published and snapshot.repository_id == job.repository_id
        assert snapshot.tenant_id == job.tenant_id and snapshot.commit_sha == job.snapshot_commit_sha
        assert outbox and outbox.status == 'processed'
        evidence = db.scalars(select(InvestigationEvidence).where(InvestigationEvidence.job_id == job.id)
                              .order_by(InvestigationEvidence.rank)).all()
        assert len(evidence) <= job.evidence_limit
        assert [e.rank for e in evidence] == list(range(1, len(evidence) + 1))
        assert len({e.chunk_id for e in evidence}) == len(evidence)
        items = []
        for e in evidence:
            chunk = db.get(CodeChunk, e.chunk_id)
            file = db.get(IndexedFile, chunk.file_id) if chunk else None
            assert chunk and file and e.snapshot_id == snapshot.id and file.snapshot_id == snapshot.id
            assert chunk.repository_id == file.repository_id == e.repository_id == job.repository_id
            assert chunk.tenant_id == file.tenant_id == e.tenant_id == job.tenant_id
            assert fingerprint_chunk(chunk, file) == e.chunk_fingerprint
            assert len(chunk.source_text.splitlines()) == chunk.end_line - chunk.start_line + 1
            items.append({'path': file.path, 'symbol': chunk.symbol, 'start_line': chunk.start_line,
                          'end_line': chunk.end_line, 'file_hash': file.content_hash,
                          'chunk_hash': hashlib.sha256(chunk.source_text.encode()).hexdigest()})
        print(json.dumps({'repository': job.source_repository_name, 'commit_sha': snapshot.commit_sha, 'items': items}))
except Exception:
    print('Persisted evidence validation failed.', file=sys.stderr)
    raise SystemExit(1) from None
PYVERIFY
docker compose logs --no-color --since=2h dispatcher worker | .venv/bin/python -c '
import json, sys
job = sys.argv[1]
for line in sys.stdin:
    pos = line.find("{")
    if pos < 0: continue
    try: row = json.loads(line[pos:])
    except ValueError: continue
    if row.get("job_id") == job and str(row.get("event", "")).startswith("investigation_"):
        print(json.dumps({k: row[k] for k in ("event", "job_id", "repository_id", "task_id", "snapshot_id", "level") if k in row}))
' "$job_id"
