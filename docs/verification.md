# Verification record

## Sprint 2A real-service verification follow-up — 2026-10-28

Subsequent user screenshots show a real GitHub sign-in as `roshan-pandit1`, an eligible
personal installation listing public repositories, two connected repositories, and the UI
message “Initial issue synchronization completed.” The selected repository showed an empty
issue list. **PASS with limitation:** provider sign-in and onboarding were observed through the
UI; database job records, actual synchronized issues, and a real GitHub webhook remain to be
verified. No credentials or webhook payloads were supplied.

**PASS with limitation — real sync jobs:** The user queried PostgreSQL after sign-in. The
`Mini-Css-Project` and `To_Do_list` jobs were `processed`, each with one dispatch attempt and
a processing timestamp. Both repositories had zero stored issues; the demo repository retained
five. The UI and database evidence show job completion, but do not establish that a real issue
was imported, that an issue webhook was received, or that a browser rendered a real issue.

**PASS with limitation — real issue rendered:** The user created `To_Do_list` issue #1,
enabled the Issues event, and edited its title. GitHub showed an `issues.edited` delivery.
The relay initially reported HTTP 401 and PostgreSQL had no corresponding delivery or issue.
A later dashboard screenshot showed the edited issue as processed. The intervening fix and
the corresponding PostgreSQL delivery/outbox record have not yet been confirmed, so the
precise ingestion path and end-to-end webhook processing are still unverified.

| Check | Status | Evidence and limitations |
| --- | --- | --- |
| Commit and push | PASS, host-reported | The user ran `git commit` and `git push origin main`; commit `337967b` was pushed to `roshan-pandit1/RepoPilot`. This supersedes the earlier sandbox publication failure below. |
| Stack | PASS with limitation, host-reported | `docker compose ps` showed PostgreSQL, Redis, API and web healthy; worker and dispatcher were running without reported health checks. |
| Backend tests | PASS with limitation, host-reported | `docker compose exec api pytest -q -ra`: 58 passed, 2 skipped. Both skipped tests require PostgreSQL row locks; without `TEST_DATABASE_URL` the fixture uses SQLite. These tests use injected GitHub clients, not real GitHub. |
| PostgreSQL migration | BLOCKED | The user ran `docker compose run --rm migrate`; no error was shown, but the supplied output does not show the migration revision or a before/after data check. Confirm the live revision and preservation separately. |
| PostgreSQL concurrency tests | BLOCKED | Sprint 2A's two PostgreSQL-specific tests have not yet been reported against a disposable PostgreSQL database. Fixtures drop tables: never use the application database as `TEST_DATABASE_URL`. |
| Real GitHub onboarding and live lifecycle | BLOCKED | No real GitHub App sign-in, verified enrollment, synchronization or lifecycle event has been reported. Existing mock tests are not evidence of real provider integration. |
| GitHub Actions | BLOCKED | No actual workflow result has been provided. |

The app uses a user OAuth token, not an installation private key; GitHub App private key
configuration is not implemented or required by the current flow. A public webhook relay receives
event payloads: use a dedicated public test repository and a trusted relay, never expose the demo
dashboard or include webhook secrets, credentials, callback codes or payloads in shared logs.

## Repository publication attempt — 2026-10-28

The user authorized committing and pushing to `https://github.com/roshan-pandit1/RepoPilot`.
The existing `origin` points to that repository and the current branch is `main`.

- `uv lock --check --offline` passed, resolving 61 packages; the lock includes `cryptography`.
- Backend pytest: 58 passed, two PostgreSQL-only tests skipped; Ruff passed.
- Frontend type check, lint, 12 tests, and production build passed using installed dependencies.
- `git diff --check` passed. `.env`, environment variants, build output, node modules and local
  SQLite files are ignored. A targeted source scan did not find common token/private-key patterns.
