# Commercial GitHub and review quality: scoped progress

## Current result

**Specific commercial review gates remain blocked.** The existing product uses a
GitHub App **user OAuth token**, verifies the user's own active personal-account
installation and selected public repository, and checks tenant ownership and access
again before worker publication. It does not mint server-side installation tokens,
refresh expired tokens, enroll organizations or review private repositories. No
authenticated live GitHub review was performed in this run; no relevant credential
was configured in the checked environment. Do not infer installation authorization
from an anonymous public read or from the offline fixture.

## Required read-only GitHub permissions and setup

GitHub's documentation specifies **Pull requests: read** for PR retrieval and file
listing, and **Contents: read** for commits, Git trees and blobs; repository metadata
read is needed for repository selection. See [pull request endpoints](https://docs.github.com/en/rest/pulls/pulls),
[commit endpoints](https://docs.github.com/en/rest/commits/commits),
[Git trees](https://docs.github.com/en/rest/git/trees) and
[Git blobs](https://docs.github.com/en/rest/git/blobs). No GitHub write permission is
required for the described review. GitHub documents that installation access tokens
are acquired with an App JWT and expire after one hour; see [installation token setup](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app).

A user-controlled App registration and installation must be performed separately when
the installation-token implementation has been completed and reviewed. The current
OAuth path requires the app ID, OAuth client ID and client secret, token-encryption
key, fixed callback URL and matching web origin in protected server configuration.
Select only intended repositories. Do not put secrets in source, frontend, logs or
chat. The current code has no server-side installation-token issuer; registering an
App alone does not complete this gate. Production activation and live-source AI
inference remain unauthorized.

## Pinned review and retry

Before creating a job or outbox record, the authenticated API resolves the PR's
stable ID and exact base/head SHAs and rechecks authorization. Duplicate queued
requests match that identity; a changed head produces a separate job. The worker
rejects missing legacy pins and rejects a changed PR before reading source. It checks
the pinned identity again at completion under its lease. Current support deliberately
rejects fork-head PRs rather than fetching an unverified head repository. Historical
records were not reclassified or migrated.

GitHub server failures and network timeouts use a bounded retry of at most three
worker attempts. The outbox schedules delays of 30 then 60 seconds; duplicate delivery
cannot bypass the delay. Authentication, permission, rate limit, missing PR, changed
head and source-integrity errors fail closed and do not automatically retry. GitHub
rate-limit reset/Retry-After metadata and fork-head pinning remain unimplemented;
there is no claim that the full retry contract is complete. AI inference retries
are separate and the real Ollama worker remains blocked.

## TypeScript and quality evaluation

No TypeScript/TSX review rule was activated. The installed native parser's documented
real-source crash-containment boundary remains unresolved; using it in the worker
would risk worker termination on untrusted input. This is an explicit blocker, not a
claim of TypeScript support. Python retains the narrow `PY-SHELL-001` rule.

The existing original synthetic rule-contract set reported development TP 1, TN 3,
FP 0, FN 0; its ten-case holdout reported TP 4, TN 6, FP 0, FN 0 and four correct
positive locations. It was authored with knowledge of the rule and is **not an
independent holdout or generalizable precision/recall measurement**. Independent
labels, a truly frozen holdout, severity calibration and side-by-side comparison
remain outstanding; no competitor scores or superiority are claimed.

## Verification and operational boundary

The offline HTTPX browser workflow passed with the pinned worker: disposable
PostgreSQL, Redis, dispatcher, Celery, FastAPI, Next.js and desktop WebKit; migration
head 0020 and drift passed. The review completed partial with four files, zero
findings, one dispatch and a worker receipt; a second tenant was denied. Synthetic
mobile feedback browser regression also passed. These use fixture GitHub responses,
not live authenticated access. A separate disposable PostgreSQL selection passed
56 tests after the final changes. The broader in-process selection passed 352 with
three skips (two PostgreSQL row-lock cases and the separately opt-in Celery test).
Frontend tests passed 116, TypeScript and ESLint passed, and the Node 24 build passed
with 27 symlink-related standalone trace omissions; standalone packaging is unverified.
Ruff, offline lock and `git diff --check` passed. No real source, patch or model was
executed; no GitHub write occurred. Owned temporary services and databases were removed.

Before a commercial beta: implement and review installation-token issuance and
revocation, safely support fork heads and rate-limit recovery, establish TypeScript
parser containment and rule quality, independently label evaluation data, verify
production privacy/recovery/monitoring, and obtain explicit operational and security
approval.


The pinning API now returns sanitized, distinct authentication, permission, not-found,
rate-limit and temporary-unavailability responses before creating any job. The UI
shows when a pinned review is waiting for a transient retry and tolerates missing
file-count metadata without treating the review as complete. These UI changes passed
component tests but their retry state was not exercised in a live browser.


## Subsequent commercial beta foundation update

The earlier status in this historical record is superseded in part: an **opt-in,
mock-verified** server-side installation-token issuer and persisted rate-limit
scheduling have since been added. Fork-head review, live authenticated GitHub,
TypeScript support and independent labels remain open. See
[commercial-beta-foundation.md](commercial-beta-foundation.md) for the current
security limitations and exact verification results.
