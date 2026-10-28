# Sprint 2 plan: verified GitHub access and repository lifecycle

Status: broader plan. A restricted Sprint 2A OAuth, personal-account enrollment, and first-page
issue sync implementation now exists; it remains unverified against real GitHub/PostgreSQL.
No AI functionality has been implemented. The goal is a read-only, public-repository connection that can
be traced from a verified GitHub user to an explicitly authorized installation and repository.
Preserve the Sprint 1 modular monolith, verified webhook boundary, transactional outbox, and
at-least-once/idempotent processing.

## User journey and trust boundaries

1. A user starts GitHub App user authorization from a fixed, server-configured callback URL.
   A one-time, expiring state value binds the callback to the initiating browser; validate it
   and use PKCE where supported. Exchange the authorization code server-side, resolve the
   GitHub user ID from GitHub, and create a rotated, opaque application session. Login errors
   are generic; never log the authorization code or tokens.
2. The user selects a tenant and starts installation/enrollment. Installation identifiers
   received from browser redirects or webhooks are **claims**, not proof of ownership. Fetch
   installation/account details through the app credential, verify the authenticated user's
   access and right to connect it, and bind it to the correct tenant in an audited transaction.
   A user's app token and an installation token have different scopes: GitHub documents that
   user tokens are limited by both the user and app permissions; installation tokens represent
   the app installation. [GitHub App user authorization](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app),
   [GitHub App best practices](https://docs.github.com/en/apps/creating-github-apps/about-creating-github-apps/best-practices-for-creating-a-github-app).
3. Enumerate the installation's selected repositories through an injected GitHub client.
   Confirm each repository is public and currently selected, and store authoritative GitHub IDs.
   Never grant a user access merely because their tenant has an installation: enforce their
   verified repository access in every data query.
4. Synchronize bounded, paginated issue metadata for authorized public repositories only. Use
   GitHub IDs as keys, idempotent upserts and source timestamps, rate-limit-aware retries, and
   checkpoints; webhooks continue to ingest opened/edited issues. Reconcile visibility changes,
   close/reopen/delete states, removals, transfers, and missed webhooks before declaring sync
   current. No repository source indexing, private-repository ingestion, or GitHub writes.
5. On removal, suspension, or uninstall, deny reads and new work immediately. Workers recheck
   permissions under the existing lock order. Make queued effects harmless or canceled, revoke
   internal sessions/tokens where applicable, and start an explicit, auditable retention/deletion
   process. Re-enable only after fresh user- and GitHub-verified authorization; stale webhook
   additions or unsuspension alone must not grant access.

## Modules and service interfaces

- `modules/auth`: authorization initiation/callback, session creation/rotation/revocation,
  current-user resolution, logout, CSRF defense, and session expiry.
- `modules/tenancy`: membership, repository grants and verified role checks. Derive tenant from
  authenticated server state and check membership on every request.
- `modules/github`: injectable, typed HTTP client for current-user access, installation metadata,
  repository enumeration, issue synchronization and token minting. Pin the API version, enforce
  timeouts and bounded pagination, and model rate limits, permission denial, 404 and transient
  errors. No arbitrary URLs or commands.
- `modules/ingestion`: reconciliation and lifecycle transitions over the same transactional
  outbox. Authentication and repository authorization are rechecked before applying effects.
- `workers`: bounded reconciliation/sync jobs; use stable idempotency keys, checkpoints,
  exponential backoff with jitter, and explicit terminal failure/operator recovery.

GitHub's installation-token endpoint can scope tokens to selected repositories and granted
permissions; mint short-lived, narrowly scoped tokens on demand. Enterprise installation token
scoping restrictions must be handled explicitly, not assumed. Do not persist installation tokens
as long-lived credentials. [GitHub installation tokens](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app).

## Database changes and migrations

Design reviewed Alembic migrations for:

- Stable GitHub user/account IDs and tenant ownership, with unique constraints. Preserve existing
  Sprint 1 IDs and demo records during migration; do not silently convert or delete data.
- Tenant memberships with explicit roles, status and last-verified time; repository grants or
  equivalent verifiable access records keyed by tenant, user and repository. Composite foreign
  keys must prevent cross-tenant association. Avoid treating a cached grant as permanent.
- Opaque session hashes, expiration, revocation and rotation metadata. If GitHub user tokens must
  be retained, store encrypted tokens and expiry/refresh metadata using a separately managed key;
  specify rotation, access controls, revocation, and deletion. Do not store plaintext secrets.
- Installations and repositories with pending/active/suspended/removed state, authoritative
  verification/reconciliation timestamps, public visibility, and a revision or generation to
  invalidate work created before revocation.
- Sync cursor/checkpoint, bounded retry status, last successful reconciliation and failure reason;
  audit records and deletion requests without credentials or issue bodies.

Migrations must support existing data and be tested for upgrade, downgrade where safe, constraint
checks, and concurrent changes. A dry-run/backup and operator rollback procedure precede production
migration. PostgreSQL RLS is a separate design decision; application authorization is mandatory
whether or not RLS is added.

## Proposed endpoints

Paths are proposals, not existing contracts. Keep the current read endpoints and webhook route;
use typed Pydantic request/response schemas and bounded pagination.

| Method and path | Purpose / required authorization |
| --- | --- |
| `GET /v1/auth/github/start` | Start browser-bound authorization; generate state and PKCE verifier. |
| `GET /v1/auth/github/callback` | Validate state, exchange code, verify identity, rotate session. |
| `GET /v1/me` | Return authenticated user and authorized tenant memberships. |
| `POST /v1/auth/logout` | CSRF-protected session revocation and cookie clearing. |
| `POST /v1/tenants/{tenant_id}/installations/enroll` | Explicit maintainer enrollment, with server-side GitHub verification. |
| `GET /v1/tenants/{tenant_id}/installations` | List only installations the authenticated member may see. |
| `POST /v1/repositories/{repository_id}/sync` | Authorized, rate-limited request to enqueue a read-only sync. |
| `GET /v1/repositories` and `GET /v1/repositories/{id}/issues` | Require real session, tenant membership and fresh repository visibility/grant. |
| `POST /v1/webhooks/github` | Existing raw-body HMAC ingress; add reviewed lifecycle reconciliation and immediate revocation. |

Mutating session-based routes require CSRF protection and an Origin policy. HTTPS deployments use
`Secure`, `HttpOnly`, `SameSite` cookies, strict callback and redirect allowlists, and no tokens in
URLs, local storage, client bundles, logs, or errors. Production remains fail-closed until real
identity is complete. Development demo must remain explicitly non-production and isolated.

## Lifecycle and failure policy

- Continue accepting signed `installation` and `installation_repositories` events. Persist
  delivery IDs idempotently and deny on removal/deletion/suspension in the same transaction as
  durable event recording. GitHub documents removal payloads in its [webhook reference](https://docs.github.com/en/webhooks/webhook-events-and-payloads).
- Verify additions and reactivation through the authenticated enrollment flow plus authoritative
  GitHub state. Do not infer a total event order from delivery time; reconcile stale, duplicate,
  missing and out-of-order messages. A late removal must never silently restore access.
- Distinguish temporary GitHub outage/rate limit from revoked permission; fail closed on uncertain
  authorization, retry with a bounded policy, and surface actionable state without leaking secrets.
- Removal first disables visibility and processing, then schedules retention/deletion according to
  an explicit documented policy. Define ownership, grace period, backups, audit retention and
  deletion guarantees before promising deletion; never purge unapproved existing data.
- Repository visibility changes to private immediately block reads/processing pending reconciliation;
  no private content or metadata sync without a separately reviewed policy.

## Test plan

- OAuth callback: valid state/PKCE, state replay/mismatch/expiry, malicious redirects, code exchange
  failures, session rotation, logout, CSRF, cookie attributes, and token redaction.
- Enrollment: authorized user, wrong tenant/account/installation, forged installation ID,
  unverified GitHub responses, duplicate requests, public/private and inaccessible repositories.
- Tenancy: cross-tenant and cross-repository reads, revoked membership/grant, changed GitHub access,
  expired verification, unauthorized sync requests, and constraints against forged foreign keys.
- Lifecycle: duplicate, out-of-order, removal/re-add/suspend/unsuspend, uninstall, stale queued jobs,
  concurrent revoke/process lock ordering, and verification failure. PostgreSQL concurrency tests
  must use a dedicated disposable database.
- Sync: pagination, interruption/resume, repeated records, stale issue updates, visibility changes,
  rate limits, GitHub 401/403/404/429/5xx and timeouts. Use an injected fake GitHub client;
  contract-test against GitHub only with an explicitly authorized test app/repository.
- Full integration: authorized session → verified public installation/repository → signed webhook →
  outbox/worker → tenant-scoped dashboard, plus negative access and revocation paths. Inspect logs
  for accidental token/body disclosure. Keep a separate CI gate and a host smoke test.

## Acceptance criteria and sequencing

1. **Identity:** real GitHub login works with protected session, state/PKCE and logout; demo bypass
   cannot operate in production. Automated negative auth/CSRF tests pass.
2. **Enrollment:** a permitted user can bind a verified GitHub App installation and selected
   public repository to the correct tenant; a different user or tenant cannot enroll or read it.
3. **Synchronization:** bounded public issue sync and signed webhook ingestion are repeatable,
   preserve newer data, and expose sync progress and failures without leaked credentials.
4. **Revocation:** uninstall, suspension, selection removal or permission loss immediately block
   reads and queued effects; only fresh verified authorization can reactivate access. Retention
   and deletion behavior is documented and tested.
5. **Release gate:** migrations and concurrency tests pass on PostgreSQL; Redis/Celery integration
   and browser flow pass; lockfiles are committed with authorization; an actual CI run passes.
   Audit logs do not contain tokens, webhook payloads, or issue bodies.

Suggested order: session/auth foundations → verified enrollment and tenant grants → lifecycle
revocation/reconciliation → bounded issue synchronization → integration and security review.