- `git ls-remote origin refs/heads/main` failed because the sandbox could not resolve github.com.
- `git add -A -- .env.example .github/workflows/ci.yml .gitignore AGENTS.md Makefile README.md
  apps/api apps/web compose.yaml docs` failed: the sandbox denied creation of `.git/index.lock`.
  No files were staged; no commit or push was created.

The user can run the corresponding Git commands from their host Terminal. Do not force-push if
remote history differs; inspect the failure first. These checks do not prove real GitHub OAuth,
the new PostgreSQL migration, or a passing GitHub Actions workflow.

## Sprint 2A implementation — 2026-10-28

**Status: NOT RELEASE VERIFIED.** The new sign-in, personal installation verification,
repository selection, and first-page synchronization have not been exercised against real
GitHub or the real PostgreSQL/Redis/Celery stack. Sprint 1's earlier host results remain
historical evidence for the previous code, not evidence for these new changes.

| Check | Status | Evidence |
| --- | --- | --- |
| Backend `pytest -q` | PASS with limitation | 58 passed, two PostgreSQL-only concurrency tests skipped on SQLite. GitHub client interactions were injected or `httpx.MockTransport`; no real credentials or outbound GitHub calls. |
| Backend `ruff check . --no-cache` | PASS | No lint errors. |
| SQLite migration preservation | PASS with limitation | Fresh SQLite database upgraded to 0001, seeded, upgraded to 0002, and checked for model drift; existing demo repository and membership remained. PostgreSQL migration and downgrade were not run. |
| Frontend type check, lint, `npm test`, and build | PASS with limitation | Installed dependencies, Node 24 and Next 16.4.3. Twelve tests passed, including server-only forwarding of a real-session cookie and OAuth proxy redirect/error handling. Not a clean install, browser OAuth test, or a Docker build. |
| Python lockfile | PASS with limitation | The updated lock includes `cryptography` and its dependencies; `uv lock --check --offline` resolved 61 packages on October 28. A clean locked install and Docker build after this update have not been run in this session. |
| Real GitHub / host integration | BLOCKED | No registered App/test credentials or host Docker access were used. PKCE callback, cookie forwarding, real installation API, synchronization, Redis delivery, and PostgreSQL concurrency remain unverified end-to-end. |
| CI | BLOCKED | No remote workflow run; existing lockfiles remain uncommitted. |

Tests cover state mismatch/replay/expiry, encrypted token storage, session expiry and logout,
CSRF, production cookie attributes/demo rejection, personal account/app verification, private
repository rejection, tenant isolation, stale selection/removal tombstones, permission-change
revocation, a durable initial-sync job, idempotent processing, logout/revocation during queued
work, sanitized upstream errors, rollback on transient sync failure, access changes during fetch, and the first-page limit.
They do not prove concurrent PostgreSQL locking or real GitHub provider behavior.

Known restrictions before external use: personal accounts and public repositories only;
organizations and explicit reauthorization after revocation are unavailable; synchronization
covers the first 100 GitHub issue/PR entries only and may return `partial`; refresh tokens,
complete pagination, close/delete reconciliation, session/token retention cleanup, OAuth endpoint
rate limits, operational metrics, independent security review, and real-provider integration are
not implemented. Rotate encryption keys only with a planned session invalidation procedure.
No existing data was removed and no commit, push or deployment was performed.

On the authorized host, review the updated `apps/api/uv.lock` and use a disposable PostgreSQL
database to test migration preservation and concurrency. Rebuild the
stack and run the Sprint 1 smoke and full checks before testing a real GitHub App. Configure
secrets only locally, never include them in terminal output or screenshots, and use a public test
repository you control. Do not point `TEST_DATABASE_URL` at existing application data.

## Sprint 1 hardening / Sprint 2 planning — 2026-10-28

