# Final local demo: reviewed execution plan

**Stage 2 completed:** the authorized `0014` migration and application restart succeeded;
see [verification](verification.md). The commands below are retained as a historical plan
and must not be repeated without a new review and approval. New browser demo writes remain
unapproved.

**Stage 1 completed, 2026-11-04:** The approved services were quiesced; an actual private
`0013` backup and isolated restore comparison succeeded. The retained backup path, hash,
restore container and remaining limitations are recorded in [verification](verification.md).
At the end of Stage 1, API, web, worker and dispatcher were stopped; PostgreSQL and Redis
remained running. Stage 2 has since restarted the four application services.
The backup script's archive-list check was corrected to use `docker exec -i` before the run.
Migration, rebuild and restart were subsequently authorized and performed; new demo records
still require separate approval.

**Remaining stages are not approved or executed.** Obtain separate approval before any
further action. Never run `make dev`, the Compose `migrate` service,
`alembic downgrade`, or a restore against an existing application database.

## Original read-only findings, before Stage 2

- Docker context `desktop-linux`; Compose project `repopilot-local`; PostgreSQL container
  `repopilot-local-postgres-1`, volume `repopilot-local_postgres-data`, database `repopilot`,
  PostgreSQL **16.15**, Alembic **0013**, 35 public tables. The separate default Compose
  database is not the target.
- Repository `1435878031` is enabled under an active installation; issue #1 exists. The
  **current** published snapshot is `b11f8c40-2d4b-4ab3-a4d4-d053249f8bc8`, commit
  `1d26667b64527b41e67013bd00d326ab86ada8de`: 135 files, 1,482 chunks, one skipped file.
  Its latest index job is `partial`. The formerly current snapshot is unpublished.
- There are two completed investigations, 40 evidence records, one report job and one mock
  report. Their old snapshot lacks the original provenance and manifests and remains
  unavailable for historical reads. Do not reconstruct or backfill them.
- At inspection all database pending/active-job counts, other open transactions, Redis
  `celery` queue length and unacknowledged counts were zero. These are point-in-time
  observations; Celery in-memory active/reserved/scheduled work has **not** been inspected.
- Running API/worker/dispatcher share image ID `sha256:46730e12e9cae64cdd1c9284a711ca85ad5bf9ebff1f5424a107cf94860fdca5`;
  web uses `sha256:1bb6aeae1eb908675b50df49b884566a7c7e63af4cee9773011f3006c42cb105`.
  API and web are healthy. The API image lacks migration `0014` and its backend hashes differ
  from the checkout, so a rebuild is required. Running services use the isolated network;
  API/worker/dispatcher target `postgres/repopilot`. The Compose override pins the isolated
  PostgreSQL/Redis volumes and separate image tags. GitHub OAuth settings are present; actual
  future login and repository visibility still depend on GitHub. Mock mode is selected; real
  generation, external counting and paid embeddings are disabled.

## 1. Recheck and quiesce only after separate approval

From the repository root, validate the target and zero pending work. All counts must be zero;
the version must be `repopilot|0013|16`. Stop if the context, labels, volume, version or
network differ. Do not show `docker compose config` without `--quiet`: it contains secrets.

```bash
cd "/Volumes/Samsung SSD/Project/RepoPilot"
set -o pipefail
docker context show
docker inspect repopilot-local-postgres-1 --format '{{.Name}} project={{index .Config.Labels "com.docker.compose.project"}} {{range .Mounts}}{{.Name}}:{{.Destination}} {{end}}'
docker exec repopilot-local-postgres-1 sh -c 'PGOPTIONS="-c default_transaction_read_only=on" psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc "SELECT current_database() || '\''|'\'' || (SELECT string_agg(version_num, '\'','\'') FROM public.alembic_version) || '\''|'\'' || current_setting('\''server_version_num'\'')::int / 10000"'
docker compose -p repopilot-local -f compose.yaml -f infra/compose.local-demo.yaml config --quiet
docker compose -p repopilot-local -f compose.yaml -f infra/compose.local-demo.yaml config --format json | python3 -I infra/final-demo-config-check.py
docker exec -i repopilot-local-postgres-1 sh -c 'PGOPTIONS="-c default_transaction_read_only=on" psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atq' < infra/final-demo-queue.sql
docker exec repopilot-local-redis-1 redis-cli LLEN celery
docker exec repopilot-local-redis-1 redis-cli HLEN unacked
docker exec repopilot-local-redis-1 redis-cli ZCARD unacked_index
```

