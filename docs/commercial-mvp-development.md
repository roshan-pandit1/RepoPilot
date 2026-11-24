# Commercial PR review MVP development

## Positioning and scope

RepoPilot is an evidence-first review and fix-proposal product for small teams using GitHub,
initially Python and TypeScript. A finding is a review lead tied to a pinned source identity,
not a proven vulnerability. The existing issue investigation, source provenance and
proposal-only patch validation/export flows remain separate from executable validation.
No customer interviews, competitor comparison, customer revenue or production deployment
are claimed.

## Deterministic rule catalog

`PY-SHELL-001` (`pr-rules-v1`) reports a newly added Python call to a directly imported
`subprocess` method when a direct function parameter occurs in an f-string and
`shell=True` is a literal. The report is medium severity and medium confidence: the
caller may not control the parameter, and impact depends on shell and validation.
Argument-vector calls, literal commands, shadowed/rebound imports, altered parameters,
unknown expressions, unchanged lines and unparseable code do not trigger the rule.
Dynamic monkey-patching, indirect flows and other APIs are outside its scope. This is
not a general SAST scan. Unsupported files and unverified inputs must be shown as partial
coverage, not as a clean security review.

## Evaluation methodology

`python -m app.evaluation.pr_review_smoke` runs original, non-executed synthetic strings.
The author knew the rule when creating the development and holdout splits. This is a tiny
rule-contract smoke test, not an independent benchmark or a measure of broad vulnerability
recall. At one run, development had 1 true positive, 3 true negatives, 0 false positives
and 0 false negatives; the 10-case holdout had 4 true positives, 6 true negatives, 0 false
positives and 0 false negatives. The positive evidence locations matched 4/4 holdout labels;
there were no duplicate findings. The measured synthetic inputs were 289 and 785 bytes.
Latency was under 1 ms locally for each split, but this is not a PR latency percentile.
No AI tokens, model quality, human usefulness, comparative advantage or cost were measured.
A real benchmark needs independently reviewed labels and a truly untouched holdout.
Targets, not results: actionable precision ≥80%, recall ≥60% for labeled high-severity
issues, no source-identity mismatches, no unauthorized disclosures, and eventual small-PR
P95 under five minutes.

## Security and privacy boundaries

Public PR content and metadata are untrusted. Only authenticated authorized repository access,
pinned source identities and bounded static parsing may lead to a review. AI on real source,
code execution, automatic GitHub comments, merge gates and deployment remain disabled.
The existing experimental local approval ledger and transport are not an authenticated,
worker-integrated approval authority. A claim can be lost to ambiguous transport outcome;
a future implementation must never automatically retry and must enforce one fixed authority,
current tenant/source identity, exact bytes and verified local daemon/egress. No exactly-once
execution is claimed. Logs and analytics should not include source, prompts, tokens or secrets.
Retention/deletion, audited access, production recovery, security review and paid-customer
terms remain release work; no compliance certification is claimed.

## Pricing hypotheses and unit economics

Possible developer and team prices are $19 and $29 per seat/month, respectively; neither is
approved pricing. Illustrative assumptions only: 40 reviews/seat/month; a hypothetical payment
fee of 2.9% plus $0.30 per seat-month; and an 80% gross-margin target. With those assumptions,
total remaining delivery/support allowance is about $2.95 per $19 seat or $4.66 per $29 seat,
roughly $0.074 or $0.116 per review at 40 reviews. Real payment pricing, model/server cost,
review distributions, shared storage, support and churn are unknown and must be measured.
Free trials should have explicit duration and review/compute caps; no unlimited AI plan is
assumed. No payment provider is connected and no card data is stored.

## Customer discovery and beta gates

Interview five engineering teams without assuming results: ask about PR volume and languages,
existing review tools and false-positive tolerance, concrete examples of useful findings,
privacy requirements and acceptable source/model boundaries, desired fix handoff, latency,
pricing and adoption barriers. Request explicit permission before using any team data.
Validate onboarding, revocation, tenant isolation, retention/deletion, incident handling,
backup/recovery, quotas, operational telemetry and dependency licenses before a private beta.
A team-ownership and billing model, live-provider approval, independently reviewed sandbox
for any future code execution, and verified operations are not yet launch-ready.

