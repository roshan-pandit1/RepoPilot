# P15 — Local reliability verification (2026-11-16)

## Scope and implementation

A test-only P15 stack used PostgreSQL 16.16/pgvector 0.8.7, authenticated Redis 7.4.11,
actual Celery solo workers, the real dispatcher and synthetic GitHub/source/provider
fixtures. The isolated database identity was checked before migrating through 0018;
`alembic check` reported no new operations. No model inference or generated code ran.
The P15 environment enabled proposal generation only within the disposable processes; its
feature flags were explicitly removed before the independent regression suite.

Inspection found that a worker's failure path checked the lease token but not whether the
lease had expired. An expired owner could consequently finalize an error and consume the
outbox before recovery. `patches/worker.py` now requires an unexpired lease on failure as
well as on successful publication. The regression test verifies that an expired owner
leaves the proposal generating and the outbox pending, after which a current owner can
complete it. Two later synthetic in-process cases also check that a changed lease token
prevents stale success and failure from publishing; these two were run on SQLite only.

`/health` remains API liveness. `/ready` now checks PostgreSQL, Redis PING and a bounded,
cached Celery control response from the same worker advertising the configured queue and
core tasks; when patch proposals are enabled it also requires the patch task. The queue is
configurable using `WORKER_READINESS_QUEUE`, default `celery`. The cache can remain stale
for three seconds; a busy solo worker may not respond within the one-second reply window.
This is worker control-plane evidence, not proof of dispatcher health, queue progress or
successful job completion. Compose API healthcheck timeouts were increased to accommodate
the two bounded inspections; no normal services were restarted.

The frontend patch panel previously shared an error value between concurrent list and detail
fetches. A successful list refresh could clear a failed detail error. The component now
retains independent list, detail and action errors; a deterministic component regression
covers the observed response order. Existing visual styling is unchanged.

## Genuine delivery, cancellation and readiness

A synthetic proposal was received and claimed by the actual Celery worker. The provider
paused after claim using a private test-only handshake. An authenticated cancellation
changed the proposal to failed/rejected with `reviewer_cancelled`, cleared its lease and
processed its outbox; after the pause was released, the task and duplicate delivery did not
publish a candidate. This covers one in-flight provider boundary, not every cancellation
boundary.

A separate claimed task was paused and its P15 worker was killed with SIGKILL. Immediately
afterward the proposal remained `generating`, with its prior lease and pending outbox. The
fixture explicitly expired that lease and rescheduled the outbox in the disposable database;
a replacement worker received the task and committed `static_validated` with a processed
outbox. The natural 120-second lease deadline was not waited out. A live old-owner completion
after a newer worker claimed the same proposal was not tested. Celery uses late ACK,
reject-on-worker-lost and prefetch one, but this experiment does not establish all Redis
visibility-timeout or multiprocess crash behavior.

With the latest probe, `/health` and `/ready` were 200 with an idle P15 worker online. After
that worker stopped and the cache expired, `/health` was 200 and `/ready` 503. Earlier probe
experiments with too-short socket timeouts returned false for a healthy worker; the reply and
transport timeouts were corrected and the live checks repeated.

## HTTP and browser observations

Live isolated HTTP checks returned anonymous proposal 401, missing CSRF 403, invalid review
422, unknown proposal 404 and inaccessible repository 404. Synthetic session and CSRF
values were absent from those responses. P15 did not run the requested live cross-tenant,
source-hash mismatch, stale snapshot, invalid evidence, provider abstention, invalid edit,
provider timeout, stale completion or unsandboxed completion cases. Existing in-process
tests cover related paths; that is not live HTTP evidence.

WebKit showed patch availability loading while the test harness held a real listing
response. It routed a detail request to a nonexistent synthetic proposal, producing a real
HTTP 404; the error remained visible after the concurrently held listing response completed,
and Retry restored the real detail. No response body was fabricated. A separate invalid
session check at 375×812 showed sign-in without exposing the synthetic source. P15 did not
verify browser generation pending, worker-unavailable, abstention, cancellation, failed
review or API outage recovery states. P14's responsive results remain separate.

## Verification and release gates

The PostgreSQL-backed selection finished **243 passed, 0 failed, 0 skipped**, with one
pytest cache-disabled configuration warning. It includes the expired-error regression and
readiness tests. Afterwards two superseded-token tests and the expired-error test ran on
SQLite: **3 passed, 28 deselected**, with the same warning. Frontend: **95 passed**,
TypeScript, ESLint and the Node 24 production build passed; the temporary standalone build
reported 27 tracing warnings due to the existing node_modules symlink. Ruff, offline uv lock
verification and `git diff --check` passed. No P9 fixture execution occurred.

| Area | Status |
| --- | --- |
| Local model generation | VERIFIED ON SYNTHETIC DATA ONLY in P8; no P15 calls |
| Source provenance | VERIFIED ON SYNTHETIC DATA ONLY |
| PostgreSQL schema, proposal persistence | VERIFIED ON SYNTHETIC DATA ONLY |
| Worker delivery | VERIFIED ON SYNTHETIC DATA ONLY |
| Worker crash recovery | PARTIALLY VERIFIED; test-induced lease expiry, solo worker |
| Cancellation and lease fencing | PARTIALLY VERIFIED; one live cancellation boundary, superseded owner only in-process |
| Authenticated API and frontend review | VERIFIED ON SYNTHETIC DATA ONLY; live negatives incomplete |
| Live GitHub and real-repository inference | BLOCKED; not authorized or exercised |
| Real-repository patch execution | BLOCKED; reviewed isolation not provisioned |
| Production infrastructure and migration | BLOCKED; not exercised |
| Independent security review | BLOCKED |
| Observability and alerting | PARTIALLY VERIFIED; no dispatcher progress or alerting proof |

P15 API, frontend, dispatcher, worker, Redis and PostgreSQL were stopped. The dedicated
loopback ports closed and disposable database storage, credentials and temporary harnesses
were removed; runtimes and sanitized database log were retained. Normal services and frontend
design were not restarted or redesigned. Production flags and sandbox requirements remain
unchanged. Local reliability remains incomplete because the live superseded-owner race,
several prioritized security cases and browser failure states remain open.
