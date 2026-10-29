#!/bin/bash
# Authorized local-only migration. Never enable shell tracing: configuration contains secrets.
set -euo pipefail
umask 077
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
expected_hash=76d5d879c8816700086067637a2b84b2fb85d87de6de01beb2f5e74c56fe50e2
actual_hash="$(shasum -a 256 apps/api/alembic/versions/0007_investigation_jobs.py | cut -d ' ' -f 1)"
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
        tables = c.execute(text("select count(*) from information_schema.tables where table_schema='public' and table_name in ('investigation_jobs','investigation_outbox')")).scalar_one()
        assert name == 'repopilot' and addr.split('/')[0] == sys.argv[1] and revision == '0006' and tables == 0
        print(f'Confirmed local development API database: {name}; server={addr}:{port}; revision={revision}; investigation tables absent')
except Exception:
    print('Database preflight failed; no migration attempted.')
    raise SystemExit(1) from None
PY
# Confirm the local PostgreSQL container's configured database matches before dumping it.
docker compose exec -T postgres sh -c '[ "$POSTGRES_DB" = repopilot ] && psql -X -qAt -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select current_database()"' | grep -qx repopilot
backup_root="$HOME/Library/Application Support/RepoPilot/backups"
mkdir -p "$backup_root"
chmod 700 "$backup_root"
backup_dir="$(mktemp -d "$backup_root/4b-XXXXXX")"
backup_file="$backup_dir/repopilot-before-0007.dump"
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
        assert c.execute(text('select version_num from alembic_version')).scalar_one() == '0006'
    print('Migration container target and revision confirmed.')
except Exception:
    print('Migration container preflight failed; no migration attempted.')
    raise SystemExit(1) from None
PY
docker compose run -T --rm --no-deps migrate
docker compose run -T --rm --no-deps --entrypoint alembic migrate current
docker compose run -T --rm --no-deps --entrypoint alembic migrate check
# Start local services only; no dependent migration service is auto-started.
docker compose up -d --no-deps api worker dispatcher web
printf 'Local services restarted. Backup retained at %s\n' "$backup_file"
