#!/bin/bash
# REVIEWED PLAN ONLY: execute only after separate explicit backup approval.
set -euo pipefail
set +x
umask 077
repo_root='/Volumes/Samsung SSD/Project/RepoPilot'
container='repopilot-local-postgres-1'
summary_sql="$repo_root/infra/final-demo-summary.sql"
test "$(docker context show)" = 'desktop-linux'
test "$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$container")" = 'repopilot-local'
test "$(docker inspect -f '{{index .Config.Labels "com.docker.compose.service"}}' "$container")" = 'postgres'
test "$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}' "$container")" = 'repopilot-local_postgres-data'
test "$(docker exec "$container" sh -c 'PGOPTIONS="-c default_transaction_read_only=on" psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc "SELECT current_database() || '\''|'\'' || (SELECT string_agg(version_num, '\'','\'') FROM public.alembic_version) || '\''|'\'' || current_setting('\''server_version_num'\'')::int / 10000"')" = 'repopilot|0013|16'
backup_root="$HOME/Library/Application Support/RepoPilot/backups"
mkdir -p -m 700 "$backup_root"
chmod 700 "$backup_root"
backup_root="$(cd -P "$backup_root" && pwd -P)"
repo_physical="$(cd -P "$repo_root" && pwd -P)"
case "$backup_root/" in "$repo_physical/"*) printf 'Refusing a backup inside the repository.\n' >&2; exit 1;; esac
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="$(mktemp -d "$backup_root/repopilot-${stamp}.XXXXXXXX")"
chmod 700 "$backup_dir"
printf 'Private backup directory: %s\n' "$backup_dir"
cp "$summary_sql" "$backup_dir/summary.sql"
printf '%s\n' '{"context":"desktop-linux","project":"repopilot-local","container":"repopilot-local-postgres-1","volume":"repopilot-local_postgres-data"}' > "$backup_dir/target.json"
docker exec "$container" sh -c 'PGOPTIONS="-c default_transaction_read_only=on" psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc "SELECT json_build_object('\''database'\'',current_database(),'\''server_version'\'',current_setting('\''server_version'\''),'\''revision'\'',(SELECT string_agg(version_num,'\'','\'') FROM public.alembic_version))"' > "$backup_dir/identity.json"
docker exec -i "$container" sh -c 'PGOPTIONS="-c default_transaction_read_only=on" psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atq' < "$backup_dir/summary.sql" > "$backup_dir/before.json"
(set -o noclobber; docker exec "$container" sh -c 'PGOPTIONS="-c default_transaction_read_only=on" pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$backup_dir/database.dump")
docker exec -i "$container" pg_restore --list < "$backup_dir/database.dump" > /dev/null
docker exec -i "$container" sh -c 'PGOPTIONS="-c default_transaction_read_only=on" psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atq' < "$backup_dir/summary.sql" > "$backup_dir/after.json"
cmp -s "$backup_dir/before.json" "$backup_dir/after.json" || { printf 'Metadata changed during backup; retain and review the artifact.\n' >&2; exit 1; }
(cd "$backup_dir" && shasum -a 256 database.dump summary.sql target.json identity.json before.json after.json > artifacts.sha256)
chmod 600 "$backup_dir"/*
printf 'Backup archive catalog and metadata checks passed; isolated restore remains required.\n'
printf 'Archive SHA-256: '
head -n 1 "$backup_dir/artifacts.sha256" | cut -d ' ' -f 1
