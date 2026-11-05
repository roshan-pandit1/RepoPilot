#!/bin/bash
# Disposable PostgreSQL regression. Does not publish a committed-source snapshot.
set -euo pipefail
set +x
umask 077
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
python="$repo_root/.venv/bin/python"
if [ ! -x "$python" ]; then
  printf 'Project Python is missing or not executable: %s\n' "$python" >&2
  exit 1
fi
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
"$python" -m app.evaluation.disposable_regression
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