| Check | Status | Evidence and limits |
| --- | --- | --- |
| Frontend rendering and API-route tests | PASS with limitation | `npm test`: **9 passed**. Tests render actual issue-list states for loading, retry, errors including unauthorized, empty results, and escaped issue text. Separate route tests mock the upstream. They do not exercise browser networking, effect timing, or real backend authorization. |
| Retry behavior | FIXED, browser verification pending | A regression test first failed because loading plus an old error displayed the stale error. The retry handler now sets loading, and the issue list prioritizes the loading state. The focused test and full frontend suite passed afterward. |
| `npm run typecheck`, `npm run lint`, `npm run build` | PASS | Passed with installed dependencies and Node 24.22.0; Next.js 16.4.3 production build completed. |
| Backend pytest / Ruff | PASS with limitation | `pytest -q`: 38 passed, 1 PostgreSQL-only test skipped using SQLite. `ruff check . --no-cache` passed. Earlier host PostgreSQL run: 39 passed without warnings. |
| `uv lock --check` | PASS | uv 0.13.6 resolved 58 locked packages; manifest matches the lock. |
| Clean Python install in isolated temporary environment | BLOCKED locally | `uv sync --locked --offline` could not find the locked Ruff wheel in the isolated cache. Prior host Docker image build completed `uv sync --locked`. |
| npm lock and clean install | PASS with limitation | Root dependency specifications match. Prior host `npm ci` passed; current isolated offline `npm ci` could not find `zod-validation-error` in its cache. No dependency manifest or lock was changed in this task. |
| CI configuration | PASS static / BLOCKED actual | YAML parsed; push/PR triggers, PostgreSQL service, uv 0.13.6, Node 22, locked installs, lint/tests/build and smoke commands were checked. `actionlint` was unavailable and no GitHub Actions run was executed. |
| Git / secrets | PASS with limitation | `.env`, `.env.production`, node_modules, `.next` and a local SQLite file are ignored. Both lockfiles remain untracked. No file was staged, committed, or pushed. |
| Browser loading/error transitions | BLOCKED | No browser automation is available; server-rendering tests do not establish interactive fetch or retry timing. |

The current code is a local demo, not production-ready for external users. Before committing,
review the pre-existing and new working-tree changes and include the lockfiles only with the
user's authorization. A real GitHub Actions run is required before calling CI passed.

## Browser and database follow-up — 2026-10-28

| Check | Status | Evidence |
| --- | --- | --- |
| Browser Console | PASS with limitation | User screenshot shows no visible console error or hydration message at the captured moment. DevTools identified one form field without an id or name. The dashboard repository selector is the only form field in project source; an id and name have been added, but verification in the running Docker browser is pending. A fresh reload with preserved logs has not been confirmed. |
| Browser Network | PASS with limitation | User screenshot shows repeated `200` responses for health, repository and issue dashboard requests, and one canceled issue request. The canceled request is consistent with effect cleanup aborting an earlier fetch when the initial repository selection changes; its exact cause is inferred, not proven. No other failures are visible in the captured portion. |
| API-backed issue rendering | PASS with limitation | Dashboard source fetches `/api/dashboard` and renders `page.items`; screenshots show processed smoke rows, and host-reported live smoke previously verified the data route. The screenshot does not show response bodies. |
| PostgreSQL issue count | PASS, host-reported | User ran `SELECT count(*) FROM issues;` against the application database; PostgreSQL returned **4**, matching the screenshot’s four issue rows. |
| PostgreSQL delivery correlation | PASS, host screenshot | Read-only join returned four distinct issue IDs and four distinct delivery UUIDs. Every joined event was `issues`, each outbox status was `processed`, and each showed one dispatch attempt. Prior live smoke replayed its delivery and verified a single issue record. |
| Celery and dispatcher logs | PASS with limitation | User ran `docker compose logs --tail=80 worker dispatcher`; it returned no output. Worker log level is WARNING and successful completion is not explicitly logged, so empty logs do not independently prove processing. |
| GitHub Actions | BLOCKED | No workflow result reported; both lockfiles remain untracked. |

The read-only database join confirmed distinct issue IDs and distinct processed delivery UUIDs for
the four smoke issues, consistent with separate smoke runs. No data was deleted.

## Browser form-field fix — 2026-10-28

