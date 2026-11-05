# Local demo preparation

**Superseded by the [final execution plan](final-demo-execution-plan.md).** The current
snapshot is now `b11f8c40-2d4b-4ab3-a4d4-d053249f8bc8`, the database contains two jobs and
one report, and the running backend images lack the `0014` correction. The older snapshot,
empty-history and image observations below describe the earlier assessment, not current state.
The older startup commands must not be used before the separately approved `0014` migration.

**Prepared 2026-11-04; not executed.** The existing `repopilot-local` project is the
preferred demo target. No migration, sign-in, job, report, image build or service restart
was performed during this preparation. Browser acceptance remains outstanding.

Read-only inspection found `repopilot-local-postgres-1` mounting
`repopilot-local_postgres-data`, database `repopilot`, revision `0013` and 35 public tables.
Repository `1435878031` is enabled under an active installation, issue #1 exists, and
published snapshot `5d24f965-fb26-431b-80b4-14275467c07d` pins commit
`1d26667b64527b41e67013bd00d326ab86ada8de` with 135 files, 1,482 chunks and one skipped
file. Tenant-scoped file and chunk row counts match the snapshot metadata. These are
persisted application data, not recovered historical investigation records.
There are no investigation jobs, report jobs or active sessions. Current GitHub access,
issue freshness, and successful end-to-end use of this snapshot remain unverified.

The isolated API, worker and dispatcher use an older image that lacks the CIE module; the
web image has no CIE proxy files. OAuth is enabled, demo auth is disabled, required OAuth
settings are present, and the configured callback matches `http://localhost:3000` and the
fixed callback path. This does not prove the GitHub App registration, credentials or current
repository access will work. The running API validates its settings: mock provider, real
generation and external token counting disabled, embeddings disabled. Login is required and
creates database records. CIE reads the current GitHub issue and can reject changed context.

The API, PostgreSQL and Redis use `repopilot-local_default`. At inspection all pending
webhook, sync, index, embedding, investigation and report counts were zero; the default
Redis queue and unacknowledged-task counts were zero. The existing worker and dispatcher
are already running. These observations can change and do not prove no task is in flight.

## Checks immediately before any approved restart

From the project root, check the target and revision without printing credentials:

```bash
docker context show
docker inspect repopilot-local-postgres-1 --format '{{.Name}} project={{index .Config.Labels "com.docker.compose.project"}} {{range .Mounts}}{{.Name}}:{{.Destination}} {{end}}'
docker exec repopilot-local-postgres-1 sh -c 'PGOPTIONS="-c default_transaction_read_only=on" psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc "SELECT current_database(), current_setting('\''transaction_read_only'\''), (SELECT string_agg(version_num, '\'','\'') FROM alembic_version), (SELECT count(*) FROM pg_tables WHERE schemaname = '\''public'\'')"'
docker compose -p repopilot-local -f compose.yaml -f infra/compose.local-demo.yaml config --quiet
```

Expect context `desktop-linux`, container/project `repopilot-local`, mount
`repopilot-local_postgres-data`, and `repopilot|on|0013|35`. Stop if any differ. Never use
the empty default Compose database. The override uses external named existing volumes,
separate demo image names, loopback port 8001 for the API, and explicitly disables paid
providers. Compose resolved the web port to 3000. `config --quiet` avoids displaying secrets.

Recheck pending work before restarting workers. The dispatcher handles all job types, not
only demo investigations. **Stop and review if any count is nonzero or work is in flight.**
These counts are a point-in-time check, not a queue lock:

