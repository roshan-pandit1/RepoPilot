# RepoPilot development conventions

## Scope and architecture

- Read README.md, docs/verification.md, and docs/adr/0001-foundation.md before changes.
- apps/api is a Python/FastAPI modular monolith; API, dispatcher, and Celery share business modules.
- apps/web uses Next.js App Router, strict TypeScript, and Tailwind. Keep secrets in server modules.
- docs/reference is design reference, not executable migrations or an implemented API contract.
- Preserve the original RepoPilot/ bundle and archive. Never execute reference SQL wholesale.
- Sprint 1 excludes AI, indexing, shell execution of repository code, and GitHub writes.

## Security and correctness

- Verify exact raw webhook bytes before parsing; stream-enforce the 1 MiB limit.
- Use constant-time HMAC comparison. Never log secrets, tokens, webhook payloads, or SQL parameters.
- Delivery and outbox insertion must be atomic. Never dispatch slow work inline with the request.
- Treat Redis/Celery delivery as at least once. Database effects must remain idempotent.
- Preserve lock ordering: event/sync job, session (for sync/mutations), installation guard, installation, repository guard, repository as applicable. Dispatcher locks only event/job rows.
- All reads require authenticated membership, tenant predicates, enabled repo, and active installation.
- Do not accept tenant IDs from incoming webhook payloads or client headers.
- Composite foreign keys protect tenant ownership across repositories/issues/outbox.
- Production must never enable demo authentication. Do not expose the shared development demo publicly.
- GitHub OAuth uses one-time state, PKCE, opaque session hashes, encrypted tokens, same-origin CSRF checks, and a fixed callback. Never log callback query strings.
- Lifecycle events may revoke access, never enroll or reactivate. Enrollment is limited to verified personal-account installations and public repositories; organizations remain disabled.
- Apply source updates only when strictly newer; equal timestamps keep first-applied state.
- Use Alembic migrations independent of mutable ORM metadata; no startup create_all in the service.
- External GitHub requests must use an injected client protocol. Do not fabricate successful integrations.

## Commands

- `python3 infra/init_env.py`: generate private local .env once; refuses overwrites.
- `make lock`: update uv/npm lockfiles using uv 0.13.6 when dependency resolution changes.
- `make dev`: build and start Compose; migrations run as a prerequisite.
- `make migrate`, `make seed`, `make smoke`, `make test`, `make lint`, `make down`.
- Backend host: `cd apps/api && uv sync --locked && uv run pytest -q && uv run ruff check .`.
- Frontend host: `cd apps/web && npm ci && npm run typecheck && npm run lint && npm test && npm run build`.
- Frontend rendering tests use React server rendering; they do not verify browser fetch transitions.
- Docker and CI enforce `uv sync --locked` and `npm ci`; the current lockfiles are uncommitted.
- TEST_DATABASE_URL must point to a disposable database; tests drop tables. PostgreSQL is required
  to validate concurrency; SQLite results are not evidence that row locking works.

## Change discipline

- Inspect existing files, keep changes scoped, use reusable components and explicit schemas.
- Add meaningful regression tests for changes to trust boundaries, transactions, retries, and ordering.
- Never claim a test, build, smoke, or deployment succeeded unless it was executed successfully.
- Record missing tools or environment restrictions in docs/verification.md. Current checks are partial.
- No paid infrastructure or deployment is authorized. No secrets belong in tracked files.
