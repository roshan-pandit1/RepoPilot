#!/bin/bash
# REVIEWED PLAN ONLY: execute only after separate explicit restore-drill approval.
set -euo pipefail
set +x
umask 077
repo_root='/Volumes/Samsung SSD/Project/RepoPilot'
test "$#" -eq 2 || { printf 'Usage: bash infra/final-demo-restore-check.sh /private/backup/directory recorded-archive-sha256\n' >&2; exit 2; }
backup_dir="$(cd -P "$1" && pwd -P)"
repo_physical="$(cd -P "$repo_root" && pwd -P)"
case "$backup_dir/" in "$repo_physical/"*) printf 'Refusing a backup inside the repository.\n' >&2; exit 1;; esac
for name in database.dump artifacts.sha256 summary.sql target.json before.json after.json identity.json; do
  test -f "$backup_dir/$name" && test ! -L "$backup_dir/$name" || { printf 'Required regular artifact missing.\n' >&2; exit 1; }
done
test "$(docker context show)" = 'desktop-linux'
python3 - "$backup_dir" "$2" <<'PY'
import hashlib, hmac, json, pathlib, re, sys
root, recorded = pathlib.Path(sys.argv[1]), sys.argv[2].lower()
names = {'database.dump', 'summary.sql', 'target.json', 'identity.json', 'before.json', 'after.json'}
if not re.fullmatch(r'[0-9a-f]{64}', recorded):
    raise SystemExit('A separately recorded archive SHA-256 is required.')
entries = {}
for line in (root / 'artifacts.sha256').read_text(encoding='ascii').splitlines():
    parts = line.split('  ', 1)
    if len(parts) != 2 or parts[1] not in names or parts[1] in entries or not re.fullmatch(r'[0-9a-f]{64}', parts[0]):
        raise SystemExit('Invalid artifact checksum manifest.')
    entries[parts[1]] = parts[0]
if set(entries) != names or not hmac.compare_digest(entries['database.dump'], recorded):
    raise SystemExit('Recorded archive hash or artifact list does not match.')
for name in sorted(names):
    digest = hashlib.sha256()
    with (root / name).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    if not hmac.compare_digest(digest.hexdigest(), entries[name]):
        raise SystemExit('Artifact integrity check failed.')
identity = json.loads((root / 'identity.json').read_text(encoding='utf-8'))
target = json.loads((root / 'target.json').read_text(encoding='utf-8'))
if (identity.get('database') != 'repopilot' or identity.get('revision') != '0013'
        or not str(identity.get('server_version', '')).startswith('16.')
        or target != {'context': 'desktop-linux', 'project': 'repopilot-local',
                      'container': 'repopilot-local-postgres-1', 'volume': 'repopilot-local_postgres-data'}):
    raise SystemExit('Backup identity does not match the approved target.')
print('Backup artifact checksums match the separately recorded archive hash.')
PY
cmp -s "$backup_dir/summary.sql" "$repo_root/infra/final-demo-summary.sql" || {
  printf 'The reviewed summary query differs from the backed-up query; stop for review.\n' >&2; exit 1; }
cmp -s "$backup_dir/before.json" "$backup_dir/after.json" || { printf 'Backup metadata comparison failed.\n' >&2; exit 1; }
run_id="$(openssl rand -hex 8)"
container="repopilot-final-restore-${run_id}"
summary="$backup_dir/restore-summary-${run_id}.json"
verification="$backup_dir/restore-verification-${run_id}.json"
log="$backup_dir/restore-${run_id}.log"
docker image inspect pgvector/pgvector:pg16 >/dev/null
docker run --pull=never -d --name "$container" --label repopilot-purpose=final-restore-check \
  --network none -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_USER=restore_fixture \
  -e POSTGRES_DB=restore_fixture pgvector/pgvector:pg16 >/dev/null
printf 'New network-isolated retained container: %s\n' "$container"
ready=false
for attempt in {1..60}; do
  if docker exec "$container" pg_isready -q -U restore_fixture -d restore_fixture; then ready=true; break; fi
  sleep 1
done
test "$ready" = true || { printf 'Disposable restore database did not become ready.\n' >&2; exit 1; }
test "$(docker inspect -f '{{.HostConfig.NetworkMode}}' "$container")" = 'none'
test "$(docker exec "$container" psql -X -v ON_ERROR_STOP=1 -U restore_fixture -d restore_fixture -Atqc "SELECT current_database() || '|' || count(*) FROM pg_tables WHERE schemaname = 'public'")" = 'restore_fixture|0'
(set -o noclobber; docker exec -i "$container" pg_restore --exit-on-error --no-owner --no-privileges \
  -U restore_fixture -d restore_fixture < "$backup_dir/database.dump" > "$log" 2>&1) || {
  printf 'Restore failed; private diagnostic log: %s\n' "$log" >&2; exit 1; }
(set -o noclobber; docker exec -i "$container" sh -c 'PGOPTIONS="-c default_transaction_read_only=on" psql -X -v ON_ERROR_STOP=1 -U restore_fixture -d restore_fixture -Atq' \
  < "$repo_root/infra/final-demo-summary.sql" > "$summary")
python3 - "$backup_dir/after.json" "$summary" "$verification" "$container" "$2" <<'PY'
import json, sys
with open(sys.argv[1], encoding='utf-8') as source, open(sys.argv[2], encoding='utf-8') as restored:
    expected, actual = json.load(source), json.load(restored)
checks = {'metadata_matches': expected == actual, 'revision_0013': actual['revision'] == '0013',
          'target_repository_present': actual['target_repository'] == 1,
          'target_issue_present': actual['target_issue_1'] == 1,
          'published_snapshot_present': any(item['published'] for item in actual['target_snapshots'])}
with open(sys.argv[3], 'x', encoding='utf-8') as out:
    json.dump({'passed': all(checks.values()), 'checks': checks, 'container': sys.argv[4],
               'archive_sha256': sys.argv[5].lower(), 'source_revision': expected.get('revision')}, out, indent=2)
    out.write('\n')
if not all(checks.values()):
    raise SystemExit('Restore verification failed; inspect the private verification summary.')
print('Restored revision, target metadata and recorded row counts match.')
PY
printf 'Machine-readable restored data and verification: %s %s\n' "$summary" "$verification"
printf 'Container and volume retained; owner/ACL fidelity and a full application recovery are not verified.\n'
