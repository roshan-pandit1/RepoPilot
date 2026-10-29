#!/bin/bash
# Republish the existing completed task; this does not submit or create another job.
set -euo pipefail
job_id="${1:-}"
if [[ ! "$job_id" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]]; then
  printf 'Usage: bash apps/api/evaluation/investigation-replay.sh JOB_UUID\n' >&2
  exit 1
fi
cd "$(git rev-parse --show-toplevel)"
state="$(docker compose exec -T postgres sh -c 'exec psql -X -qAt -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v jobid="$1"' sh "$job_id" <<'SQL'
SELECT status FROM investigation_jobs WHERE id = :'jobid' AND repository_id = 1435878031 AND issue_number = 1;
SQL
)"
[ "$state" = completed ] || { printf 'Job is not the completed authorized issue #1 job; no replay sent.\n' >&2; exit 1; }
docker compose exec -T worker celery -A app.workers.tasks call investigate_issue --args "[\"$job_id\"]"
printf 'Duplicate task sent for existing job; allow the worker to consume it before checking evidence.\n'