The user supplied DevTools evidence of a form field lacking an id or name. The repository
selector is the only form field in the dashboard source; `id="repository-selector"` and
`name="repository"` were added. Local frontend type checking, lint, all four API-route tests,
and the production build passed. A subsequent user screenshot showed the dashboard without the previous DevTools issue badge.
The user then confirmed `document.querySelector('#repository-selector') !== null` returned
`true` in the browser, verifying that the updated selector is served. GitHub Actions remains
unverified.

## Closure audit — 2026-10-28

**Verdict: SPRINT 1 VERIFIED LOCALLY for the demo ingestion slice.** User-supplied host evidence
shows a successful real-service smoke, 39 passing PostgreSQL-backed tests, the rendered issue
table, and four distinct processed issue/delivery pairs. The user confirmed the browser serves the
updated form selector. Loading/error states and a real GitHub Actions run remain unverified; the
worker logs contained no success records at the configured warning level.

| Check | Status | Evidence |
| --- | --- | --- |
| Backend tests and Ruff | PASS with limitation | This session: 38 passed, one PostgreSQL-only skip with SQLite; Ruff passed. Previous host run: 39 passed with PostgreSQL and no warnings. |
| Frontend checks | PASS with limitation | This session: type check, lint, four tests, and production build passed using installed packages. Previous host clean `npm ci` and checks passed with npm warnings. |
| Live smoke | PASS, host-reported | Earlier `make smoke` checked signature rejection, authentication, duplicate delivery, durable outbox, worker processing, persisted issue, API, and web data route. This session did not access Docker. |
| Browser rendering | PASS with limitation | User screenshots show four processed issue rows. Console, network failures, hydration, and loading/error states were not inspected. Browser automation is unavailable in this session. |
| Four smoke issues | PASS, host-reported | User-supplied SQL output showed four distinct issue IDs and four distinct processed delivery IDs, each with one dispatch attempt. The live smoke separately confirmed duplicate replay has a single issue effect. No data was removed. |
| Lockfiles / CI | BLOCKED for remote verification | `uv lock --check` passed. Workflow pins uv 0.13.6 and Node 22 and uses `uv sync --locked` and `npm ci`, but both lockfiles are untracked and no actual GitHub Actions run has been observed. |

Manual browser verification: open `http://localhost:3000`, press **⌘ Option J** in Chrome,
clear the Console, enable Preserve log in the Network panel, and reload. Confirm the issue table,
`/api/dashboard` and `/api/health` responses, absence of unexpected red console/hydration errors,
and no unexpected failed network requests. In DevTools Network throttling, briefly select Offline
and refresh to check the error state, then restore Online and refresh. Loading can be checked using
network throttling. Report observations rather than assuming these states passed.

## Host-assisted verification — 2026-10-27

The following result was supplied by the user from their macOS Terminal. The assistant did
not independently access Docker. Existing volumes were preserved.

