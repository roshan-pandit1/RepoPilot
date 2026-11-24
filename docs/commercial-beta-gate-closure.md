# Commercial beta gate closure: verified scope and open gates

**Verdict: commercial beta capabilities advanced; specific gates remain.** No live
installation was available, no real-source inference was made, no reviewed
repository or generated patch was executed, and no GitHub writes were made.

## Evaluation-harness regression

The synthetic report harness uses an explicit schema revision allowlist as one of
several disposable-database checks; it does not authorize P19.2 inference. The
existing allowlist included `0020` but its test asserted that it was excluded.
The synthetic SQLite workflow also migrated to `head`, which is now `0021` and
is not allowlisted. The test now asserts the actual reviewed allowlist, explicitly
rejects `0021`, and uses `0020` for that fixture. The harness allowlist and its
network, identity and approval guards were not widened. The affected file passed
11 tests. `0021` remains unavailable to that separate evaluation harness pending
an explicit compatibility review.

## GitHub authorization and revocation

Existing personal-account enrollment checks a logged-in GitHub user's stable account
ID, the configured App ID, installation suspension, selected public repository,
RepoPilot session, tenant membership, CSRF, and the database's revocation guards.
A caller-supplied installation ID alone is not authorization. A signed webhook can
revoke, but cannot enroll or silently reactivate an installation. Webhook ingestion
validates raw-body HMAC and a bounded body, records delivery IDs, and rejects a
conflicting replay. Organization and private repository enrollment remain disabled.

This change reauthorizes before each logical PR metadata, commit, tree and blob
read, using current GitHub visibility and a fresh database session. If access is
removed between tree and blob retrieval, the worker records `authorization_revoked`,
publishes no findings, and does not read the blob. The in-process and PostgreSQL
regressions cover this controlled sequence. These checks add GitHub requests; no
production rate or latency study was performed. An already in-flight HTTP call
cannot be recalled, and checks do not constitute an atomic transaction with GitHub.
Other service paths and multi-process token-cache invalidation need a separate audit.
A webhook delivered to one process does not directly purge every process's cache;
subsequent review reads still reauthorize before using the cached token. Do not
claim immediate global revocation or complete installation lifecycle verification.

The existing optional App issuer signs short-lived App JWTs, requests one selected
repository and read-only permissions, caches tokens in-process, and invalidates a
scope when the worker observes an access failure. GitHub user and installation
tokens have different authorization semantics; organization membership or an
installation alone cannot prove each user's private repository access. Relevant
GitHub documentation: [permissions](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app),
[webhook signature validation](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries),
and [installation setup](https://docs.github.com/en/apps/using-github-apps/installing-your-own-github-app).

Threats still requiring work include a spoofed setup/callback association for an
organization, a selected repository removed during a source read, an installed App
with broader rights than the user, revocation across processes, stale webhook
ordering, and a compromised signing key. The current personal/public restriction
fails closed for unsupported organizations and private repositories; it is not a
complete commercial onboarding solution. No new callback or webhook was added.

## Setup for a separately authorized future live test

After an independent review of the remaining gates, the user can register their own
GitHub App and install it on a selected personal public repository. Request Metadata,
Contents and Pull requests read access, and no write permissions. Configure the
existing fixed OAuth callback and webhook URL only in a properly protected reachable
environment; do not invent a public callback or tunnel. Subscribe to the existing
installation and installation-repositories lifecycle events when signed webhook
delivery is available. Set the App ID, OAuth client credentials, App private key,
webhook secret and encryption key through protected server-side configuration.
Never paste keys or tokens into chat or put them in frontend bundles. Rotate a
compromised key and controlled server configuration together; remove access via
GitHub's installation settings and verify RepoPilot denies subsequent reads.
The present code does not support the full organization/private onboarding flow.
**LIVE INSTALLATION-BACKED PR REVIEW — USER ACTION REQUIRED**, after the above
security and environment prerequisites are satisfied.

## Forks, TypeScript and quality

Fork-head review remains unsupported: the current review identity requires the
head repository ID and name to equal the base, while persisted job identity does
not bind a separately authorized head repository. Public fork support requires
pinned head-repository identity and verified object/access handling; private forks
need explicit user authorization. No fallback to a base branch or merge commit was
added.

Node 24.18.0 and the installed TypeScript 5.9.3 compiler are available locally.
Neither the Node parser's restricted environment, network denial, resource limits,
nor malformed-input crash handling were established in this run. A parse-only
`createSourceFile` call would not execute the source, but a subprocess alone is not
a security sandbox. TypeScript and TSX analysis remain disabled and no TypeScript
rules are claimed. Python's limited `PY-SHELL-001` remains in use.

No independently labeled dataset was obtained. The existing authored examples
remain regression evidence only. The evaluator reports label independence as
unverified. [Independent labeling protocol](commercial-review-labeling-protocol.md)
defines a frozen candidate manifest and blind review process; it does not represent
completed external labeling or benchmark results.

## Verification

- Disposable PostgreSQL: migration to 0021 and Alembic drift check passed; **60
  tests passed, 0 failed, 0 skipped** in the focused selection. Three of those
  exercised actual Redis, dispatcher and Celery with synthetic GitHub responses,
  including user-token, mock installation-token, and rate-limit modes.
- Separate in-process review/provenance/evaluation selection: **147 passed, 0
  failed, 0 skipped**. This includes the 11-test synthetic harness file and does not
  use a live provider. A preceding focused selection had **66 passed, 1 skipped**;
  it overlaps these results and the PostgreSQL selection.
- Desktop WebKit at 1440 × 900 used the existing synthetic full-stack harness:
  actual authenticated submission, persisted review and finding, useful feedback,
  refresh and reopen passed. PostgreSQL recorded completed/partial, the outbox was
  processed, Celery receipt was observed, and a second tenant received 404. This
  was not live GitHub or a changed onboarding UI. Observed database lifecycle was
  0.085 seconds for this single synthetic case, not a production latency statistic.
- Frontend unit tests: **117 passed, 0 failed, 0 skipped**. TypeScript, ESLint and
  the Node 24 production build passed in a disposable copy with existing symlinked
  dependencies. Standalone build completeness is not established because tracing
  omitted files outside the copied build root. Ruff, offline lock verification and
  `git diff --check` passed.
- The extra reauthorization calls were tested with mocked GitHub, not a real App
  installation. No TypeScript parser containment tests, private-fork tests or live
  onboarding browser test were claimed.

Owned test processes, data and temporary credentials were removed, and test listeners
were checked closed. Existing private checkpoints and offline fixtures were preserved.
Production deployment, privacy controls, independently measured quality and guarded
real-source AI inference remain commercial launch blockers.


## Commercial alpha follow-up

A synthetic public-fork review now persists both repository identities and passed
a full-stack browser regression. This is not live GitHub verification; TypeScript,
organization/private onboarding and independent labels remain open. See
[commercial-alpha-product-milestone.md](commercial-alpha-product-milestone.md).