After explicit approval for transient Redis control messages, check Celery in-memory work.
These commands publish control requests and temporary replies; they are **not strictly
read-only**. They suppress task contents and require exactly one responding worker with empty
lists. A timeout, malformed output, extra worker or any task means **stop**.

```bash
set -o pipefail
for state in active reserved scheduled; do
  docker exec repopilot-local-worker-1 celery -A app.workers.tasks:celery inspect --timeout 5 --json "$state" 2>/dev/null | python3 -I -c 'import json,sys; d=json.load(sys.stdin); assert len(d)==1 and all(isinstance(v,list) and not v for v in d.values()), "unexpected or unverified worker activity"; print("worker state empty")' || break
done
```

The loop stops on error; the operator must confirm three `worker state empty` lines before
continuing. Also inspect Redis for unexpected queue keys without printing their contents:

```bash
docker exec repopilot-local-redis-1 redis-cli --scan | python3 -c 'import sys; keys=set(sys.stdin.read().splitlines()); allowed={"_kombu.binding.celery","_kombu.binding.celery.pidbox","_kombu.binding.celeryev"}; extra=keys-allowed; print("unexpected Redis key count:",len(extra)); sys.exit(bool(extra))'
```

Only after checks pass and a separate service-quiescence approval, stop the four application
services, leaving PostgreSQL and Redis running. This stops the UI/API ingress and the worker;
it does not delete containers or volumes. Repeat the database/Redis checks above afterward;
wait for other transactions to clear and stop if work appears. Keep the stack quiescent through
backup, restore review and migration so the recovery point cannot become stale from app writes.

```bash
docker compose -p repopilot-local -f compose.yaml -f infra/compose.local-demo.yaml stop web api dispatcher worker
```

## 2. Backup only after separate approval

Review [the backup script](../infra/final-demo-backup.sh) and [its read-only summary query](../infra/final-demo-summary.sql).
It checks context, container labels, volume, database, revision and PostgreSQL major version;
creates a unique UTC-stamped mode-700 directory outside the repository; writes a custom-format
`pg_dump`, identity and metadata summaries with mode-600 files; checks the archive catalog;
and prints the archive SHA-256. Record the **actual printed directory and SHA-256 separately**
for restore verification. It refuses an overwritten archive and never prints credentials.

```bash
bash infra/final-demo-backup.sh
```

`pg_dump` is a consistent logical database snapshot. Before/after metadata comparison is a
guard against visible count/state changes, not proof that no same-count row changed. The dump
can contain private issue/source data and encrypted tokens; protect it and the existing OAuth
encryption key separately. The dump is not automatically encrypted and is not uploaded.
Archive-list success is not restore verification.

## 3. Disposable restore only after separate approval

The [restore-check script](../infra/final-demo-restore-check.sh) checks the separately
recorded dump hash and artifact hashes, then creates a uniquely named, **network-isolated**
`pgvector/pgvector:pg16` container and empty `restore_fixture` database. It has no host port
or connection to the application database. `pg_restore --exit-on-error` loads the archive;
the script compares revision, table/row counts, snapshot/job/report metadata and the target
repository/issue, then writes machine-readable data and pass/fail JSON beside the backup.
The container and its volume are retained. `--no-owner --no-privileges` deliberately does
not verify role ownership or grants; PostgreSQL cluster globals and external encryption keys
are not included in a database-only dump. This is not a complete production recovery test.

Enter the actual values printed by the backup; do not invent a run ID or hash:

```bash
printf 'Backup directory: '
read -r backup_dir
printf 'Separately recorded archive SHA-256: '
read -r archive_sha256
bash infra/final-demo-restore-check.sh "$backup_dir" "$archive_sha256"
```

Stop on any failure or mismatch. Inspect the private verification JSON and log. The scripts
have been syntax-checked. The recorded Stage 1 application backup and isolated restore were
executed successfully; the commands above must not be repeated without approval.

## 4. Build, migrate and restart only after separate approvals

Review `0014` and confirm the restore succeeded. It creates two tables and foreign keys;
it does not update existing rows, fabricate publication events or create manifests. PostgreSQL
DDL and foreign-key creation take locks on referenced tables until transaction commit and can
wait on other transactions. Disk space, privileges, an unexpected migration head and interrupted
or stale backups are risks. The planned `PGOPTIONS` caps lock wait at five seconds and statement
time at 60 seconds. A partial or failed command must be investigated before retrying.