| Command | Status | Host-reported evidence |
| --- | --- | --- |
| `make dev` | PASS | Compose built the API, migration, worker, dispatcher, and web images using cached build steps. PostgreSQL, Redis, API, worker, dispatcher, and web reported healthy; the migration container exited and dependent services started. |
| `make seed && make smoke` | PASS | User reported `PASS: auth rejection, signature rejection, durable delivery, deduplication, real worker, DB, API, web data`. The script checks a signed webhook, duplicate replay, processed outbox row, unique persisted issue, authorized API access, and the Next.js data route. |
| `make test && make lint` | PASS with limitations | User reported 38 passed, one PostgreSQL concurrency test skipped, two warnings; container Ruff with `--no-cache`, frontend type checking, and frontend ESLint passed. Pytest warned that `/app/.pytest_cache` was not writable and Starlette warned that its TestClient prefers `httpx2`. |
| `make dev && make test` after pytest cache fix | PASS with limitation | User reported successful locked API image rebuild and healthy services; pytest reported 38 passed, one PostgreSQL test skipped, and only the Starlette `httpx2` deprecation warning. The pytest cache permission warning no longer appeared. |
| PostgreSQL suite using a newly created disposable database | PASS | User reported **39 passed, one Starlette TestClient deprecation warning**. The formerly skipped row-locking test ran; test database remains in place. |
| `(cd apps/api && uv lock) && make dev && make test` | PASS with limitation | User reported lock generation with 58 packages, a successful `uv sync --locked` image rebuild, healthy services, and **38 passed, one PostgreSQL-only skip, no warnings**. The PostgreSQL suite needs a rerun with the updated test client. |
| PostgreSQL suite after locked test-client update | PASS | User reran the suite against the separate disposable database: **39 passed, no warnings**. |
| `make smoke` after locked dependency rebuild | PASS | User reported `PASS: auth rejection, signature rejection, durable delivery, deduplication, real worker, DB, API, web data`. |
| Browser issue rendering | PASS with limitation | User supplied a screenshot showing the `demo/repopilot-sandbox` issue table with multiple processed signed smoke issues. Browser console, loading and error states were not shown. |
| `(cd apps/web && npm ci && npm run typecheck && npm run lint && npm test && npm run build)` | PASS with warnings | User reported clean installation, zero npm audit vulnerabilities, type check, lint, four tests, and Next.js 16.4.3 production build passed. npm warned that ESLint 9.39.5 is unsupported and blocked the `unrs-resolver` postinstall script; all requested checks still passed. |
| Browser console, loading/error states, and CI | PENDING | Not yet verified from host output. |

## Current verification attempt — 2026-10-27

**Verdict: NOT YET VERIFIED.** Both lockfiles are present but untracked. No commit or push
was made. The running services and database state cannot be inspected from this sandbox.

| Check | Status | Actual result |
| --- | --- | --- |
| `docker compose config -q` | PASS | Compose configuration parsed successfully. |
| `docker compose exec api ruff check . --no-cache` | BLOCKED | Docker daemon socket permission denied; the reported cache failure could not be reproduced in this session. The Makefile now invokes this command once, before frontend checks. |
| Escalated Docker access | BLOCKED | Automatic approval policy rejected the request because sandbox approvals are disabled. No service commands were run with elevated access. |
| `make lint` | BLOCKED | The corrected first command could not connect to the Docker socket; full Makefile lint was not verified. |
| Host `ruff check . --no-cache` | PASS | Ruff found no backend lint errors. Host success does not verify container permissions. |
| Host `pytest -q -W default` | PASS with limitation | 38 passed, 1 skipped; SQLite-backed, with one Starlette TestClient deprecation warning. PostgreSQL row-locking test remains skipped. The user's second reported Docker warning could not be examined. |
| `uv lock --check` with uv 0.13.6 | PASS | 54 packages resolved; the backend lock matches its manifest. |
| `uv sync --locked --offline` into a temporary environment | BLOCKED | A locked psycopg wheel was absent from the local cache. A clean Python install was not verified. |
| npm manifest/lock consistency | PASS with limitation | Root dependency specifications match. Both lockfiles remain untracked; CI uses locked installation but has not run. |
| `npm ci` in a temporary directory | BLOCKED | Corrected invocation reached package download but failed with `ENOTFOUND` for the npm registry. This did not remove the existing installation. |
| Frontend `npm run typecheck`, `npm run lint`, `npm test`, `npm run build` | PASS with limitation | Existing installed dependencies, Node 24.22.0 and Next 16.4.3; four frontend API-route mock tests passed. ESLint initially scanned `node_modules.preverification`; global ignore now excludes dependency backups. `npm ls --depth=0` reported two extraneous optional packages. |
| Docker image build, `up -d --wait`, `ps`, logs, `make migrate`, `make seed`, `make test`, `make smoke` | BLOCKED | Daemon socket is unavailable; commands were not repeatedly retried after the denial. No assertion is made about Docker health, PostgreSQL, Redis, or Celery. |
| Browser / GitHub Actions | BLOCKED | No live app reachable for browser validation. No real workflow run was observed. |

