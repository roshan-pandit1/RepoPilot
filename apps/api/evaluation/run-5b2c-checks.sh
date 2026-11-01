#!/bin/bash
# Fake-only token-count and PostgreSQL regression; the new container and volume are retained.
set -euo pipefail
umask 077
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
python="$repo_root/.venv/bin/python"
test -x "$python"
run_id="$("$python" -c 'import secrets; print(secrets.token_hex(8))')"
log="$repo_root/apps/api/evaluation/5b2c-${run_id}.log"
( set -o noclobber; : > "$log" )
exec > >(tee -a "$log") 2>&1
finish() {
  result=$?
  trap - EXIT
  printf 'Script final exit status: %s; run: %s; log: %s\n' "$result" "$run_id" "$log"
  exit "$result"
}
trap finish EXIT
docker image inspect pgvector/pgvector:pg16 >/dev/null
export POSTGRES_USER=repopilot_fixture
export POSTGRES_DB="repopilot_5b2b_${run_id}"
export POSTGRES_PASSWORD="$("$python" -c 'import secrets; print(secrets.token_hex(24))')"
container="repopilot-5b2c-${run_id}"
export GIT_NO_LAZY_FETCH=1 GIT_ALLOW_PROTOCOL='' GIT_TERMINAL_PROMPT=0
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_COUNT=1
export GIT_CONFIG_KEY_0=protocol.allow GIT_CONFIG_VALUE_0=never
git cat-file -e '30705da4c044192cab4ac207e253ab8e8a1bd100^{commit}'
docker run --pull=never -d --name "$container" --label repopilot-purpose=5b2c-fake-tests \
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
source_fingerprint() {
  "$python" - <<'PY'
import hashlib
from pathlib import Path
roots = (Path('app'), Path('tests'), Path('alembic'))
paths = sorted({p for root in roots for p in root.rglob('*.py') if p.is_file()}
    | {Path('alembic.ini'), Path('pyproject.toml'), Path('evaluation/run-5b2c-checks.sh'),
       Path('evaluation/adversarial-report-v1.json'), Path('evaluation/issue-report-v1.json')})
h = hashlib.sha256()
for path in paths:
    data = path.read_bytes()
    h.update(str(path).encode() + b'\0' + len(data).to_bytes(8, 'big') + data)
print(h.hexdigest(), len(paths))
PY
}
before="$(source_fingerprint)"
printf 'Test source fingerprint before: %s; Git HEAD: %s\n' "$before" "$(git rev-parse HEAD)"
"$python" - <<'PY'
import os, re
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
url = make_url(os.environ['TEST_DATABASE_URL'])
if (url.get_backend_name() != 'postgresql' or url.host != '127.0.0.1' or not url.port
        or url.username != 'repopilot_fixture' or url.query
        or not re.fullmatch(r'repopilot_5b2b_[0-9a-f]{16}', url.database or '')):
    raise SystemExit('Refusing unexpected database target.')
with create_engine(url, hide_parameters=True).connect() as db:
    name = db.execute(text('select current_database()')).scalar_one()
    if name != url.database or db.execute(text("select count(*) from pg_tables where schemaname='public'")).scalar_one():
        raise SystemExit('Refusing nonempty or unexpected database.')
    print(f'Confirmed empty dedicated database: {name}; host port={url.port}')
PY
"$python" - <<'PYTEST'
import os, sys
import pytest
from sqlalchemy.engine import make_url
from app.evaluation.provider_harness import network_fence