```bash
docker exec repopilot-local-postgres-1 sh -c 'PGOPTIONS="-c default_transaction_read_only=on" psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc "SELECT '\''webhook_pending='\'' || count(*) FROM outbox_events WHERE status = '\''pending'\'' UNION ALL SELECT '\''sync_pending='\'' || count(*) FROM sync_jobs WHERE status = '\''pending'\'' UNION ALL SELECT '\''index_active='\'' || count(*) FROM index_jobs WHERE status IN ('\''pending'\'','\''running'\'') UNION ALL SELECT '\''embedding_active='\'' || count(*) FROM embedding_jobs WHERE status IN ('\''pending'\'','\''running'\'') UNION ALL SELECT '\''investigation_pending='\'' || count(*) FROM investigation_outbox WHERE status = '\''pending'\'' UNION ALL SELECT '\''report_pending='\'' || count(*) FROM investigation_report_outbox WHERE status = '\''pending'\''"'
docker exec repopilot-local-redis-1 redis-cli LLEN celery
docker exec repopilot-local-redis-1 redis-cli HLEN unacked
docker exec repopilot-local-redis-1 redis-cli ZCARD unacked_index
```

## Rebuild and start: commands prepared, not run

Only after separate approval to restart the isolated services, and after the checks above:

```bash
docker compose -p repopilot-local -f compose.yaml -f infra/compose.local-demo.yaml build api web
docker compose -p repopilot-local -f compose.yaml -f infra/compose.local-demo.yaml up -d --no-build --no-deps api web worker dispatcher
```

The API image is shared by API, worker and dispatcher; web has its own image. `--no-deps`
prevents Compose from starting its `migrate` prerequisite, and `--no-build` uses the images
just built. The existing PostgreSQL and Redis services must already be healthy. Do not use
`make dev`, `make migrate`, ordinary `compose up`, or start the migration service. Restarting
worker/dispatcher can process pending work and write to PostgreSQL/Redis, so use the checks
and approval above; no restart is inherently read-only. Builds may download dependencies.
After startup, verify API/web health and that the API image contains the CIE module and the
web image contains the compiled CIE proxy before attempting the demo. Do not print secrets,
cookies, callback query strings, or private source in diagnostics.

```bash
docker inspect repopilot-local-api-1 repopilot-local-web-1 --format '{{.Name}} {{.State.Health.Status}}'
docker exec repopilot-local-api-1 sh -c 'test -f /app/app/modules/investigation/code_intelligence.py && echo CIE_API_present'
docker exec repopilot-local-web-1 sh -c 'find /app -type f -path "*code-intelligence*" -print | head -5'
```

Require both containers to be healthy and both CIE checks to return a result. The source
proxy is `apps/web/app/api/investigations/[repository]/jobs/[job]/code-intelligence/route.ts`;
the backend route serves `GET /v1/repositories/{repository}/investigations/{job}/code-intelligence`.
These file checks establish image contents, not successful authenticated browser behavior.

## Approval and browser workflow

Separate explicit approval is needed for the restart and for these writes **only in
`repopilot-local`**: GitHub OAuth attempt/session and any necessary user/tenant membership
records; one investigation for repository `1435878031`, issue #1, using the existing
published snapshot; one mock report for that investigation; and the corresponding outbox,
worker status, evidence, report and Redis queue updates. OAuth also reads GitHub and may
update an existing user login. It does not authorize enrollment, reindexing, issue edits,
paid providers, migration, or other jobs. If access or queue checks fail, stop.

After approval, open `http://localhost:3000` and sign in to the GitHub account that owns
the existing installation. Select the existing repository and issue #1. Click **Investigate
issue** once; wait for completion. Before generating a report, confirm the neutral missing
report state. Inspect the evidence and exact commit/line citation. Click **Analyze existing
evidence** and inspect cited observations or explicit abstention, uncertainty and limitations.
Click **Generate report** once, wait, and verify **MOCK REPORT — DEMONSTRATION ONLY**.
Refresh, reopen the new investigation in history, and check status filtering, navigation,
keyboard focus and desktop/mobile layouts. A result count of 20 or a non-abstaining CIE
finding is not guaranteed. If the issue changes after investigation, CIE can return a
conflict; record it rather than creating extra jobs without approval.

Capture redacted screenshots of history/completed status, evidence and citation, the mock
report warning, CIE findings or abstention, and a mobile view. Exclude credentials, cookies,
private issue text and sensitive source. Historical-job compatibility and multiple-job
states remain blocked if suitable existing jobs are absent. Record pass/fail/blocked for
each item in the [combined browser checklist](browser-acceptance.md). No browser acceptance
has been claimed yet.