The currently locked ESLint 9.39.5 is end-of-life. Some locked ESLint plugins declare peer
compatibility through ESLint 9 only, so moving to ESLint 10 requires a separately tested plugin
upgrade; no peer-dependency checks or npm install-script restrictions were bypassed. The blocked
`unrs-resolver` postinstall did not prevent the host lint or build from passing. Browser-console
errors have not been inspected. GitHub Actions has not been reported as passing.

The known warning comes from Starlette 1.10.0's `TestClient` fallback to `httpx`; it recommends
`httpx2`. It has not been suppressed. Adding or changing a dependency would require refreshing
and testing the lockfile; that is not possible with the current clean-install restrictions.
The second warning reported from Docker remains unknown because container logs are inaccessible.
The SQLite-only migration checks and historical verification results below do not validate
PostgreSQL. No live signed webhook, queued Celery event, or persisted dashboard issue was observed.

On a Docker-capable host with package registry access, run from the project root:

```bash
docker compose config -q
docker compose build
docker compose up -d --wait
docker compose ps
docker compose logs --tail 100
make migrate
make seed
make smoke
make test
make lint
(cd apps/web && npm ci && npx tsc --noEmit && npm run lint && npm test && npm run build)
```

Run the PostgreSQL test suite only against a **disposable** database because its fixtures drop
and recreate tables; never point `TEST_DATABASE_URL` at the running application database. Check
migration state and indexes without modifying application data. Then open
`http://localhost:3000`, select the demo repository, confirm the smoke-created issue appears,
check loading and error states, and inspect the browser console. Finally inspect a real GitHub
Actions run. Do not mark these checks passed from HTTP status or mocked tests alone.

## Final verification and environment recovery — 2026-10-27

**Overall: BLOCKED. Sprint 1 is not ready to close.** The existing Git checkout on `main`
was preserved. No commits or pushes were made. `.env` exists locally and remains ignored;
`.gitignore` was expanded for environment variants, local databases, and the preserved
preverification dependency directory. The previously copied frontend `node_modules` was
moved aside, so this session does not use it for clean installation.

| Check | Status | Evidence |
| --- | --- | --- |
| `git --version`, `git rev-parse --show-toplevel`, `git status --short --branch` | PASS | Git 2.54.0; existing checkout on `main`, with pre-existing uncommitted changes. No `git init` needed. |
| `docker compose version` | PASS | Compose v5.6.0. |
| `docker info` | BLOCKED | Docker client 29.8.2; server socket returned permission denied. Server version and service status are unknown. |
| `python3 --version`, `node --version`, `npm --version` | PASS | Python 3.15.0 (Python 3.14.8 also available); Node 24.22.0; npm 12.2.0. |
| `.venv/bin/python -m pip install uv==0.9.5`; `.venv/bin/uv --version` | PASS | uv 0.9.5 installed locally from PyPI. |
| Registry checks | PARTIAL | Approved `curl` received HTTP 200 from PyPI and npm; npm itself returned `ENOTFOUND` when resolving packages. PyPI simple-index download exceeded a 10-second timeout. |
| `PATH="$PWD/.venv/bin:$PATH" UV_CACHE_DIR=/tmp/repopilot-uv-cache UV_HTTP_TIMEOUT=5 UV_HTTP_RETRIES=0 UV_PYTHON_DOWNLOADS=never make lock` | BLOCKED | uv 0.9.5 panicked inside macOS SystemConfiguration. `uv lock --offline` also panicked. No uv.lock was created. Without `UV_CACHE_DIR`, its default cache path was denied. |
| `npm install --package-lock-only --ignore-scripts --cache /tmp/repopilot-clean-npm-cache --no-audit --no-fund --fetch-retries=0` | BLOCKED | `ENOTFOUND` from npm registry resolution. No package-lock.json was created. |
| `npm ci ... --fetch-retries=0`; `npm run build` | BLOCKED | Clean install requires the missing lockfile; build could not find Next.js after the old copied dependency tree was moved aside. Prior non-clean build evidence is listed below. |
| `../../.venv/bin/python -m pytest -q` (apps/api) | PASS with limitation | **38 passed, 1 skipped** using SQLite and directly installed dependencies; the skipped test requires PostgreSQL row locking. One Starlette TestClient deprecation warning was emitted. |
| `../../.venv/bin/python -m ruff check .` (apps/api) | PASS | All checks passed with Ruff 0.17.3. |
| `../../.venv/bin/alembic upgrade head`, `check`, `downgrade base`, `upgrade head` with a new temporary SQLite database | PASS with limitation | All four commands passed; no model drift detected on SQLite. PostgreSQL migration remains unverified. |
| `.venv/bin/python -m pip check` | PASS with limitation | No broken requirements in the local environment; dependencies were resolved by pip, not installed from a lockfile. |
| `test -f .env`; `docker compose config --quiet` | PASS | Existing `.env` preserved; configuration syntax validated. |
| `make dev`, `make migrate`, `make seed`, `make smoke`, `make test`, `make lint`; `docker compose ps` | BLOCKED | Docker daemon socket permission denied. No migration, startup, service health, worker, or live ingestion result was obtained. |
| Local TCP bind to `127.0.0.1` | BLOCKED | `PermissionError: [Errno 1] Operation not permitted`. No local HTTP service could be started. |
| Browser verification | BLOCKED | Chrome and Brave are installed, but no application can be started locally; no rendered issue or console check performed. |
| `gh run list --limit 3` | BLOCKED | Could not connect to api.github.com; no workflow success is claimed. The workflow statically specifies locked installs, backend tests/Ruff, frontend checks, and a Compose smoke job. |

