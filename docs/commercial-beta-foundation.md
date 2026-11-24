# Commercial beta foundation: scoped verification

## Status

**Partially verified; specific safety gates remain.** Read-only installation-token
issuance and durable, pinned rate-limit scheduling are implemented behind an opt-in
setting. GitHub App responses were mocked. No approved live installation was
available or used, so installation-backed GitHub review is **not verified**. Fork-head
reviews, organization and private-repository onboarding, TypeScript review, and
independently labeled quality evaluation remain open. No real-source model call,
external repository execution, or GitHub write was performed.

## GitHub App authentication

The existing tenant/user/repository authorization and OAuth installation checks are
reused. When `GITHUB_INSTALLATION_AUTH_ENABLED` is explicitly enabled, server-side
code signs an RS256 App JWT and requests a token scoped to the selected stable
repository ID. It requests Contents and Pull requests read access, validates returned
permissions, repository scope and expiration, and caches tokens only in process.
Metadata read is needed for repository selection. Auth failures do not fall back to
anonymous or user-token access. The issuer refreshes near expiry; a process-local
lock deduplicates concurrent refresh within a process. Multiple processes can refresh
independently. Rejection invalidates cached scope; expiry and revocation are also
checked on use. User authorization is rechecked before result publication.

This does not implement the requested full installation ownership and onboarding
contract for organizations and private repositories. Existing personal-account,
selected-public-repository restrictions remain. There is no verified live token,
no verified GitHub App onboarding browser flow, and no claim that deletion or
permission changes are instantaneously visible while an existing token remains
valid. App key rotation needs a controlled process/configuration refresh. Protect
server configuration (`GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`, OAuth/session
settings); never place keys or tokens in source, client code, logs or chat.

For a future authorized live test, first independently review the integration and
register and install a user-controlled GitHub App on the intended personal account
and selected repository with Metadata, Contents and Pull requests read permissions.
Configure the existing protected server-side OAuth and App secrets and callback.
Do not paste secrets into chat. Organization/private repository onboarding and
production activation need additional implementation and review. Endpoint contracts:
[installation access tokens](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app),
[pull requests](https://docs.github.com/en/rest/pulls/pulls),
[Git trees](https://docs.github.com/en/rest/git/trees), and
[rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api).

## Pinned review and retry

The API persists PR ID and base/head pins before enqueueing; workers check those
pins before source retrieval and publication. Changed heads become separate review
identities. Fork-head PRs remain explicitly unsupported rather than silently using
the base repository. Migration `0021` adds `next_retry_at`. Safe transient network
and GitHub server failures are bounded to three attempts. Rate-limit retries require
valid reset or Retry-After metadata; scheduling is bounded, persisted and checked
against premature duplicate delivery. Missing or invalid scheduling information,
authorization failures and integrity mismatches fail closed. This mechanism is for
read-only GitHub retrieval and does not authorize additional inference calls.

## TypeScript and evaluation

TypeScript/TSX deterministic review is **not enabled**: the existing native parser
has not established an acceptable real-source crash and resource containment
boundary. Process isolation would not itself be a hardened sandbox. Python retains
only the narrowly scoped `PY-SHELL-001` rule; no comprehensive security-review
coverage is claimed.

`app/evaluation/review_quality.py` supplies reproducible, versioned scoring for
labeled source ranges, rule identity and severity, duplicate findings, unsupported
inputs, precision and recall. Tests use synthetic labels. Independent human labels,
a genuinely untouched holdout, credible generalizable accuracy and competitor
comparisons remain unavailable. The previous ten-case rule-authored smoke set is
regression evidence, not an independent benchmark.

## Evidence

- Real disposable PostgreSQL: 70 selected tests passed; a separate fixture-backed
  browser run applied migration 0021 and passed Alembic drift verification.
- Real Redis/Celery and dispatcher, synthetic GitHub transports: 3 opt-in tests
  passed, including duplicate delivery, an App-token transport and deferred
  rate-limited work. No real GitHub token was acquired.
- Broader backend selection: 434 passed, 0 failed, 5 skipped (three separately run
  opt-in broker cases and two PostgreSQL-only row-lock cases). These counts are
  distinct from the PostgreSQL and broker selections above.
- Existing fixture-backed desktop WebKit workflow passed through the actual API,
  PostgreSQL, Redis and worker after migration 0021; four files were reviewed with
  partial coverage and no findings, and cross-tenant access was denied. This was
  offline replay, not a fresh GitHub read. The retry presentation was tested at the
  frontend component level, not in a live browser.
- Frontend: 117 tests passed, TypeScript and ESLint passed, and Node 24 build passed.
  Standalone packaging remains unverified because the isolated build had symlinked
  tracing omissions. Ruff, offline lock consistency and `git diff --check` passed.
- A separate evaluation-harness regression run stopped at 1 failure and 7 passes:
  `test_disposable_evaluation_harness_recognizes_current_migration_head` expects
  revision 0020 to be excluded although the existing harness allowlist includes it.
  The inference-related allowlist was not broadened for 0021 or otherwise weakened.

Disposable services used in the recorded verification were stopped and their test
state removed. The prior offline fixture and private P19 checkpoints were preserved.
These checks do not establish production privacy, operational readiness, AI review
quality, independent labels, or commercial beta readiness.


## Gate-closure follow-up

The evaluation harness test now pins its synthetic schema to reviewed revision 0020;
0021 stays excluded. PR source reads reauthorize at logical read boundaries. Live
GitHub installation access, fork heads, TypeScript and independent labels remain
open. See [commercial-beta-gate-closure.md](commercial-beta-gate-closure.md).
