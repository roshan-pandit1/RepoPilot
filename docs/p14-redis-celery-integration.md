# P14 — Redis and Celery application integration (2026-11-16)

## Disposable topology

A native ARM64 Redis 7.4.11 was built privately from the official source archive
`https://download.redis.io/releases/redis-7.4.11.tar.gz` (3,550,434 bytes, SHA-256
`3c266ece0abd54ed3b1c912c6eb86b7508cf382cb690ee6649d3843f018f6357`), matching
Redis's published redis-hashes list. Its private toolchain and verification record are
retained outside the repository. Redis ran with a test password, 128 MiB maxmemory,
noeviction, persistence disabled, and listener `127.0.0.1:16414`. Authenticated PING
succeeded and an unauthenticated PING was rejected. Disabled persistence means recovery
observed below depends on PostgreSQL outbox retry, not broker disk durability.

A new PostgreSQL 16.16/pgvector 0.8.7 cluster and database used port 51472 and private
storage. Its identity was checked before migrations; the full chain reached 0018 and
`alembic check` found no new operations. The API and Next.js frontend listened on loopback
ports 3416 and 3415. A real application dispatcher published to the unique `p14_isolated`
queue; Celery 5.6.3 used its real Redis transport and a solo worker. The configured worker
uses late acknowledgement, reject on worker loss and prefetch one. Solo processing does
not establish multiprocess or in-flight crash recovery. Fixture boundaries for GitHub,
source and deterministic structured-edit generation were installed only in guarded test
processes, with normal feature defaults untouched.

## Observed application workflow

Synthetic authentication, repository selection and issue synchronization ran through the
live API. The dispatcher published sync, indexing, investigation and patch tasks through
Redis; Celery logs recorded receiving and succeeding each. The indexed synthetic file was
persisted with 49 bytes, UTF-8 and `COMPLETE_FILE` coverage. An investigation returned one
source citation. The deterministic fixture provider used the source-edit converter; the
worker persisted a statically validated candidate and processed outbox. Duplicate API
request IDs returned the same proposal. The API returned `VALIDATION_UNAVAILABLE` with no
sandbox and no executed tests. The authenticated Next.js proxy accepted a review and a
subsequent API and PostgreSQL read confirmed `approved_for_review`. The result is a
candidate, not an executed fix. There were no new model calls or generated-code execution.

With Redis stopped, a new API-created proposal remained queued and its outbox remained
pending with a failed dispatch attempt. After Redis restarted without persistence, the
actual dispatcher retried; the worker reconnected, received the task, and PostgreSQL showed
`static_validated`/`processed` with four dispatch attempts. Worker logs also showed a
subsequent duplicate delivery completing without changing terminal state. Separately, a
manually replayed completed proposal was received through Redis and preserved its proposal,
review and outbox values. An authenticated cancellation of a queued proposal set
`reviewer_cancelled`; a later Redis-delivered task was received and left that state and its
empty diff unchanged. This does not prove an active-generation cancellation race or worker
crash recovery. The worker performed a warm shutdown; interruption during an active task,
lease expiry and redelivery after an in-flight crash remain unverified live.

## Security and frontend

Five live HTTP checks returned: anonymous proposal 401, missing CSRF 403, invalid review
422, unknown proposal 404 and unauthorized repository 404. Session/CSRF secrets did not
appear in those responses. These checks do not establish live cross-tenant, stale snapshot,
invalid evidence, source-hash mismatch, provider timeout/abstention or forged completion
coverage. Existing in-process PostgreSQL tests cover related authorization, stale and
invalid-result paths; production sandbox requirements were not modified. No real GitHub,
model or repository execution was used.

Four WebKit scenarios passed: authenticated views measured 375×812, 768×1024 and
1440×900; each displayed navigation, Tesseract canvas, evidence, candidate diff and review
control/state, loaded the bundled font (HTTP 200) and had no document horizontal overflow.
An unauthenticated 375×812 view showed sign-in and did not expose the synthetic source.
The review was submitted separately through the actual frontend proxy. Loading, cancellation
and error browser states were not exercised. No frontend source was changed.

The API readiness endpoint returned 200 while PostgreSQL and Redis were reachable; it does
not verify dispatcher or worker health. During the controlled outage dispatcher logs reported
publish failure, and after restart worker logs recorded reconnection and task receipt.

## Verification and cleanup

The PostgreSQL-backed focused regression selection finished **231 passed, 0 failed, 0
skipped**, with one pytest warning because caching was deliberately disabled. The first run
had **229 passed, 2 failed** because the P14-only enabled proposal flag remained in the
environment while two tests asserted disabled defaults. Removing the test-only flag and
rerunning the same selection produced the final passing result. Frontend: **94 passed**, with
TypeScript, ESLint and the Node 24.18.0 production build passing. Its temporary standalone
build warned that 27 traced files were outside the tracing root because existing node_modules
was symlinked. Ruff, offline uv lock verification and `git diff --check` passed.

The dispatcher, worker, API, frontend, Redis and PostgreSQL were stopped; their four loopback
ports no longer listened. P14 database storage, credentials, sockets and temporary harnesses
were removed. The verified Redis executable and sanitized verification record were retained.
No normal service, database or frontend source was changed. Real-repository execution still
requires the independently reviewed Linux KVM/Firecracker infrastructure and production
activation remains unauthorized.