The backend tests use a disposable SQLite database when run without `TEST_DATABASE_URL`.
Their results cannot prove PostgreSQL locking, Redis delivery, or live Celery operation.
The smoke script checks the dashboard data route but does not verify browser rendering.
No signed webhook has been demonstrated against a live stack in this session.

## Earlier Sprint 1.5 session

Date: 2026-10-27. At that time the workspace was not a Git checkout. The sandbox cannot resolve
PyPI/npm DNS, access the Docker daemon socket, or bind a local TCP listener. These are
independent blockers to dependency resolution, Compose, and live HTTP tests.

## Executed checks

| Command or check | Actual outcome |
| --- | --- |
| `test -f .env` | Passed; existing local development file was preserved. |
| `make lock` | Failed: `uv: command not found`. Neither lockfile exists. |
| `curl --fail --location --max-time 5 https://pypi.org/simple/uv/ -o /dev/null` | Failed: DNS could not resolve `pypi.org`. |
| `npm install --package-lock-only --ignore-scripts --cache /tmp/repopilot-npm-cache --fetch-retries=0 --fetch-timeout=5000 --no-audit --no-fund` (apps/web) | Failed: DNS could not resolve the npm registry. |
| Offline npm resolution | Failed: cached registry metadata / optional package archives incomplete. No incomplete lock was retained. |
| `npm ci --offline --cache /tmp/repopilot-npm-cache --no-audit --no-fund` | Failed: no package-lock.json. |
| `docker compose config --quiet` | Passed; validates the Compose configuration only. |
| `make dev`, `make migrate`, `make seed`, `make smoke`, `make test`, `make lint` | All failed: permission denied opening the Docker daemon socket. No services were started. |
| `../../.venv/bin/python -m pytest -q` (apps/api) | Collection failed: FastAPI missing. |
| `../../.venv/bin/python -m ruff check .` (apps/api) | Failed: Ruff missing. |
| `PYTHONPATH=apps/api .venv/bin/python -m pytest --confcutdir=apps/api/tests/unit apps/api/tests/unit -q` | **7 passed**: raw-body HMAC test vector and invalid/tampered signatures. |
| `python3.14 -m compileall -q apps/api infra` | Passed. Compilation does not exercise runtime imports. |
| `npm run typecheck` (apps/web) | Passed with copied local dependencies and Node 24.22.0. This was actual `tsc --noEmit`. |
| `npm run lint` (apps/web) | Initially failed on a Next.js link rule and a PostCSS export warning; both fixed. Rerun passed. |
| `npm test` (apps/web) | **4 passed** with a mocked upstream. Exercises the dashboard route and server API client, not a live backend. |
| `npm run build` (apps/web) | Passed with copied local dependencies and Node 24.22.0; Next.js 16.3.1 compiled and produced the App Router routes. |
| Python mock HTTP server on `127.0.0.1:18080` | Failed: `PermissionError: [Errno 1] Operation not permitted` while binding. No browser or live frontend/API integration check was possible. |
| GitHub Actions | Not run; no Git repository or remote is present. |

