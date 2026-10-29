#!/bin/bash
# PREPARED ONLY: separate user approval is required before running. Never enable shell tracing.
set -euo pipefail
umask 077
[ "${REPOPILOT_4D_LOCAL_MIGRATION_APPROVED:-}" = yes ] && [ "${1:-}" = --migrate-0009-local ] || { printf 'Separate approval and explicit acknowledgement are required; stopped.\n' >&2; exit 1; }
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
expected_hash=5e9739493b5935141ce05487143a21ac2a5895c593762a20fce8ddc4fd52d74d
actual_hash="$(shasum -a 256 apps/api/alembic/versions/0009_investigation_reports.py | cut -d ' ' -f 1)"
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
        tables = c.execute(text("""select count(*) from information_schema.tables where table_schema='public'
            and table_name in ('investigation_report_jobs', 'investigation_report_outbox', 'investigation_reports')""")).scalar_one()
        assert name == 'repopilot' and addr.split('/')[0] == sys.argv[1] and revision == '0008' and tables == 0
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
        print(f'Confirmed local development API database: {name}; server={addr}:{port}; revision={revision}; report table absent')
        print(f'Published local snapshot: {snapshots[0].id}; commit={snapshots[0].commit_sha}; no active issue #1 jobs')
        existing = c.execute(text("""SELECT j.status, j.attempts, j.operation, j.snapshot_id, j.snapshot_commit_sha,
            (SELECT count(*) FROM investigation_evidence e WHERE e.job_id=j.id) AS evidence_count
            FROM investigation_jobs j WHERE j.id='457d40bf-7e15-4e10-9a27-b8a0de9e513b'
              AND j.repository_id=1435878031 AND j.issue_number=1""")).one()
        assert tuple(existing[:3]) == ('completed', 1, 'code_evidence')
        assert str(existing.snapshot_id) == str(snapshots[0].id) and existing.snapshot_commit_sha == snapshots[0].commit_sha
        assert str(existing.snapshot_id) == '24e51533-c612-4833-921d-447cfed7df99'
        assert existing.snapshot_commit_sha == '63491908290e6874dbaaf2b15c2a96473aad1324'
        assert existing.evidence_count == 20
        assert c.execute(text("SELECT status FROM investigation_outbox WHERE job_id='457d40bf-7e15-4e10-9a27-b8a0de9e513b'")).scalar_one() == 'processed'
        guards = c.execute(text("""SELECT ig.revoked, rg.revoked FROM repositories r
            JOIN installation_guards ig ON ig.id=r.installation_id
            JOIN repository_guards rg ON rg.installation_id=r.installation_id AND rg.repository_id=r.id
            WHERE r.id=1435878031""")).one()
        assert tuple(guards) == (False, False)
        print('Prior 4B job and completed 4C job with 20 evidence references verified.')
except Exception:
    print('Database preflight failed; no migration attempted.')
    raise SystemExit(1) from None
PY
# Confirm the local PostgreSQL container's configured database matches before dumping it.
docker compose exec -T postgres sh -c '[ "$POSTGRES_DB" = repopilot ] && psql -X -qAt -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select current_database()"' | grep -qx repopilot
backup_root="$HOME/Library/Application Support/RepoPilot/backups"
mkdir -p "$backup_root"
chmod 700 "$backup_root"
backup_dir="$(mktemp -d "$backup_root/4d-XXXXXX")"
backup_file="$backup_dir/repopilot-before-0009.dump"
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
        assert c.execute(text('select version_num from alembic_version')).scalar_one() == '0008'
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
        assert db.execute(text('select version_num from alembic_version')).scalar_one() == '0009'
        legacy = db.execute(text("""SELECT status, attempts, operation, snapshot_id FROM investigation_jobs
            WHERE id='d0614fdf-6931-4f7f-ab52-37bcb9955208'""")).one()
        assert tuple(legacy) == ('completed', 1, 'mock_orchestration', None)
        existing = db.execute(text("""SELECT status, attempts, operation, snapshot_id, snapshot_commit_sha
            FROM investigation_jobs WHERE id='457d40bf-7e15-4e10-9a27-b8a0de9e513b'
              AND repository_id=1435878031 AND issue_number=1""")).one()
        assert tuple(existing[:3]) == ('completed', 1, 'code_evidence')
        assert str(existing.snapshot_id) == '24e51533-c612-4833-921d-447cfed7df99'
        assert existing.snapshot_commit_sha == '63491908290e6874dbaaf2b15c2a96473aad1324'
        count = db.execute(text("SELECT count(*) FROM investigation_evidence WHERE job_id='457d40bf-7e15-4e10-9a27-b8a0de9e513b' ")).scalar_one()
        assert count == 20
    print('Post-migration target, revision, previous 4B job and 4C evidence verified.')
except Exception:
    print('Post-migration verification failed; do not request a report.')
    raise SystemExit(1) from None
PYVERIFY
# Start local services only; no dependent migration service is auto-started.
docker compose up -d --no-deps api worker dispatcher web
printf 'Local services restarted. Backup retained at %s\n' "$backup_file"
