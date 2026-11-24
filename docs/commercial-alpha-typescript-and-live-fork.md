# Commercial alpha: TypeScript review and public-fork status

**Verdict: commercial alpha partially verified; specific capabilities remain
blocked.** An opt-in local TypeScript rule was exercised end to end using original
synthetic source. A genuine authenticated GitHub review and independent quality
measurements remain open.

## Public GitHub target

Five direct anonymous local GitHub API requests returned HTTP 200: PR metadata,
changed-file list, the pinned head and base commit endpoints in `psf/requests`, and
independent fork repository metadata. The PR is `psf/requests#7586`, ID 4083365609,
closed and unmerged. Base repository ID 1362490 is `psf/requests`, commit
`f361ead047be5cb873174218582f7d8b9fcd9f49`; public fork ID 1305148344 is
`PEliet/requests`, commit `9820a0c297d4c3e3f7359b617b5082f24c63c79e`. GitHub's
base-repository commit endpoints returned both exact SHAs. Files listed:
`src/requests/utils.py` and `tests/test_utils.py`. One initial sandboxed DNS
attempt failed before reaching GitHub. Rate-limit headers were not retained. The
[public PR page](https://github.com/psf/requests/pull/7586) also identifies the fork
and closed status.

These were direct read-only metadata requests, **not a RepoPilot review**. Source
blobs and diffs were not independently validated in this run and no coverage or
findings are claimed for this PR. No approved RepoPilot GitHub credential was
available in the inspected process environment. User-controlled App installation
and authorization are required before the requested live authenticated
API → outbox → worker → browser demonstration. No unrelated credentials were
accessed. The prior synthetic public-fork regression remains separate.

## Local-only TypeScript review

The existing review pipeline can opt in to a parse-only Node/TypeScript child on
macOS. It is disabled by default and explicitly prohibited when `APP_ENV=production`.
No normal service or production feature was activated. A trusted project-owned
runner calls `ts.createSourceFile`; it does not import, execute or resolve modules
from reviewed source, load a repository config or plugin, or invoke npm. The parent
sends bounded source through stdin. The child receives a minimal environment, not
GitHub tokens. The selected Node binary, TypeScript compiler and trusted runner are
hashed; their hashes are bound into the review policy identity, and staged bytes are
verified. The test used Node 24.18.0 and TypeScript 5.9.3 from retained local tools.
No source is written to the staging directory.

The macOS profile denies network access, process forks, execution of other programs,
reads under the user's home, mounted volumes and unrelated temporary files, and
writes outside `/dev/null`. A synthetic canary observed denial of loopback network,
an outside read/write, process launch and inherited credential access. Input is
limited to 100,000 UTF-8 bytes and 220,000 serialized bytes, output to 32,768 bytes,
and child execution to ten seconds. Node's old-space heap limit is 128 MiB; a
sampled RSS watchdog terminates a child above 512 MiB or on monitoring failure.
Process groups are killed and reaped on failure. Parser output is validated for
version, path, hash, PID, rule and line bounds before existing evidence binding.

**Threat-model decision:** this boundary is acceptable only for an explicitly
opted-in local, non-production alpha with trusted pinned runtime files and controlled
users. It is crash containment and a restrictive macOS profile, not a hardened OS
sandbox. The filesystem policy is not a complete allowlist, RSS sampling is not a
hard full-process memory limit, staging time is not included in the child timeout,
and these canaries do not prove universal OS isolation. Linux/production support,
independent security review and load testing are unverified. Failures and unavailable
isolation produce partial coverage, never a clean finding result. The feature must
remain off where this boundary is not accepted.

For isolated local testing only, configure `PR_TYPESCRIPT_REVIEW_ENABLED=true`,
`PR_TYPESCRIPT_NODE_PATH`, `PR_TYPESCRIPT_NODE_SHA256`,
`PR_TYPESCRIPT_COMPILER_PATH`, and `PR_TYPESCRIPT_COMPILER_SHA256` for reviewed local
files. Do not turn this on in production or change normal services. The retained
test binary SHA-256 was `ee6fb0e015284d83a91e8ec5213f43a157f8a392b58555301682892ba928c04a`;
the compiler module SHA-256 was
`3ae902c92cc44dace175c0e69e13a4b0899f6983c6121d76b9ab8dd5795e7675`.
These values identify the local test artifacts, not a general distribution trust
claim. Updating any runtime or runner changes policy identity and can invalidate a
queued review.

`TS-EVAL-001` reports a **LOW**-severity risky construct for a direct
`eval(identifier)` call on an added line. It suppresses the rule if any other
`eval` identifier might indicate shadowing, ignores literal arguments and indirect
calls, and does not implement taint analysis. A runtime value might not be a string
or attacker-controlled; the finding does not assert exploitability. Syntax errors,
resource limits or parser failure produce `typescript_analysis_unavailable` and
partial coverage. Python `PY-SHELL-001` remains unchanged. This is not comprehensive
SAST and no precision, recall or competitive superiority is claimed.

## Real service and browser evidence

An original synthetic public-fork TypeScript fixture passed through authenticated
FastAPI, disposable PostgreSQL, transactional outbox, real Redis, real Celery,
Next.js and desktop WebKit at 1440 × 900. The real parser generated one persisted
`TS-EVAL-001` finding on line 2, bound to synthetic source SHA-256
`d19487a670bcabc8c5623b4f4a0015dc9582ef406a63e71efcdb8d287d60e8a4`.
WebKit displayed the finding and head repository, submitted useful feedback and
confirmed it after refresh; a second tenant was denied with 404. Review status was
completed with partial coverage, outbox processed, one dispatch attempt and an
observed worker receipt. The recorded creation-to-completion interval was 1.31
seconds for this one fixture, not a production latency statistic. A separate real
broker duplicate-delivery test retained one finding and one processing attempt.
No real GitHub or AI inference was part of this fixture.

## Reviewer packet and quality

The existing 20-case candidate manifest remains unchanged. The new
[offline reviewer page](../apps/api/evaluation/fixtures/alpha-review-candidates-v1/reviewer.html)
contains the 16 original snippets, no analyzer predictions and local JSON response
download controls; a WebKit check verified the case count and controls. Four HTTPX
public references are not included as excerpts until source sharing and license
terms are reviewed. The originals were authored with knowledge of existing rules
and are not an independent holdout. **Independent human labels: zero.**

`python -m app.evaluation.reviewer_responses MANIFEST RESPONSE...` validates the
manifest hash and reconciles pending, conflicting and adjudicated responses.
Optional `--adjudications` and `--predictions` inputs can score explicitly
adjudicated locations with two reviewer references using the existing scorer. The
system cannot verify who reviewers are or their independence; automated scores are
marked `regression` and `not independently verified`. No responses, adjudications or
accuracy scores were fabricated. A future comparison must use the same frozen
changes, scope and review budget, independent human adjudication, normalized
findings and recorded tool versions; no competitor results are claimed.

## GitHub onboarding and limits

The existing personal public-repository enrollment checks OAuth state and session,
CSRF, stable GitHub user and installation identity, selected repository, tenant
ownership and reauthorization before source reads. Synthetic tests cover forged or
wrong accounts, revocation, and selected-repository removal. An installation ID in
a setup callback is not proof of association; [GitHub's setup guidance](https://docs.github.com/en/enterprise-server%403.21/apps/creating-github-apps/registering-a-github-app/about-the-setup-url)
requires checking it against the authenticated user. Organization/private
onboarding, cross-process token invalidation and live App installation remain
unverified. An in-flight request cannot be recalled. A future user must register
and install their own read-only App, configure a reviewed reachable callback and
server-side secrets, and select the intended repository; do not paste credentials
into chat. See [existing setup notes](commercial-beta-gate-closure.md).

## Checks and cleanup

- Disposable PostgreSQL migration through 0022 and Alembic drift passed. A focused
  PostgreSQL suite passed **82, failed 0, skipped 0**, including five genuine
  Redis/Celery modes with synthetic GitHub, one of them TypeScript duplicate delivery.
- Parser/macOS sandbox plus PR selection: **74 passed, 0 failed, 0 skipped**. It
  includes TS, TSX, Unicode, invalid source, oversized input, nested input, negative
  examples, child crash/timeout/output limits, RSS watchdog, forged output and
  filesystem/network/process canaries. These selections overlap.
- Separate in-process authorization, provenance, review, labels and inference-guard
  selection: **142 passed, 0 failed, 1 skipped** (PostgreSQL row locks required).
- Frontend: **119 passed**, TypeScript and ESLint passed; Node 24 build passed in a
  disposable copy. Standalone packaging remains unverified because symlinked
  dependencies caused tracing omissions. Desktop WebKit checked the full-stack
  fixture and the offline reviewer page; mobile TypeScript browser behavior was not
  retested. Ruff, offline lock check and `git diff --check` passed.
- No generated patch or reviewed repository code executed. No real-source model
  call, GitHub write, normal database migration, normal-service restart, deployment
  or billing action occurred. Owned disposable processes, databases, broker state
  and temporary credentials were removed and test ports checked closed. Prior
  checkpoints and fixtures were retained.

## Commercial blockers

1. Complete an authenticated live GitHub App review and independently review
   installation ownership, revocation and callback handling.
2. Obtain independently adjudicated labels and a valid untouched comparison set.
3. Review the local parser boundary and extend it for a supported deployment; the
   sampled memory watchdog and macOS profile are not production isolation.
4. Support and verify organization/private repository authorization and retention,
   with no assumption that installation access grants every user access.
5. Complete production packaging, operations, observability and the separate
   fail-closed real-source AI approval boundary before accepting private customer
   repositories or charging customers.


## First developer pilot follow-up

[DEVELOPER-LABELED] The reviewer CLI now requires a previously frozen, matching
ground-truth file before loading predictions. The package is not shareable pending
license and source-context clearance. See [first developer pilot](commercial-first-developer-pilot.md).