The successful frontend checks used a copy of `/Volumes/Samsung SSD/Project/DeepVerify/frontend/node_modules`
placed under the ignored `apps/web/node_modules`, including Next.js 16.3.1 and TypeScript 5.9.3.
The other project was not modified. These checks are useful but do **not** verify `npm ci`,
the missing frontend lock, the Docker image, or a clean checkout.

The frontend mock tests exercise the production route implementation, including token forwarding,
rejection when demo access is disabled, input validation, and safe upstream error handling. They
do not test React rendering, PostgreSQL, Redis, or a Celery worker. The new backend malformed-body
and non-ASCII bearer-token regression tests were written but could not be run without dependencies.

## Reproduce on an unrestricted host

Install Docker with Compose, Python 3.12+, Node 22 or 24, and uv **0.13.6**. Restore registry
access and use a disposable local database. Then, from the repository root:

```bash
test -f .env || python3 infra/init_env.py
make lock
make dev
make migrate
make seed
make smoke
make test
(cd apps/web && npm ci && npm run typecheck && npm run lint && npm test && npm run build)
make lint
```

The current lockfiles are untracked. Commit `apps/api/uv.lock` and
`apps/web/package-lock.json` only after verification and with the user’s authorization. Run the PostgreSQL test and migration checks in CI on a disposable database:

```bash
cd apps/api
uv sync --locked
# Set DATABASE_URL and TEST_DATABASE_URL to a disposable PostgreSQL database and
# GITHUB_WEBHOOK_SECRET to a local secret of at least 32 characters first.
uv run --locked alembic upgrade head
uv run --locked alembic check
uv run --locked alembic downgrade base
uv run --locked alembic upgrade head
uv run --locked pytest -q
uv run --locked ruff check .
```

After the smoke test, open `http://localhost:3000` and verify the signed demo issue is
rendered. The smoke checks the Next.js data route but does not operate a browser. Investigate
and fix any failed check before closing the sprint. A green remote GitHub Actions run is still
required; authoring the workflow is not evidence of a passing run.

## Open release blockers and security limitations

- Both lockfiles are present but uncommitted; clean installations were not verified because package archives are unavailable in this sandbox.
- Docker builds/startup, migrations, PostgreSQL concurrency, Redis/Celery, and live signed
  ingestion have not been run. There is no evidence of an issue persisted in this session.
- Backend tests and Ruff passed locally with SQLite and pip-installed dependencies; the PostgreSQL concurrency test was skipped and reproducibility remains unverified.
- Production OAuth, sessions and verified GitHub installation enrollment do not exist. Demo auth
  is deliberately shared and must remain local; production startup rejects demo authentication.
- Tenant isolation is enforced in application queries and composite keys, not PostgreSQL RLS.
  Retention/deletion automation and repository visibility/transfer reconciliation are absent.
- Readiness does not establish worker health. The outbox has bounded retries and requires operator
  review after exhaustion. Issue close/reopen synchronization and timestamp reconciliation remain
  out of scope.
- Sprint 1 / 1.5 is **not ready to close** until the definition-of-done checks pass.
