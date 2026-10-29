#!/bin/bash
# Authorized by the user for this local verification. Never enable shell tracing: configuration contains secrets.
set -euo pipefail
umask 077
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
expected_hash=7ba8e5c850061f03d9f97f2eb1db5a88d9c4be311159f0dc107cdad77efbdf51
actual_hash="$(shasum -a 256 apps/api/alembic/versions/0008_investigation_evidence.py | cut -d ' ' -f 1)"
[ "$actual_hash" = "$expected_hash" ] || { printf 'Migration differs from reviewed version; stopped.\n' >&2; exit 1; }
pg_container="$(docker compose ps -q postgres)"
[ -n "$pg_container" ] || { printf 'Local Compose PostgreSQL is not running.\n' >&2; exit 1; }
[ "$(docker inspect -f '{{ index .Config.Labels "com.docker.compose.project" }}' "$pg_container")" = repopilot ] || { printf 'Unexpected Compose project; stopped.\n' >&2; exit 1; }
# Verify the container is on the expected project network.
pg_ip="$(docker inspect -f '{{with index .NetworkSettings.Networks "repopilot_default"}}{{.IPAddress}}{{end}}' "$pg_container")"
[ -n "$pg_ip" ] || { printf 'Unexpected PostgreSQL network; stopped.\n' >&2; exit 1; }
# Inspect the running application connection, never print its URL or credentials.
docker compose exec -T api python - "$pg_ip" <<'PY'
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from app.core.config import get_settings
try:
    s = get_settings()
    u = make_url(s.database_url)
    assert s.app_env == 'development' and u.get_backend_name() == 'postgresql'
    assert u.host == 'postgres' and u.port == 5432 and u.database == 'repopilot'
    assert s.embedding_provider in ('disabled', 'fake') and not s.embedding_allow_paid
    with create_engine(u).connect() as c:
        name, addr, port = c.execute(text('select current_database(), inet_server_addr()::text, inet_server_port()')).one()
        revision = c.execute(text('select version_num from alembic_version')).scalar_one()
        tables = c.execute(text("select count(*) from information_schema.tables where table_schema='public' and table_name = 'investigation_evidence'")).scalar_one()
        assert name == 'repopilot' and addr.split('/')[0] == sys.argv[1] and revision == '0007' and tables == 0
        snapshots = c.execute(text("""SELECT s.id, s.commit_sha FROM code_snapshots s
            JOIN repositories r ON r.id=s.repository_id AND r.tenant_id=s.tenant_id
            JOIN installations i ON i.id=r.installation_id AND i.tenant_id=r.tenant_id
            WHERE s.repository_id=1435878031 AND s.published=true AND r.enabled=true AND i.active=true
              AND r.full_name='roshan-pandit1/RepoPilot'""")).all()
        assert len(snapshots) == 1 and len(snapshots[0].commit_sha) == 40
        active = c.execute(text("""SELECT count(*) FROM investigation_jobs
            WHERE repository_id=1435878031 AND issue_number=1 AND status IN ('queued','running')""")).scalar_one()
        assert active == 0
        legacy = c.execute(text("""SELECT status, attempts FROM investigation_jobs
            WHERE id='d0614fdf-6931-4f7f-ab52-37bcb9955208'""")).one()
        assert tuple(legacy) == ('completed', 1)
        print(f'Confirmed local development API database: {name}; server={addr}:{port}; revision={revision}; evidence table absent')
        print(f'Published local snapshot: {snapshots[0].id}; commit={snapshots[0].commit_sha}; no active issue #1 jobs')
        print('Prior 4B job verified completed with one attempt before migration.')
except Exception:
    print('Database preflight failed; no migration attempted.')
    raise SystemExit(1) from None
PY
# Confirm the local PostgreSQL container's configured database matches before dumping it.
docker compose exec -T postgres sh -c '[ "$POSTGRES_DB" = repopilot ] && psql -X -qAt -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select current_database()"' | grep -qx repopilot
backup_root="$HOME/Library/Application Support/RepoPilot/backups"
mkdir -p "$backup_root"
chmod 700 "$backup_root"
backup_dir="$(mktemp -d "$backup_root/4c-XXXXXX")"
backup_file="$backup_dir/repopilot-before-0008.dump"
if ! docker compose exec -T postgres sh -c 'exec pg_dump -Fc -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > "$backup_file"; then
  printf 'Backup failed; migration not attempted. Partial backup retained at %s\n' "$backup_file" >&2
  exit 1
fi
[ -s "$backup_file" ] || { printf 'Backup is empty; migration not attempted.\n' >&2; exit 1; }
if ! docker compose exec -T postgres pg_restore --list < "$backup_file" > /dev/null ||
   ! docker compose exec -T postgres pg_restore --file=/dev/null < "$backup_file"; then
  printf 'Backup validation failed; migration not attempted.\n' >&2
  exit 1
fi
printf 'Private backup created and archive fully read: %s\n' "$backup_file"
# Build only local images; this does not start services or migrate a database.
docker compose build api migrate worker dispatcher web
# Verify the new migration container's exact target and unchanged revision before applying it.
docker compose run -T --rm --no-deps --entrypoint python migrate - "$pg_ip" <<'PY'
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from app.core.config import get_settings
try:
    s = get_settings()
    u = make_url(s.database_url)
    assert s.app_env == 'development' and u.host == 'postgres' and u.port == 5432 and u.database == 'repopilot'
    assert s.embedding_provider in ('disabled', 'fake') and not s.embedding_allow_paid
    with create_engine(u).connect() as c:
        name, addr = c.execute(text('select current_database(), inet_server_addr()::text')).one()
        assert name == 'repopilot' and addr.split('/')[0] == sys.argv[1]
        assert c.execute(text('select version_num from alembic_version')).scalar_one() == '0007'
    print('Migration container target and revision confirmed.')
except Exception:
    print('Migration container preflight failed; no migration attempted.')
    raise SystemExit(1) from None
PY
docker compose run -T --rm --no-deps migrate
docker compose run -T --rm --no-deps --entrypoint alembic migrate current
docker compose run -T --rm --no-deps --entrypoint alembic migrate check
docker compose run -T --rm --no-deps --entrypoint python migrate - "$pg_ip" <<'PYVERIFY'
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from app.core.config import get_settings
try:
    url = make_url(get_settings().database_url)
    assert url.host == 'postgres' and url.database == 'repopilot'
    with create_engine(url).connect() as db:
        name, address = db.execute(text('select current_database(), inet_server_addr()::text')).one()
        assert name == 'repopilot' and address.split('/')[0] == sys.argv[1]
        assert db.execute(text('select version_num from alembic_version')).scalar_one() == '0008'
        legacy = db.execute(text("""SELECT status, attempts, operation, snapshot_id FROM investigation_jobs
            WHERE id='d0614fdf-6931-4f7f-ab52-37bcb9955208'""")).one()
        assert tuple(legacy) == ('completed', 1, 'mock_orchestration', None)
    print('Post-migration target, revision and prior 4B job verified.')
except Exception:
    print('Post-migration verification failed; do not submit a 4C job.')
    raise SystemExit(1) from None
PYVERIFY
# Start local services only; no dependent migration service is auto-started.
docker compose up -d --no-deps api worker dispatcher web
printf 'Local services restarted. Backup retained at %s\n' "$backup_file"