class Required:
    def __init__(self): self.cases = {}
    def pytest_runtest_logreport(self, report):
        if report.when == 'call': self.cases[report.nodeid] = report.outcome
    def pytest_sessionfinish(self, session, exitstatus):
        reporter = session.config.pluginmanager.get_plugin('terminalreporter')
        required = ('test_postgres_concurrent_count_approval_consumption',
            'test_postgres_concurrent_counted_generation_publishes_once',
            'test_counted_generation_rejects_changed_body_at_send_marker[model]',
            'test_counted_generation_rejects_changed_body_at_send_marker[instructions]',
            'test_counted_generation_rejects_changed_body_at_send_marker[input]',
            'test_counted_generation_rejects_changed_body_at_send_marker[schema]',
            'test_counted_generation_rejects_changed_body_at_send_marker[cache]',
            'test_counted_generation_rejects_changed_body_at_send_marker[output_limit]',
            'test_counted_generation_rejects_changed_body_at_send_marker[truncation]',
            'test_counted_generation_rejects_changed_body_at_send_marker[tier]',
            'test_counted_generation_rejects_changed_body_at_send_marker[store]',
            'test_expired_or_excessive_count_blocks_fake_generation_before_reservation[expired]',
            'test_expired_or_excessive_count_blocks_fake_generation_before_reservation[excessive]',
            'test_successful_fake_count_does_not_clear_unknown_actual_pricing',
            'test_completed_count_does_not_allow_duplicate_generation_approval',
            'test_stress_capacity_fails_closed_for_value_beyond_postgres_bigint',
            'test_fake_count_is_one_use_and_does_not_touch_generation_or_ledger',
            'test_counted_fake_generation_still_requires_separate_approval_and_full_reservation',
            'test_count_invalidation_before_generation_send_marker_prevents_publication',
            'test_changed_access_or_source_before_generation_marker_blocks_send',
            'test_count_approval_cannot_authorize_generation_or_live_transport',
            'test_postgres_approval_send_marker_is_atomic_under_concurrency',
            'test_postgres_concurrent_reservation_cannot_overspend[budget]',
            'test_postgres_concurrent_reservation_cannot_overspend[concurrency]',
            'test_postgres_stress_guard_does_not_promote_or_record_paid_approval',
            'test_postgres_legacy_job_survives_migration')
        if (exitstatus != 0 or session.testscollected < 200
                or any(reporter.stats.get(x, []) for x in ('failed', 'skipped', 'error'))
                or not all(any(name in node and outcome == 'passed' for node, outcome in self.cases.items())
                           for name in required)):
            print('Disposable verification incomplete: failed, skipped or missing required cases.')
            session.exitstatus = pytest.ExitCode.TESTS_FAILED

with network_fence(make_url(os.environ['TEST_DATABASE_URL']).port):
    status = pytest.main(['-q', '-ra', '--tb=no', '--show-capture=no',
        'tests/test_token_counting.py', 'tests/test_pricing_gate.py', 'tests/test_experiment_executor.py',
        'tests/test_experiment_preparation.py', 'tests/test_real_report_foundation.py',
        'tests/test_adversarial_workflow.py', 'tests/test_adversarial_evaluation.py',
        'tests/test_report_model.py', 'tests/test_investigation_reports.py',
        'tests/test_investigation_evidence.py', 'tests/test_investigation_migration.py'], plugins=[Required()])
sys.exit(status)
PYTEST
"$python" - <<'PY'
from pathlib import Path
from app.evaluation.adversarial import evaluate
r = evaluate(Path('evaluation/adversarial-report-v1.json').read_bytes())
print(f"Security fixture: {r['passed']}/{r['case_count']} passed; SHA-256={r['dataset_sha256']}")
if r['failed'] or r['passed'] != r['case_count']: raise SystemExit('Security fixture failed.')
PY
unset TEST_DATABASE_URL
"$repo_root/.venv/bin/ruff" check .
"$repo_root/.venv/bin/alembic" upgrade head
"$repo_root/.venv/bin/alembic" current
"$repo_root/.venv/bin/alembic" check
git diff --check
after="$(source_fingerprint)"
if [ "$before" != "$after" ]; then printf 'Source changed during verification.\n' >&2; exit 1; fi
printf 'Test source fingerprint after: %s\n' "$after"
printf 'Completed fake-only token-count PostgreSQL verification: %s\n' "$run_id"
printf 'Container and volume retained: %s\n' "$container"
