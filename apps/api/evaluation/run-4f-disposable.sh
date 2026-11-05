#!/bin/bash
# Run only after separate approval to build this committed-source snapshot.
set -euo pipefail
set +x
umask 077
commit=30705da4c044192cab4ac207e253ab8e8a1bd100
if [ "${REPOPILOT_4F_APPROVED_COMMIT:-}" != "$commit" ]; then
  printf 'Separate approval for the exact 4F disposable source snapshot is required.\n' >&2
  exit 1
fi
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
python="$repo_root/.venv/bin/python"
test -x "$python"
git cat-file -e "${commit}^{commit}"
cd "$repo_root/apps/api"
"$python" - <<'PY'
import hashlib, json
from pathlib import Path
from app.evaluation.git_source import GitSource
from app.evaluation.issue_report import verify_dataset
from app.modules.ingestion.code_snapshot import plan_snapshot

raw = Path('evaluation/issue-report-v1.json').read_bytes()
dataset = json.loads(raw)
if (hashlib.sha256(raw).hexdigest() != '416cbf9e46b9399cf78d118f581a882d16cf512da439d352d3af29674c447bf6'
        or dataset.get('repository') != 'roshan-pandit1/RepoPilot'
        or dataset.get('commit_sha') != '30705da4c044192cab4ac207e253ab8e8a1bd100'):
    raise SystemExit('Fixture dataset or approved source mismatch.')
result = verify_dataset(dataset, Path('../..'))
if (result['cases'], result['scored_cases'], result['unscored_cases'], result['labels']) != (19, 16, 3, 23):
    raise SystemExit('Fixture case or label count mismatch.')
plan = plan_snapshot(GitSource(Path('../..'), dataset['commit_sha'], dataset['repository']), '', dataset['repository'])
manifest = ''.join(f'{f.path}\t{f.blob_sha}\t{f.size}\n' for f in plan.files).encode()
print(f"Verified approved source: {len(plan.files)} eligible Python files; {result['labels']} labels; "
      f"selected manifest SHA-256 {hashlib.sha256(manifest).hexdigest()}")
PY
cd "$repo_root"
docker image inspect pgvector/pgvector:pg16 >/dev/null
suffix="$("$python" -c 'import secrets; print(secrets.token_hex(8))')"
log="$repo_root/apps/api/evaluation/4f-fixture-${suffix}.log"
( set -o noclobber; : > "$log" )
exec > >(tee -a "$log") 2>&1
finish() {
  result=$?
  trap - EXIT
  printf 'Script final exit status: %s; run: %s; log: %s\n' "$result" "$suffix" "$log"
  exit "$result"
}
trap finish EXIT
export POSTGRES_USER=repopilot_fixture
export POSTGRES_DB="repopilot_4f_disposable_${suffix}"
export POSTGRES_PASSWORD="$("$python" -c 'import secrets; print(secrets.token_hex(24))')"
container="repopilot-4f-disposable-${suffix}"
docker run --pull=never -d --name "$container" --label repopilot-purpose=4f-evaluation \
  -e POSTGRES_USER -e POSTGRES_DB -e POSTGRES_PASSWORD \
  -p 127.0.0.1::5432 pgvector/pgvector:pg16 >/dev/null
printf 'New disposable container: %s; new database: %s\n' "$container" "$POSTGRES_DB"
ready=false
for attempt in {1..60}; do
  if docker exec "$container" pg_isready -q -U "$POSTGRES_USER" -d "$POSTGRES_DB"; then ready=true; break; fi
  sleep 1
done
if [ "$ready" != true ]; then printf 'Database not ready; container retained.\n' >&2; exit 1; fi
port="$(docker port "$container" 5432/tcp | sed -n 's/^127\.0\.0\.1://p')"
case "$port" in ''|*[!0-9]*) printf 'Unexpected published port; stopping.\n' >&2; exit 1;; esac
export DATABASE_URL="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:${port}/${POSTGRES_DB}"
export REPOPILOT_4F_DB="$POSTGRES_DB"
export REPOPILOT_4F_OUTPUT="$repo_root/apps/api/evaluation/4f-issue-report-v1-${suffix}"
export REPOPILOT_GIT_ROOT="$repo_root"
export APP_ENV=test GITHUB_WEBHOOK_SECRET='test-only-webhook-secret-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
export EMBEDDING_PROVIDER=disabled EMBEDDING_ALLOW_PAID=false GITHUB_OAUTH_ENABLED=false DEMO_AUTH_ENABLED=false
export INVESTIGATION_PROVIDER=mock INVESTIGATION_REAL_ENABLED=false INVESTIGATION_PAID_BACKGROUND_ENABLED=false
export INVESTIGATION_COUNT_EXTERNAL_ENABLED=false
export GIT_NO_LAZY_FETCH=1 GIT_ALLOW_PROTOCOL='' GIT_TERMINAL_PROMPT=0
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_COUNT=1
export GIT_CONFIG_KEY_0=protocol.allow GIT_CONFIG_VALUE_0=never
unset TEST_DATABASE_URL PYTHONOPTIMIZE OPENAI_API_KEY EMBEDDING_API_KEY
unset INVESTIGATION_OPENAI_API_KEY INVESTIGATION_OPENAI_ORGANIZATION INVESTIGATION_OPENAI_PROJECT INVESTIGATION_EXPERIMENT_ID
cd "$repo_root/apps/api"
"$python" - <<'PY'
import os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
u = make_url(os.environ['DATABASE_URL'])
assert u.host == '127.0.0.1' and u.database == os.environ['REPOPILOT_4F_DB']
assert u.database.startswith('repopilot_4f_disposable_') and not u.query
with create_engine(u, hide_parameters=True).connect() as c:
    name, addr, port = c.execute(text('select current_database(), inet_server_addr()::text, inet_server_port()')).one()
    assert name == u.database
    assert c.execute(text("select count(*) from pg_tables where schemaname = 'public'")).scalar_one() == 0
    print(f'Confirmed empty dedicated database: {name}; server={addr}:{port}; host port={u.port}')
PY
"$python" -m app.evaluation.issue_report
"$repo_root/.venv/bin/alembic" upgrade head
"$repo_root/.venv/bin/alembic" current
"$repo_root/.venv/bin/alembic" check
"$python" - <<'PY'
import os
from unittest.mock import patch
import httpx
from sqlalchemy.engine import make_url
from app.evaluation.provider_harness import network_fence
from app.evaluation.issue_report_disposable import main

def deny_http(*args, **kwargs):
    raise AssertionError('external_http_transport_forbidden')

with (network_fence(make_url(os.environ['DATABASE_URL']).port),
      patch.object(httpx.HTTPTransport, 'handle_request', deny_http),
      patch.object(httpx.AsyncHTTPTransport, 'handle_async_request', deny_http)):
    main()
PY
printf 'Container and its new data volume retained: %s\n' "$container"
