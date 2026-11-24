# Commercial PR review workflow verification

## Scope and result

The complete browser and authenticated GitHub workflow is **not verified**. The
prior public read of [encode/httpx#3690](https://github.com/encode/httpx/pull/3690)
verified four changed Python files at base `20380490fd0bd13c68704080754c1385bff96d69`
and head `350221558d4f079fc4ab3673d81a4bc730fbb9c3`; the one supported Python
rule produced no findings, and overall coverage remained partial. That read was
anonymous, not a fresh authenticated review in this run.

The previous database-backed live attempt received GitHub HTTP 403 with a rate-limit
response while anonymously reading a tree; the exact failing response headers and
request count were not retained, so its precise category and count cannot be
independently reconstructed. A current anonymous `/rate_limit` query returned HTTP
200 and core limit 60, remaining 0, reset `1795234495`. This is not an authenticated
rate-limit measurement. No approved local token was present in the checked environment
variables; no unrelated credential store or normal application database was read.
The existing OAuth session mechanism is the supported credential path: an authorized
user must sign in and select an accessible repository in an isolated environment.
Never put a token in a browser, document or command line.

## Reliability changes

GitHub source-fetch errors now propagate out of per-file processing rather than being
published as completed partial reviews. Sanitized codes distinguish authentication,
permission, primary rate limit, retry-after-indicated secondary limit, not-found and
server failures. No raw response body or credential is persisted in these codes.
GitHub clients use a controlled user agent. Existing bounded per-client immutable
tree caching is retained. Neither cache request counts nor retry eligibility were
measured in this run. The current worker records a terminal failure: it does **not**
automatically retry a rate-limited job, because its PR base/head are not durably pinned
when the job is first queued. A new explicit review request is a new version and may
resolve a different head. Durable pinned retry and safe reset-time scheduling remain open.

## Synthetic real-broker integration

`tests/test_pr_review_celery.py` is an opt-in regression using the existing P17
disposable PostgreSQL and Redis marker guard. Its worker bootstrap
`evaluation/pr_review_celery_support.py` permits only a guarded test environment and
serves original synthetic source and GitHub responses; it makes no model calls.
The test uses real PostgreSQL, a real dispatcher process, Redis and a solo Celery
worker. A synthetic authenticated in-process API request created the job and outbox;
the worker received the task and persisted one finding and partial coverage. An
explicit duplicate was sent through Redis and a new receipt and completion were
observed; the database retained one finding and one processing attempt. CSRF-less
feedback was rejected, and authenticated synthetic feedback was read twice from the
database-backed API. This is not a running API server or browser test, and synthetic
authorization is not a live GitHub credential.

For a controlled local rerun, provision disposable services with the database/Redis
identities and random marker described in `p17-local-closure-and-execution-handoff.md`,
set `P17_ENABLE_CELERY_RACE=1`, `P17_DATABASE_URL`, `P17_REDIS_URL`, and `P17_MARKER`
privately, then run `pytest -q tests/test_pr_review_celery.py` from `apps/api`. The
shared test fixture creates and drops schema, so the identity guard is mandatory and
the database must contain no valuable data. This is a developer regression, not yet
a complete customer demonstration procedure.

## Results and remaining gates

* Real guarded broker test: **1 passed, 0 failed, 0 skipped** after a harness import
  was fixed; its first run failed before worker startup. Redis persistence was disabled.
* Focused in-process tests: **125 passed, 0 failed, 2 skipped**: the opt-in real-broker
  test (run separately above) and a PostgreSQL row-lock test in the SQLite selection.
* Frontend: **114 passed**, TypeScript and ESLint passed. Node 24 production build
  passed, but the temporary dependency symlink omitted 27 standalone trace files.
* Ruff, offline lock verification and `git diff --check` passed.
* No fresh real GitHub PR fixture, authenticated live GitHub read, real browser, live
  HTTP server, current-run migration/drift check, or actual PR queue timing metrics
  were established. No real-source inference or repository code execution occurred.

The disposable PostgreSQL and Redis processes were stopped and their owned data removed.
A full fixture-to-browser journey, cross-tenant browser checks, live authorization,
durable retry policy, broader coverage and independently reviewed inference approval
remain release gates. No production readiness or comparative performance is claimed.


### Offline PR browser follow-up

The previously open browser gap has a scoped offline regression: real HTTPX data
replayed through the disposable application and appeared in WebKit; an original
synthetic finding and feedback survived reload. This does not establish authenticated
live GitHub access, durable retry or production readiness. See
[commercial-pr-review-browser-e2e.md](commercial-pr-review-browser-e2e.md).
