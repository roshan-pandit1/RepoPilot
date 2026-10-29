#!/bin/bash
# Read-only correlated evidence: pass the job UUID printed by the browser check.
set -euo pipefail
job_id="${1:-}"
if [[ ! "$job_id" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]]; then
  printf 'Usage: bash apps/api/evaluation/investigation-evidence.sh JOB_UUID\n' >&2
  exit 1
fi
cd "$(git rev-parse --show-toplevel)"
docker compose exec -T postgres sh -c 'exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v jobid="$1"' sh "$job_id" <<'SQL'
SELECT j.id, j.repository_id, j.issue_number, j.status, j.attempts, j.error_code,
       j.created_at, j.started_at, j.completed_at,
       o.status AS outbox_status, o.attempts AS dispatch_attempts
FROM investigation_jobs j JOIN investigation_outbox o ON o.job_id = j.id
WHERE j.id = :'jobid';
SQL
docker compose logs --no-color --since=2h dispatcher worker | .venv/bin/python -c '
import json, sys
job = sys.argv[1]
for line in sys.stdin:
    pos = line.find("{")
    if pos < 0: continue
    try: row = json.loads(line[pos:])
    except ValueError: continue
    if row.get("job_id") == job and str(row.get("event", "")).startswith("investigation_"):
        print(json.dumps({k: row[k] for k in ("event", "job_id", "repository_id", "task_id", "level") if k in row}))
' "$job_id"
