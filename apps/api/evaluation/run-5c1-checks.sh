#!/bin/bash
# Disposable PostgreSQL regression. Does not publish a committed-source snapshot.
set -euo pipefail
set +x
umask 077
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
python="$repo_root/.venv/bin/python"
test -x "$python"
run_id="$("$python" -c 'import secrets; print(secrets.token_hex(8))')"
log="$repo_root/apps/api/evaluation/5c1-checks-${run_id}.log"
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
# Existing isolated-executor regression fixtures require this dedicated database prefix.
export POSTGRES_DB="repopilot_5b2b_${run_id}"
export POSTGRES_PASSWORD="$("$python" -c 'import secrets; print(secrets.token_hex(24))')"
container="repopilot-5c1-checks-${run_id}"
export GIT_NO_LAZY_FETCH=1 GIT_ALLOW_PROTOCOL='' GIT_TERMINAL_PROMPT=0
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_COUNT=1
export GIT_CONFIG_KEY_0=protocol.allow GIT_CONFIG_VALUE_0=never
docker run --pull=never -d --name "$container" --label repopilot-purpose=5c1-checks \
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
export INVESTIGATION_COUNT_EXTERNAL_ENABLED=false
unset INVESTIGATION_OPENAI_API_KEY INVESTIGATION_OPENAI_ORGANIZATION INVESTIGATION_OPENAI_PROJECT
unset INVESTIGATION_EXPERIMENT_ID EMBEDDING_API_KEY OPENAI_API_KEY
unset PYTHONOPTIMIZE PYTEST_ADDOPTS PYTEST_PLUGINS REPOPILOT_4C_EVAL_PREFIX REPOPILOT_4D_EVAL_PREFIX REPOPILOT_4F_APPROVED_COMMIT
cd "$repo_root/apps/api"
source_fingerprint() {
  "$python" - <<'PY'
import hashlib
from pathlib import Path
roots = (Path('app'), Path('tests'), Path('alembic'))
paths = sorted({p for root in roots for p in root.rglob('*.py') if p.is_file()}
    | {Path('alembic.ini'), Path('pyproject.toml'), Path('evaluation/run-5c1-checks.sh'),
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
from unittest.mock import patch
import httpx
import pytest
from sqlalchemy.engine import make_url
from app.evaluation.provider_harness import network_fence

class Required:
    def __init__(self): self.cases = {}
    def pytest_runtest_logreport(self, report):
        if report.when == 'call': self.cases[report.nodeid] = report.outcome
    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session, exitstatus):
        reporter = session.config.pluginmanager.get_plugin('terminalreporter')
        required = ('test_postgres_search_returns_commit_citation',
            'test_postgres_keyword_search_handles_natural_language_and_identifiers',
            'test_postgres_keyword_camelcase_and_bounded_results',
            'test_postgres_v2_retrieval_deduplicates_and_fences_source',
            'test_queued_v1_job_keeps_legacy_queries_and_ranking',
            'test_v2_keeps_exact_symbols_and_adds_filtered_body_terms',
            'test_v2_stack_trace_identifier_and_vague_input_are_bounded',
            'test_snapshot_job_evidence_is_atomic_fenced_and_idempotent',
            'test_reindex_after_submit_never_switches_snapshot',
            'test_access_revoked_before_and_after_persistence',
            'test_cross_tenant_and_unauthenticated_evidence',
            'test_readonly_replay_rejects_mutations_and_write_locks',
            'test_comparison_rejects_mixed_provenance',
            'test_postgres_legacy_job_survives_migration')
        if (exitstatus != 0 or session.testscollected < 200
                or any(reporter.stats.get(x, []) for x in ('failed', 'skipped', 'error'))
                or not all(any(name in node and outcome == 'passed' for node, outcome in self.cases.items())
                           for name in required)):
            print('Disposable verification incomplete: failed, skipped or missing required cases.')
            session.exitstatus = pytest.ExitCode.TESTS_FAILED

def deny_http(*args, **kwargs):
    raise AssertionError('external_http_transport_forbidden')

with (network_fence(make_url(os.environ['TEST_DATABASE_URL']).port),
      patch.object(httpx.HTTPTransport, 'handle_request', deny_http),
      patch.object(httpx.AsyncHTTPTransport, 'handle_async_request', deny_http)):
    # This committed-Git snapshot publication is separately approval-gated.
    status = pytest.main(['-q', '-ra', '--tb=short', '--show-capture=no',
        '--ignore=tests/test_investigation_evaluation_pg.py'], plugins=[Required()])
sys.exit(status)
PYTEST
"$python" - <<'PY'
from pathlib import Path
from app.evaluation.adversarial import evaluate
result = evaluate(Path('evaluation/adversarial-report-v1.json').read_bytes())
print(f"Security fixture: {result['passed']}/{result['case_count']} passed; SHA-256={result['dataset_sha256']}")
if result['failed'] or result['passed'] != result['case_count']: raise SystemExit('Security fixture failed.')
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
printf 'Completed disposable PostgreSQL regression: %s\n' "$run_id"
printf 'Container and volume retained: %s\n' "$container"
