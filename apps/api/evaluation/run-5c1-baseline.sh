#!/bin/bash
# Read-only replay against the retained 4F fixture. Never creates or modifies a database snapshot.
set -euo pipefail
set +x
umask 077
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
mode="${1:-baseline}"
case "$mode" in baseline|candidates|production|paired) ;; *) printf 'Use baseline, candidates, production or paired.\n' >&2; exit 1;; esac
python="$repo_root/.venv/bin/python"
if [ ! -x "$python" ]; then
  printf 'Project Python is missing or not executable: %s\n' "$python" >&2
  exit 1
fi
container='repopilot-4f-disposable-4f762b71ae8d9569'
database='repopilot_4f_disposable_4f762b71ae8d9569'
unset REPOPILOT_5C1_FIXTURE_SUFFIX
if [ "$mode" = paired ]; then
  suffix="${2:-}"
  if ! [[ "$suffix" =~ ^[0-9a-f]{16}$ ]]; then
    printf 'Paired replay requires the 16-character suffix of a completed new 4F fixture.\n' >&2
    exit 1
  fi
  container="repopilot-4f-disposable-${suffix}"
  database="repopilot_4f_disposable_${suffix}"
  export REPOPILOT_5C1_FIXTURE_SUFFIX="$suffix"
  test -f "apps/api/evaluation/4f-issue-report-v1-${suffix}.json" || { printf 'Completed fixture report is missing.\n' >&2; exit 1; }
fi
if ! purpose="$(docker inspect --format '{{index .Config.Labels "repopilot-purpose"}}' "$container")" ||
   [ "$purpose" != '4f-evaluation' ]; then
  printf 'The previously retained 4F disposable container is unavailable; no snapshot was created.\n' >&2
  exit 1
fi
if [ "$(docker inspect --format '{{.State.Running}}' "$container")" != true ]; then
  printf 'Starting the retained 4F disposable container: %s\n' "$container"
  docker start "$container" >/dev/null
fi
ready=false
for attempt in {1..60}; do
  if docker exec "$container" pg_isready -q -U repopilot_fixture -d "$database"; then ready=true; break; fi
  sleep 1
done
if [ "$ready" != true ]; then printf 'The retained disposable database is not ready.\n' >&2; exit 1; fi
docker exec "$container" sh -c 'test "$POSTGRES_USER" = repopilot_fixture'
if [ "$(docker exec "$container" sh -c 'printf %s "$POSTGRES_DB"')" != "$database" ]; then
  printf 'Unexpected fixture database.\n' >&2; exit 1
fi
port="$(docker port "$container" 5432/tcp | sed -n 's/^127\.0\.0\.1://p')"
case "$port" in ''|*[!0-9]*) printf 'Unexpected disposable database port.\n' >&2; exit 1;; esac
task_password="$(docker exec "$container" sh -c 'printf %s "$POSTGRES_PASSWORD"')"
case "$task_password" in ''|*[!0-9a-f]*) printf 'Unexpected disposable database credentials.\n' >&2; exit 1;; esac
if [ "${#task_password}" -ne 48 ]; then printf 'Unexpected disposable database credentials.\n' >&2; exit 1; fi
export DATABASE_URL="postgresql+psycopg://repopilot_fixture:${task_password}@127.0.0.1:${port}/${database}"
unset task_password TEST_DATABASE_URL PYTHONOPTIMIZE OPENAI_API_KEY EMBEDDING_API_KEY
unset INVESTIGATION_OPENAI_API_KEY INVESTIGATION_OPENAI_ORGANIZATION INVESTIGATION_OPENAI_PROJECT
unset INVESTIGATION_EXPERIMENT_ID
export APP_ENV=test EMBEDDING_PROVIDER=disabled EMBEDDING_ALLOW_PAID=false
export INVESTIGATION_PROVIDER=mock INVESTIGATION_REAL_ENABLED=false INVESTIGATION_PAID_BACKGROUND_ENABLED=false
export INVESTIGATION_COUNT_EXTERNAL_ENABLED=false
export REPOPILOT_5C1_RUN_ID="$("$python" -c 'import secrets; print(secrets.token_hex(8))')"
export REPOPILOT_5C1_MODE="$mode"
cd "$repo_root/apps/api"
"$python" - <<'PY'
import json, os
from pathlib import Path
from unittest.mock import patch
import httpx
from sqlalchemy.engine import make_url
from app.evaluation.provider_harness import network_fence
from app.evaluation.compare_issue_retrieval import compare, markdown
from app.evaluation.issue_retrieval_replay import _safe_output, main

def deny_http(*args, **kwargs):
    raise AssertionError('external_http_transport_forbidden')

with (network_fence(make_url(os.environ['DATABASE_URL']).port),
      patch.object(httpx.HTTPTransport, 'handle_request', deny_http),
      patch.object(httpx.AsyncHTTPTransport, 'handle_async_request', deny_http)):
    mode, run = os.environ['REPOPILOT_5C1_MODE'], os.environ['REPOPILOT_5C1_RUN_ID']
    strategies = (('baseline', 'production-v2') if mode == 'paired' else
                  ('body', 'body-filtered', 'body-first') if mode == 'candidates' else
                  ('production-v2',) if mode == 'production' else ('baseline',))
    baseline = Path(f'evaluation/5c1-baseline-{run}.json' if mode == 'paired'
                    else 'evaluation/5c1-baseline-eda70e4b43a14eb6.json')
    if mode in ('candidates', 'production') and not baseline.is_file():
        raise SystemExit('The verified baseline artifact is missing; run the baseline first.')
    for strategy in strategies:
        os.environ['REPOPILOT_5C1_STRATEGY'] = strategy
        main()
        if mode in ('candidates', 'production') or (mode == 'paired' and strategy == 'production-v2'):
            candidate = Path(f'evaluation/5c1-{strategy}-{run}.json')
            result = compare(json.loads(baseline.read_bytes()), json.loads(candidate.read_bytes()))
            prefix = Path(f'evaluation/5c1-comparison-{strategy}-{run}')
            _safe_output(prefix.with_suffix('.json'), json.dumps(result, indent=2) + '\n')
            _safe_output(prefix.with_suffix('.md'), markdown(result))
            print(f'Comparison saved: {prefix}.json and {prefix}.md')
PY
