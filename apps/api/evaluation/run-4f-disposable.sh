#!/bin/bash
# Run only after separate approval to build this committed-source snapshot.
set -euo pipefail
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
docker image inspect pgvector/pgvector:pg16 >/dev/null
suffix="$("$python" -c 'import secrets; print(secrets.token_hex(8))')"
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
unset TEST_DATABASE_URL PYTHONOPTIMIZE
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
"$python" -m app.evaluation.issue_report_disposable
printf 'Container and its new data volume retained: %s\n' "$container"
