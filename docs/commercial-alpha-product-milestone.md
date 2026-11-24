# Commercial alpha product milestone

**Verdict: TypeScript/onboarding product capabilities partially verified.** This
increment adds a constrained public-fork review path and a prepared reviewer packet;
it does not establish a commercial alpha or independently measured review quality.

## Public-fork reviews

Migration `0022` stores the head repository's stable ID and name alongside the
existing PR ID and base/head commit pins. A check constraint rejects partially
specified or nonpositive head identities. Legacy rows with both fields absent are
interpreted only as same-repository reviews, matching the old acceptance policy;
legacy queued reviews remain idempotent. New jobs pin the head identity before the
outbox is committed. API stale detection, feedback, duplicate requests and worker
lease fencing bind the complete identity.

A fork must be reported as public in the PR metadata. Before each logical source
read, the worker reauthorizes the selected base repository and reconciles the
fork's GitHub repository ID, name and public visibility. It resolves both commits,
trees and blobs through the authorized **base repository** at the pinned SHAs;
source bytes, Git blob hashes and diffs retain the existing verification. If the
base repository cannot resolve a fork head's objects, review fails closed. This is
not a claim that GitHub exposes every public fork head through that endpoint. A
fork becoming private, deleted, renamed or changed is rejected. These checks add
GitHub API calls, and cannot recall an HTTP request already in flight. No private
fork is accepted and there is no branch or merge-commit fallback.

The existing review detail displays the pinned head repository name. Evidence now
includes head repository identity as well as the head commit and source hashes.
The deterministic rule remains Python-only and review coverage stays partial.

## GitHub authentication

The existing personal-account, public-repository path uses authenticated user
OAuth, verifies the user's stable GitHub ID and selected installation/repository,
checks tenant membership and reauthorizes before source reads. Mocked tests cover
wrong accounts, CSRF, revoked installations, repository removal and token scope;
this is not independent security review or live installation verification. The
optional installation token path is server-side and disabled by default. The App
setup URL's installation ID is untrusted, as [GitHub documents](https://docs.github.com/en/enterprise-server%403.21/apps/creating-github-apps/registering-a-github-app/about-the-setup-url).
Organization and private-repository enrollment remain unsupported. No App was
created or installed and no unrelated credentials were accessed. The existing
[setup guidance](commercial-beta-gate-closure.md) lists read-only permissions,
callback and protected-secret requirements; a user-controlled installation and
security-reviewed reachable callback are needed for a future live pilot.

## TypeScript and review quality

No TypeScript or TSX parser or review rule was activated. Node 24.18.0 and the
installed TypeScript 5.9.3 are present, and a simple macOS `sandbox-exec` process
started, but that does not establish a Node parser's trusted dependency identity,
network and filesystem denial, memory boundary, timeout, crash handling or worker
integration. A child process alone is not a hardened sandbox. The safe parser
boundary and resulting TypeScript findings remain necessary product work.

The existing scorer now provides per-rule TP/FP/FN, precision and recall, duplicate
rate with its finding denominator, and supported-case fraction. It continues to
state that label independence is not verified. No new review-quality score or
competitor comparison is claimed.

The [reviewer packet](../apps/api/evaluation/fixtures/alpha-review-candidates-v1/manifest.json)
contains 20 **unlabeled candidates**: 16 original Python/TypeScript/TSX snippets
and four references to a previously verified public HTTPX PR fixture. Manifest
SHA-256: `88b6f49d922f7275a1f990776b1b2d277ab8954a404520421077d9dbbdc1885a`.
The originals were authored with knowledge of the existing rule and cannot be
presented as an independent holdout. The HTTPX references all come from one PR,
and source is not redistributed in this packet; the retained private fixture or
verified public retrieval is required. Redistribution terms require confirmation.
The accompanying reviewer template and [labeling protocol](commercial-review-labeling-protocol.md)
are for outside adjudicators. Independent labels: **zero**; no holdout was scored.

## Verification

- Synthetic public-fork vertical slice: actual disposable PostgreSQL, transactional
  outbox, Redis, Celery, authenticated API, Next.js and desktop WebKit. The worker
  received the message, persisted one `PY-SHELL-001` finding with source identity
  and partial coverage, and an authenticated useful-feedback decision survived
  refresh. Cross-tenant access returned 404. The browser displayed the synthetic
  fork's pinned head name. This was mocked GitHub data, not a live public PR.
- The final disposable PostgreSQL migration/drift run and Redis/Celery selection
  passed **79 tests, 0 failed, 0 skipped**, including four real broker modes and the
  synthetic public fork. An earlier in-process selection including additional fork
  negative cases and evaluation tests passed **99, 0 failed, 1 skipped**. An
  overlapping separate review/provenance/evaluation selection passed **149, 0
  failed, 0 skipped**. Test selections overlap and must not be added together.
- Frontend: **118 tests passed**, TypeScript and ESLint passed, and Node 24 build
  passed. Standalone packaging is not verified because the isolated build used
  symlinked dependencies and warned about tracing files outside the build root.
  Ruff, offline dependency-lock check and `git diff --check` passed.
- The synthetic browser run observed 1.80 seconds from persisted creation to
  completion for one case. This is not a production P95 or cost measurement. No
  model was invoked and no inference cost is estimated.

No approved live GitHub installation or OAuth credential was used. No reviewed
repository code or generated patch was executed; no model call, GitHub write,
production deployment or normal-service restart occurred. Owned disposable
services and test data were cleaned up; prior checkpoints and fixtures remain.

## Before the first external pilot

1. Independently review and test installation ownership, user visibility,
   revocation, callback/state and cross-process behavior; complete organization and
   private-repository scope only where authorization is demonstrable.
2. Establish a tested TypeScript parser boundary and ship evidence-backed rules,
   with clear unsupported and parser-failure results.
3. Verify a user-controlled read-only GitHub App installation and a real public
   fork using the complete application; document behavior when base objects are
   unavailable and measure request costs.
4. Obtain outside developer labels and adjudication, then score an untouched
   holdout. Do not market authored fixtures as independent accuracy evidence.
5. Review production privacy, deployment, retention, observability and the separate
   fail-closed real-source inference approval mechanism before enabling a pilot.


## TypeScript and real-fork follow-up

An opt-in non-production macOS TypeScript rule now passed a synthetic
PostgreSQL/Redis/Celery/WebKit workflow. The target public fork metadata was read
anonymously, but no live authenticated application review occurred. See
[commercial-alpha-typescript-and-live-fork.md](commercial-alpha-typescript-and-live-fork.md).
