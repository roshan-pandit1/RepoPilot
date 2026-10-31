#!/bin/bash
# Test-only: a fresh PostgreSQL container, synthetic GitHub and fake model transport.
set -euo pipefail
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
python="$repo_root/.venv/bin/python"
test -x "$python"
docker image inspect pgvector/pgvector:pg16 >/dev/null
run_id="$("$python" -c 'import secrets; print(secrets.token_hex(8))')"
log="$repo_root/apps/api/evaluation/5b2a-$run_id.log"
( set -o noclobber; : > "$log" )
exec > >(tee -a "$log") 2>&1
export POSTGRES_USER=repopilot_fixture
export POSTGRES_DB="repopilot_5b2a_${run_id}"
export POSTGRES_PASSWORD="$("$python" -c 'import secrets; print(secrets.token_hex(24))')"
container="repopilot-5b2a-${run_id}"
export REPOPILOT_5B2A_RUN_ID="$run_id" REPOPILOT_GIT_ROOT="$repo_root"
export GIT_NO_LAZY_FETCH=1 GIT_ALLOW_PROTOCOL='' GIT_TERMINAL_PROMPT=0
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_COUNT=1
export GIT_CONFIG_KEY_0=protocol.allow GIT_CONFIG_VALUE_0=never
git cat-file -e '30705da4c044192cab4ac207e253ab8e8a1bd100^{commit}'
docker run --pull=never -d --name "$container" --label repopilot-purpose=5b2a-evaluation \
  -e POSTGRES_USER -e POSTGRES_DB -e POSTGRES_PASSWORD \
  -p 127.0.0.1::5432 pgvector/pgvector:pg16 >/dev/null
printf 'New disposable container: %s; database: %s; run: %s\n' "$container" "$POSTGRES_DB" "$run_id"
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
unset INVESTIGATION_OPENAI_API_KEY INVESTIGATION_EXPERIMENT_ID EMBEDDING_API_KEY OPENAI_API_KEY
unset PYTHONOPTIMIZE PYTEST_ADDOPTS PYTEST_PLUGINS REPOPILOT_4C_EVAL_PREFIX REPOPILOT_4D_EVAL_PREFIX REPOPILOT_4F_APPROVED_COMMIT
cd "$repo_root/apps/api"
"$python" - <<'PY'
import os
from sqlalchemy import create_engine, text
from app.evaluation.provider_harness import safe_url
url = safe_url(os.environ['TEST_DATABASE_URL'], os.environ['REPOPILOT_5B2A_RUN_ID'])
with create_engine(url, hide_parameters=True).connect() as db:
    name, address, port = db.execute(text('select current_database(), inet_server_addr()::text, inet_server_port()')).one()
    if name != url.database or db.execute(text("select count(*) from pg_tables where schemaname = 'public'")).scalar_one():
        raise SystemExit('Refusing nonempty or unexpected database.')
    print(f'Confirmed empty dedicated database: {name}; server={address}:{port}; host port={url.port}')
PY
"$python" - <<'PYTEST'
import json
import os
import sys
from pathlib import Path
import pytest

class RequireFullSuite:
    def __init__(self):
        self.provider_cases = {}

    def pytest_runtest_logreport(self, report):
        if report.when == 'call' and report.nodeid.startswith('tests/test_real_report_foundation.py::'):
            self.provider_cases[report.nodeid.split('::', 1)[1]] = report.outcome

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session, exitstatus):
        reporter = session.config.pluginmanager.get_plugin('terminalreporter')
        counts = {name: len(reporter.stats.get(name, [])) for name in ('passed', 'failed', 'skipped', 'error')}
        required = {'test_postgres_actual_mode_uses_only_injected_transport',
                    'test_postgres_concurrent_reservation_cannot_overspend[budget]',
                    'test_postgres_concurrent_reservation_cannot_overspend[concurrency]',
                    'test_worker_interrupt_after_send_cannot_retry_provider',
                    'test_uncited_hypothesis_with_evidence_is_labeled_unsupported'}
        failure_cases = ('malformed', 'foreign', 'timeout', 'missing_usage', 'unexpected_model',
                         'unexpected_tier', 'refusal', 'incomplete', 'usage_exceeded',
                         'connection_failure', 'duplicate_envelope', 'unexpected_cache')
        required.update('test_bad_response_or_unknown_billing_never_publishes_or_retries[' + name + ']'
                        for name in failure_cases)
        ok = (exitstatus == 0 and not counts['failed'] and not counts['skipped'] and not counts['error']
              and session.testscollected >= 300 and all(self.provider_cases.get(name) == 'passed' for name in required))
        result = {'run_id': os.environ['REPOPILOT_5B2A_RUN_ID'], 'database': os.environ['POSTGRES_DB'],
                  'collected': session.testscollected, 'exit_code': 0 if ok else 1, **counts,
                  'provider_cases': self.provider_cases,
                  'excluded': ['tests/test_investigation_evaluation_pg.py']}
        path = Path('evaluation') / f"5b2a-{result['run_id']}-pytest.json"
        with path.open('x') as output:
            json.dump(result, output, indent=2)
            output.write('\n')
        if not ok:
            print('Disposable verification incomplete: failed, skipped, or insufficient tests.')
            session.exitstatus = pytest.ExitCode.TESTS_FAILED

sys.exit(pytest.main(['-q', '-ra', '--tb=no', '--show-capture=no',
    '--ignore=tests/test_investigation_evaluation_pg.py'], plugins=[RequireFullSuite()]))
PYTEST
"$python" - <<'PY'
from pathlib import Path
from app.evaluation.adversarial import evaluate
result = evaluate(Path('evaluation/adversarial-report-v1.json').read_bytes())
print(f"Security fixture: {result['passed']}/{result['case_count']} passed; SHA-256={result['dataset_sha256']}")
if result['failed'] or result['passed'] != result['case_count']:
    raise SystemExit('Security fixture failed.')
PY
unset TEST_DATABASE_URL
"$repo_root/.venv/bin/ruff" check .
"$repo_root/.venv/bin/alembic" upgrade head
"$repo_root/.venv/bin/alembic" current
"$repo_root/.venv/bin/alembic" check
"$python" -m app.evaluation.provider_harness
git diff --check
printf 'Completed disposable fake-transport run: %s\n' "$run_id"
printf 'Retained container and volume: %s; log: %s\n' "$container" "$log"