The database remains `0013` until the explicitly approved command below. Build the current
source first. Repeat the sanitized Compose configuration check above immediately before the
migration; it confirms that the resolved API, worker and dispatcher database targets match
the previously inspected isolated API configuration and keeps paid settings disabled. The
Compose `run` command uses the API image as a one-off, uses `--no-deps`, does
not start the Compose migration service, has no published service ports, and retains its
one-off container. Recheck the database identity/`0013` and zero work immediately before it.

```bash
docker compose -p repopilot-local -f compose.yaml -f infra/compose.local-demo.yaml build api web
docker compose -p repopilot-local -f compose.yaml -f infra/compose.local-demo.yaml run -T --no-deps --pull never -e 'PGOPTIONS=-c lock_timeout=5s -c statement_timeout=60s' api alembic upgrade 0014
docker exec repopilot-local-postgres-1 sh -c 'PGOPTIONS="-c default_transaction_read_only=on" psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc "SELECT current_database(), (SELECT string_agg(version_num, '\'','\'') FROM public.alembic_version), to_regclass('\''public.snapshot_publications'\''), to_regclass('\''public.investigation_evidence_manifests'\'')"'
```

Require `repopilot|0014|snapshot_publications|investigation_evidence_manifests`. Before the
next command, separately approve service restart **and replacement of only the four application
containers**: Compose may recreate them to use the new image. PostgreSQL and Redis containers
and their volumes must not be removed. Recheck queues, Redis and database identity again;
any unexpected work means stop. `--no-deps` prevents an automatic migration.

```bash
docker compose -p repopilot-local -f compose.yaml -f infra/compose.local-demo.yaml up -d --no-build --no-deps api web worker dispatcher
docker inspect repopilot-local-api-1 repopilot-local-web-1 --format '{{.Name}} {{.State.Health.Status}}'
docker exec repopilot-local-api-1 python -B -c 'from app.main import app; p="/v1/repositories/{repository_id}/investigations/{job_id}/code-intelligence"; assert "get" in app.openapi()["paths"][p]; print("CIE API route present")'
docker exec repopilot-local-web-1 sh -c 'find /app -type f -path "*code-intelligence/route.js" -print'
for service in api worker dispatcher; do
  docker exec "repopilot-local-${service}-1" python -B -c 'from app.core.config import get_settings; s=get_settings(); assert s.investigation_provider=="mock" and not s.investigation_real_enabled and not s.investigation_paid_background_enabled and not s.investigation_count_external_enabled and s.embedding_provider=="disabled" and not s.embedding_allow_paid; print("mock and disabled-provider settings verified")'
done
```

Require healthy API/web, the CIE API route and compiled proxy, and all three provider checks.
Health checks do not prove GitHub access, worker processing or browser acceptance. Verify the
running API, worker and dispatcher use the newly built image and the isolated target again.

Rollback means stopping changed services and assessing the failure; **never** run a blind
`alembic downgrade` or restore over the application database. A verified archive can be restored
to a new isolated target for comparison. Any production-data restore, replacement of the
application database, service redirection or legacy backfill requires separate approval and
an explicit recovery plan. Restoring a pre-migration backup can lose writes made after it.

## 5. Browser acceptance only after separate approval for new writes

Sign in, select the existing authorized repository and issue #1, and confirm the **current**
snapshot and partial warning. Submit exactly one new investigation, wait for completion,
inspect persisted evidence and open an exact commit/line citation. Run **Analyze existing
evidence** and accept a labeled abstention. Generate exactly one deterministic mock report,
check **MOCK REPORT — DEMONSTRATION ONLY**, refresh and reopen the new job through history,
and check desktop/mobile and keyboard use. Capture redacted screenshots of history/status,
evidence, citation, CIE, mock report and mobile layout. Record actual IDs; never resubmit when
the result is uncertain. No new investigation, report or reindex is authorized by this plan.

The current snapshot predates `0014` and has no durable publication record. The migration
does not fabricate one: a new investigation on it can work while the snapshot remains current,
but cannot later use the new historical-read policy after a replacement. Do not reindex during
the demo. The older two jobs remain fail-closed and must not be repaired or recreated without
independent evidence and separate approval. The Stage 1 application backup and isolated
restore comparison, migration and service restart have passed; authenticated browser
acceptance remains **unverified**.
