# P13 — Disposable application workflow (2026-11-16)

P13 used a private PostgreSQL 16.16/pgvector 0.8.7 cluster and disposable API,
Next.js and separate test worker processes. The database identity and loopback port were
checked before migration. The full migration chain reached 0018; `alembic check` reported
no new upgrade operations. Selected PostgreSQL-backed tests reported **78 passed, 0 failed,
0 skipped**. Those tests use in-process API clients and mocked external boundaries; they
cover authorization, source/evidence checks, provider errors, idempotency, cancellation,
worker fencing and rejected unverified passing results.

The live synthetic workflow used the real authenticated API, PostgreSQL persistence,
source indexing and investigation services, outbox dispatcher and worker processing
functions. A separate P13 polling process invoked those functions with a deterministic
synthetic provider and synthetic GitHub/source fixtures. The proposal reached
`static_validated`, its outbox was `processed`, and `VALIDATION_UNAVAILABLE` correctly
indicated that no isolated tests ran. An authenticated request through the actual Next.js
proxy recorded `approved_for_review`, and a subsequent API read confirmed the decision.
The provider was a fixture; no model inference or patch execution occurred.

No compatible Redis broker was available without a download. The test worker used a
fixture dispatch callback; actual Redis/Celery delivery, retries and recovery were not
verified, and readiness reported false. This is not a complete running-stack verification.
The selected negative tests were in-process rather than live end-to-end scenarios.

A WebKit check at 1440 pixels displayed the modern navigation, Tesseract canvas, theme,
font, indexed evidence, candidate diff, static validation state and persisted review state.
The review write was verified through the frontend proxy separately from the browser click.
The attempted mobile resize did not change the WebKit viewport, so mobile is unverified.
An initial browser harness returned before awaiting its assertions and was corrected; only
the later awaited check counts. No frontend source was changed.

Using Node 24.18.0, frontend tests reported **94 passed**, and TypeScript, ESLint and the
production build passed. The copied standalone test build initially lacked static/public
assets; copying them into the temporary standalone directory and restarting only that test
server allowed the browser check to proceed. The build warned about files outside its
tracing root because the temporary copy used the existing node_modules via symlink. Ruff,
`uv lock --check --offline` and `git diff --check` passed. PostgreSQL and the test API,
worker and web servers were stopped, their ports closed, and disposable data and test
credentials removed. No normal service or database was changed.

Remaining gates: run the actual broker and Celery worker with the same isolated workflow;
exercise live negative scenarios, mobile browser layout and test-execution security on a
separately reviewed isolation platform. Production flags remain disabled. This synthetic
result is not production readiness or proof of real GitHub or live model behavior.
