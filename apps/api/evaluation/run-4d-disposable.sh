#!/bin/bash
# Creates a NEW isolated container and database; it never connects to Compose services.
set -euo pipefail
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
python="$repo_root/.venv/bin/python"
test -x "$python"
docker image inspect pgvector/pgvector:pg16 >/dev/null
suffix="$("$python" -c 'import secrets; print(secrets.token_hex(8))')"
export POSTGRES_USER=repopilot_fixture
export POSTGRES_DB="repopilot_4d_disposable_${suffix}"
export POSTGRES_PASSWORD="$("$python" -c 'import secrets; print(secrets.token_hex(24))')"
container="repopilot-4d-disposable-${suffix}"
# No bind mount or existing volume; fail if the known local image is absent.
docker run --pull=never -d --name "$container" --label repopilot-purpose=4d-disposable \
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
unset REPOPILOT_4C_EVAL_PREFIX
export REPOPILOT_4D_EVAL_PREFIX="$repo_root/apps/api/evaluation/4d-evaluation-local"
cd apps/api
"$python" - <<'PY'
import os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
u = make_url(os.environ['TEST_DATABASE_URL'])
assert u.host == '127.0.0.1' and u.database == os.environ['POSTGRES_DB']
assert u.database.startswith('repopilot_4d_disposable_')
with create_engine(u).connect() as c:
    name, addr, port = c.execute(text('select current_database(), inet_server_addr()::text, inet_server_port()')).one()
    assert name == u.database
    assert c.execute(text("select count(*) from pg_tables where schemaname = 'public'")).scalar_one() == 0
    print(f'Confirmed empty dedicated database: {name}; server={addr}:{port}; host port={u.port}')
PY
"$python" - <<'PYTEST'
import sys
import pytest

class RequireAllTests:
    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session, exitstatus):
        reporter = session.config.pluginmanager.get_plugin('terminalreporter')
        if reporter and reporter.stats.get('skipped'):
            print('Disposable verification incomplete: skipped tests; stopping before application migration.')
            session.exitstatus = pytest.ExitCode.TESTS_FAILED

sys.exit(pytest.main(['-q', '-ra'], plugins=[RequireAllTests()]))
PYTEST
node --test "$repo_root/apps/api/evaluation/test-4d-live-check.mjs"
unset TEST_DATABASE_URL
"$repo_root/.venv/bin/ruff" check .
"$repo_root/.venv/bin/alembic" upgrade head
"$repo_root/.venv/bin/alembic" current
"$repo_root/.venv/bin/alembic" check
git diff --check
printf 'Evaluation report (synthetic mock cases; no AI reasoning):\n'
cat evaluation/4d-evaluation-local.md
printf 'Container and its new data volume retained: %s\n' "$container"
