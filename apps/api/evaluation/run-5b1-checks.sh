#!/bin/bash
# Destructive fixtures run only in a new database; no committed-Git snapshot is created.
set -euo pipefail
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
python="$repo_root/.venv/bin/python"
test -x "$python"
docker image inspect pgvector/pgvector:pg16 >/dev/null
suffix="$("$python" -c 'import secrets; print(secrets.token_hex(8))')"
export POSTGRES_USER=repopilot_fixture
export POSTGRES_DB="repopilot_5b1_checks_${suffix}"
export POSTGRES_PASSWORD="$("$python" -c 'import secrets; print(secrets.token_hex(24))')"
container="repopilot-5b1-checks-${suffix}"
docker run --pull=never -d --name "$container" --label repopilot-purpose=5b1-checks \
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
export TEST_DATABASE_URL="$DATABASE_URL"
export APP_ENV=test GITHUB_WEBHOOK_SECRET='test-only-webhook-secret-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
export EMBEDDING_PROVIDER=disabled EMBEDDING_ALLOW_PAID=false GITHUB_OAUTH_ENABLED=false DEMO_AUTH_ENABLED=false
export INVESTIGATION_PROVIDER=mock INVESTIGATION_REAL_ENABLED=false INVESTIGATION_PAID_BACKGROUND_ENABLED=false
unset INVESTIGATION_OPENAI_API_KEY INVESTIGATION_EXPERIMENT_ID
export REPOPILOT_GIT_ROOT="$repo_root"
unset PYTHONOPTIMIZE PYTEST_ADDOPTS PYTEST_PLUGINS REPOPILOT_4C_EVAL_PREFIX REPOPILOT_4D_EVAL_PREFIX REPOPILOT_4F_APPROVED_COMMIT
cd "$repo_root/apps/api"
"$python" - <<'PY'
import os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
u = make_url(os.environ['TEST_DATABASE_URL'])
assert u.host == '127.0.0.1' and u.database == os.environ['POSTGRES_DB']
assert u.database.startswith('repopilot_5b1_checks_') and not u.query
with create_engine(u, hide_parameters=True).connect() as c:
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
            print('Disposable verification incomplete: skipped tests.')
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
        if session.testscollected < 300:
            print('Disposable verification incomplete: unexpectedly few tests collected.')
            session.exitstatus = pytest.ExitCode.TESTS_FAILED

# This one test publishes a committed Git snapshot and is separately approval-gated.
sys.exit(pytest.main(['-q', '-ra', '--ignore=tests/test_investigation_evaluation_pg.py'],
                     plugins=[RequireAllTests()]))
PYTEST
"$python" - <<'PY'
from pathlib import Path
from app.evaluation.adversarial import evaluate
result = evaluate(Path('evaluation/adversarial-report-v1.json').read_bytes())
print(f"Security fixture: {result['passed']}/{result['case_count']} passed; SHA-256={result['dataset_sha256']}")
assert result['failed'] == 0 and result['passed'] == result['case_count']
PY
unset TEST_DATABASE_URL
"$repo_root/.venv/bin/ruff" check .
"$repo_root/.venv/bin/alembic" upgrade 0009
"$python" - <<'PY'
from sqlalchemy import create_engine, text
import os
with create_engine(os.environ['DATABASE_URL']).begin() as c:
    c.execute(text("INSERT INTO users (id, github_user_id, login) VALUES (910000001, 910000001, 'migration_preservation_fixture')"))
PY
"$repo_root/.venv/bin/alembic" upgrade head
"$python" - <<'PY'
from sqlalchemy import create_engine, text
import os
with create_engine(os.environ['DATABASE_URL']).connect() as c:
    assert c.execute(text("SELECT login FROM users WHERE id = 910000001")).scalar_one() == 'migration_preservation_fixture'
    print('Existing 0009 fixture preserved by 0010 upgrade.')
PY
"$repo_root/.venv/bin/alembic" current
"$repo_root/.venv/bin/alembic" check
git diff --check
printf 'PostgreSQL checks passed. The committed-source snapshot test was intentionally excluded.\n'
printf 'Container and its new data volume retained: %s\n' "$container"