## Implemented application slice and remaining gates

A tenant-scoped PR review job, deterministic analyzer, findings and per-user feedback
have been added behind the disabled-by-default `pr_reviews_enabled` setting. PR URLs
are restricted to the authorized selected repository. The analyzer pins both commit
identities, verifies the Git blob and raw file SHA-256, compares diff hunks to the
independently retrieved source versions, and rechecks the PR before publishing. A changed
head is shown as stale and feedback is rejected. Only supported Python source is scanned;
fork-head PRs, unsupported languages and file operations are deliberately constrained,
and analysis is labeled partial. There is no GitHub write, execution or model call.

Migration `0020` introduces tenant-bound review, outbox, finding and feedback tables.
A transactional outbox and lease-fenced worker use existing service conventions. The
modern dashboard includes read-only PR submission, changed files, diff display, finding
filters, evidence and feedback. A response authorization epoch prevents an old request
from restoring a detail view after access is denied. Existing issue and patch proposal
components are reused; linking findings into patch proposals is not yet implemented.

The P19.2 ledger still lacks an authenticated, worker-integrated authority, current
database identity binding, and verified local daemon/process egress controls. The ordinary proposal worker now refuses the network Ollama adapter even if its feature flags are enabled; synthetic mock-transport adapters remain test-only. Real-source Ollama inference remains blocked. Do not mistake a mock or a public-source read for
inference approval. Billing, live GitHub comments, comprehensive review policies, TypeScript
rules, independent quality benchmarks, privacy operations and production deployment are
not implemented or verified as commercial-ready.

Focused offline backend checks: 369 passed, 1 skipped (PostgreSQL row locks required),
0 failed. Frontend contract/unit tests: 114 passed, 0 failed/skipped. TypeScript, ESLint,
Node 24 build, Ruff, offline lock check and `git diff --check` passed. The Node build used
an existing dependencies symlink and reported 27 omitted standalone trace files, so
standalone packaging was not verified. No actual browser workflow was verified in this run.

## Read-only public PR and database checks

