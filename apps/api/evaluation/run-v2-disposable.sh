#!/bin/bash
# Creates a NEW isolated container and database; it never connects to Compose services.
set -euo pipefail
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
commit=956a4f92983b222ce179891bbde39cb49a2022b2
git cat-file -e "$commit^{commit}"
# Evaluation helper files may be uncommitted; application behavior must match the checkpoint.
git diff --quiet "$commit" -- apps/api/app/modules apps/api/app/workers apps/api/app/domain apps/api/app/api apps/api/app/core apps/api/app/infra apps/api/app/main.py apps/api/alembic
python="$repo_root/.venv/bin/python"
test -x "$python"
docker image inspect pgvector/pgvector:pg16 >/dev/null
suffix="$("$python" -c 'import secrets; print(secrets.token_hex(8))')"
export POSTGRES_USER=repopilot_fixture
export POSTGRES_DB="repopilot_c3_disposable_${suffix}"
export POSTGRES_PASSWORD="$("$python" -c 'import secrets; print(secrets.token_hex(24))')"
container="repopilot-c3-disposable-${suffix}"
# No bind mount or existing volume; fail if the known local image is absent.
docker run --pull=never -d --name "$container" --label repopilot-purpose=c3-disposable \
  -e POSTGRES_USER -e POSTGRES_DB -e POSTGRES_PASSWORD \
  -p 127.0.0.1::5432 pgvector/pgvector:pg16 >/dev/null
printf 'New disposable container: %s; new database: %s\n' "$container" "$POSTGRES_DB"
ready=false
for attempt in {1..60}; do
  if docker exec "$container" pg_isready -q -U "$POSTGRES_USER" -d "$POSTGRES_DB"; then ready=true; break; fi
  sleep 1
done
if [ "$ready" != true ]; then printf 'Database failed to become ready; container retained.\n' >&2; exit 1; fi
port="$(docker port "$container" 5432/tcp | sed -n 's/^127\.0\.0\.1://p')"
case "$port" in ''|*[!0-9]*) printf 'Unexpected published port; stopping.\n' >&2; exit 1;; esac
export DATABASE_URL="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:${port}/${POSTGRES_DB}"
export TEST_DATABASE_URL="$DATABASE_URL"
export APP_ENV=test GITHUB_WEBHOOK_SECRET='test-only-webhook-secret-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
export EMBEDDING_PROVIDER=disabled EMBEDDING_ALLOW_PAID=false GITHUB_OAUTH_ENABLED=false DEMO_AUTH_ENABLED=false
export REPOPILOT_GIT_ROOT="$repo_root"
cd apps/api
"$python" - <<'PY'
import os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
u = make_url(os.environ['TEST_DATABASE_URL'])
assert u.host == '127.0.0.1' and u.database == os.environ['POSTGRES_DB']
assert u.database.startswith('repopilot_c3_disposable_')
with create_engine(u).connect() as c:
    name, addr, port = c.execute(text('select current_database(), inet_server_addr()::text, inet_server_port()')).one()
    assert name == u.database
    assert c.execute(text("select count(*) from pg_tables where schemaname = 'public'")).scalar_one() == 0
    print(f'Confirmed empty dedicated database: {name}; server={addr}:{port}; host port={u.port}')
PY
"$python" -m pytest -q -ra
unset TEST_DATABASE_URL
"$repo_root/.venv/bin/ruff" check .
"$repo_root/.venv/bin/alembic" upgrade head
"$repo_root/.venv/bin/alembic" current
"$repo_root/.venv/bin/alembic" check
"$python" -m app.evaluation.verify_labels evaluation/repopilot-v2-956a4f9.json
"$python" -m app.evaluation.v2_disposable
git diff --check
printf 'Container and its new data volume retained: %s\n' "$container"
