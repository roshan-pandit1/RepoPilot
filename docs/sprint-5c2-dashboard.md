# Sprint 5C2 investigation dashboard

**SPRINT 5C2 NOT YET VERIFIED.** The changed workflows still require read-only browser
acceptance with previously persisted jobs. The server-rendered frontend tests do not exercise
browser fetch transitions, clipboard permissions, layout or screen-reader behavior.
Source excerpts remain plain escaped text; syntax highlighting has not been added.

## Audit and changes

The highest-impact gap was reopening a job: users needed its UUID and had to load its issue
first. The workspace now shows the signed-in user's repository history with status filters,
bounded pages, timestamps, attempts, evidence count and report status; opening an entry
reloads and validates its authorized issue before fetching job status. Issue titles are shown
only when a matching synchronized issue exists. History refreshes access every 30 seconds,
clears on a failed recheck or when hidden, and has bounded, cancellable requests. List order
uses creation time and job ID; offset pagination can shift as new jobs arrive.

Status messages now explain the actual states, announce updates, and show evidence loading.
Evidence navigation, copy-path and copy-citation controls use the existing validated
commit-pinned links; snippets remain escaped React text. The mock report explicitly states
that it does not establish real AI diagnosis quality. Missing reports are a neutral state;
generation remains a separate user action. Historical `mock_orchestration` jobs keep their
existing no-snapshot explanation. No retrieval, provider, approval or report validation
behavior was changed. Sidebar and unrelated navigation were preserved.

Files changed for 5C2: `apps/api/app/modules/investigation/routes.py`,
`apps/api/tests/test_investigation_jobs.py`, `apps/web/components/investigation-workspace.tsx`,
`apps/web/lib/investigation-client.ts`, `apps/web/app/api/investigations/[repository]/history/route.ts`,
`apps/web/tests/investigation-proxy.test.mjs`, `apps/web/tests/investigation-workspace.test.mjs`,
`README.md`, this report and `docs/verification.md`. The existing uncommitted 5C1 files and
artifacts were preserved.

## API and security

`GET /v1/repositories/{repository_id}/investigations` uses the same session, membership,
GitHub installation and active-repository authorization as job status. Rows are restricted to
the tenant, repository and signed-in user. It returns no source snippets, tokens or session
hashes. `limit` is 1–50, `offset` is 0–10000, and `status` is an optional known job state.
The same-origin proxy validates those parameters and requests 20 items per page. Reopening
uses the existing status and evidence routes, which remain authoritative for source access.
No migration or live job is required by the feature.

## Verification and limitations

Frontend checks on Node 24.11.1 with existing dependencies: **58 tests passed**, typecheck,
ESLint and production build passed. These include proxy parameter validation, authorized
reopening and superseded issue selection; existing tests cover polling cancellation, missing
reports, historical jobs, escaped source, citations and session failure. Browser interaction,
clipboard, responsive layout and assistive technology are not established by those tests.

Disposable PostgreSQL regression run `09581d0adb29861f` passed **587 tests**, including the
history authorization and pagination regression, plus **33/33** adversarial cases, Ruff,
Alembic `0013` and `alembic check`. The source fingerprints matched and the script exited 0;
[the retained log](../apps/api/evaluation/5c1-checks-09581d0adb29861f.log) identifies the
isolated database and container. The separately approval-gated committed-source test was
excluded; the Sprint 5C1 benchmark was not rerun. No normal application database was migrated.
`git diff --check` passed. The fixture container and its volume were retained.

## Read-only browser acceptance on the Mac

Use the [consolidated dashboard and CIE-v1 checklist](browser-acceptance.md). It uses existing
authorized data and records missing prerequisites as blocked. No screenshots or browser
acceptance have been captured for this change; do not mark 5C2 verified until review is complete.