An anonymous read of [encode/httpx#3762](https://github.com/encode/httpx/pull/3762)
resolved GitHub PR ID 3269772971, base `ae1b9f66238f75ced3ced5e4485408435de10768`,
and head `f6be07fbbfb52b20e028e3a169004b67bf9c6289`. Its single requirements file
is outside the one supported Python rule, so this is **partial coverage**, zero findings,
and no verified changed-source blob. It does not demonstrate an authenticated live review,
feedback or browser workflow. A fresh disposable PostgreSQL 16.16 database with pgvector
0.8.7 upgraded through 0020 and Alembic detected no schema drift.

The 14-case synthetic scanner set is a rule-contract check authored with knowledge of
the implementation, not an independent holdout or evidence of commercial accuracy.
There were zero actual model inference calls and zero repository-code executions in this
work. Automated inference approval remains unimplemented and cannot be claimed verified.

A further PostgreSQL-backed selection passed 27 tests, with 0 failures or skips. It
used real disposable PostgreSQL but in-process application calls and synthetic GitHub
clients, not a live broker. The private cluster was confirmed stopped and its disposable
data and credentials were removed; the temporary Unix socket was absent. Normal services
were not intentionally accessed or restarted.

## Release assessment

| Capability | Status |
| --- | --- |
| Existing real issue investigation and source provenance | Previously verified on a scoped real issue; no new inference |
| GitHub PR review | Partially verified: live metadata/static path and separate application tests; no live persisted browser flow |
| Deterministic scanning | Synthetic rule-contract checks only; one Python rule, partial coverage |
| AI review and real-source inference | Blocked pending authenticated approval, exact identity binding and verified local boundary |
| Patch validation and export | Existing proposal-only workflow; not reverified end-to-end here |
| Finding feedback and tenant authorization | Tested through in-process synthetic API calls; live end-to-end still needed |
| Operational delivery | Existing outbox integration; new PR worker has not been verified through real Redis/Celery here |
| Privacy, billing, production deployment and beta readiness | Blocked by missing operational, policy, cost and security evidence |

Next priorities: complete a real persisted PR-to-browser review using supported source;
independently evaluate the scanner and add carefully validated rules; complete the
authenticated durable inference approval boundary and local process controls; implement
privacy, recovery, quotas and operations; and validate demand and costs with consenting
customer interviews before pricing or billing.


## Public Python PR follow-up

A read-only analysis of [encode/httpx#3690](https://github.com/encode/httpx/pull/3690)
(GitHub PR ID `2910330172`) pinned base `20380490fd0bd13c68704080754c1385bff96d69`
and head `350221558d4f079fc4ab3673d81a4bc730fbb9c3`. All four modified Python files
passed the existing blob, SHA-256 and diff checks; the narrow rule emitted zero findings.
This is only partial review coverage. No source was executed or sent to a model.

A separate in-process authenticated API and worker test against an isolated PostgreSQL
cluster failed: the GitHub anonymous API returned 403 rate-limit responses before the
worker could complete. The application retained a failed state. The test used synthetic
login/installation authorization and directly invoked the worker, so even a successful
rerun would not demonstrate actual Redis delivery or a browser. The test was not retried
against a normal or credentialed service. Its disposable PostgreSQL cluster, socket and
temporary test were removed.

The source client now caches at most 16 validated immutable Git trees per client, scoped
by repository, tree identity and a token fingerprint, reducing repeated tree reads within
one operation. Invalid or truncated trees are not cached. The source-client and PR test
selection passed 61 tests with no failures or skips; these include synthetic boundaries.
Caching does not guarantee avoidance of GitHub rate limits or change authorization rules.
The real PR-to-database/browser workflow and inference approval integration remain open.

The final expanded backend regression selection after the cache change passed **375**,
failed **0**, and skipped **1** PostgreSQL row-lock case in the SQLite run. Ruff, the
offline lock check and `git diff --check` passed. Frontend checks were not rerun in this
follow-up; the preceding 114-test result is recorded above.


### Commercial PR workflow follow-up

The opt-in synthetic PR test passed through real disposable PostgreSQL, Redis, a
dispatcher and Celery, including duplicate delivery and database-backed feedback
reads. GitHub fetch failures now fail the review rather than becoming completed
partial results. The real browser journey and authenticated GitHub access remain
unverified; see [commercial-pr-review-live-workflow.md](commercial-pr-review-live-workflow.md).


### Offline PR browser follow-up

The previously open browser gap has a scoped offline regression: real HTTPX data
replayed through the disposable application and appeared in WebKit; an original
synthetic finding and feedback survived reload. This does not establish authenticated
live GitHub access, durable retry or production readiness. See
[commercial-pr-review-browser-e2e.md](commercial-pr-review-browser-e2e.md).


### GitHub and review-quality follow-up

PR requests now persist verified same-repository base/head identities before enqueue,
and workers reject changed or unpinned identities. Bounded retries cover server and
network failures only. Live installation-token authentication, fork heads, rate-limit
retry, safe TypeScript analysis and independent quality evaluation remain open. See
[commercial-github-and-review-quality.md](commercial-github-and-review-quality.md).


## Commercial beta foundation update

An opt-in GitHub App installation-token issuer and durable rate-limit deadline
were added and tested with synthetic GitHub responses. Live installation-backed
access, fork heads, safe TypeScript analysis and independent review-quality labels
remain unverified. See [commercial-beta-foundation.md](commercial-beta-foundation.md).


## Beta gate-closure follow-up

Per-read PR authorization was strengthened and the stale synthetic harness test
corrected. Organization/private onboarding, fork heads, TypeScript containment and
independent labels remain open. See [commercial-beta-gate-closure.md](commercial-beta-gate-closure.md).


## Commercial alpha follow-up

A constrained public-fork path was added with pinned head identity and tested using
synthetic GitHub. TypeScript and live installation verification remain open. See
[commercial-alpha-product-milestone.md](commercial-alpha-product-milestone.md).


## TypeScript and real-fork follow-up

A narrow local-only TypeScript rule and a reviewer response workflow were added.
Live GitHub authorization and independent labels remain open. See
[commercial-alpha-typescript-and-live-fork.md](commercial-alpha-typescript-and-live-fork.md).
