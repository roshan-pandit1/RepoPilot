# First developer pilot: security and evidence

[DEVELOPER-LABELED] **Verdict: REPOPILOT — FIRST PILOT BLOCKED BY SPECIFIC SECURITY OR INTEGRATION GATES.** A real developer has not connected an authorized repository in this run. The live GitHub installation and independent security/quality review remain open.

## Execution gates

[MOCKED-GITHUB] **A — security path: partial.** Local contract tests cover forged installation ID, one-use and expired OAuth state, wrong account, cross-tenant access, repository removal, permission downgrade and stale-worker publication. OAuth state is bound to the pre-authentication browser cookie and PKCE attempt; it is not an already authenticated user-session identity. The new PR-specific check requires current `contents: read` and `pull_requests: read` installation permissions as well as user-visible selected repository access. The existing issue-investigation authorization contract was not broadened. The GitHub HTTP clients now ignore inherited proxy/certificate environment configuration and do not follow redirects.

[REAL-INFRA] **A — database gate:** migration through 0022 and Alembic drift passed in a newly created disposable PostgreSQL database. The final PostgreSQL/Redis/Celery selection passed 93 tests, 0 failed, 0 skipped. GitHub responses in those tests were synthetic.

[SYNTHETIC-FIXTURE] **D — TypeScript decision: conditional acceptance for a controlled local public-repository pilot only.** Keep the feature opt-in, use reviewed pinned Node and compiler hashes, do not expose private data, and do not enable it in production. This is a risk acceptance for a local pilot, not production isolation or a security certification.

[DEVELOPER-LABELED] **C — coverage:** no new rules were added. `PY-SHELL-001` reports a direct function parameter interpolated into a subprocess f-string with `shell=True`; shadowed names are conservatively excluded. `TS-EVAL-001` reports a direct `eval(identifier)` call on an added line, with LOW severity. It does not establish that the identifier is attacker-controlled, that the call executes a string, or that a vulnerability is exploitable. Literal calls, indirect calls and possible shadowing are outside its narrow scope. Both findings require pinned source evidence and are review leads, not verified fixes.

[DEVELOPER-LABELED] **B — BLOCKED.** The inspected process environment did not contain the RepoPilot App ID, App signing key, OAuth client configuration or user token. No normal-service configuration or unrelated credential store was inspected. No authorized local installation was supplied or used, so no live GitHub PR review was attempted. The previously reported anonymous PR metadata is historical context, not a live result from this run.

[HUMAN-LABELED] INDEPENDENT REVIEWERS: 0. INDEPENDENT ACCURACY: NOT MEASURED.

## GitHub security review and remaining risks

[MOCKED-GITHUB] The personal-account/public-repository path verifies the GitHub user ID, the App installation returned to that user's token, the selected stable repository ID and current permissions. An installation ID supplied by a browser is not accepted as proof. Organization and private-repository enrollment remain disabled. GitHub permission and repository visibility are checked before logical PR source reads and again before publishing.

[MOCKED-GITHUB] Revoked or downgraded authorization prevents subsequent logical source reads in the controlled tests. A stale lease cannot publish or consume its outbox. A 401, 403 or authorization-obscuring 404 now invalidates displayed PR data and fences late responses. Requests already transmitted cannot be recalled; GitHub state changes, webhook delivery and the local database are not one atomic transaction. Installation-token cache invalidation is process-local, and immediate global revocation is not established.

[DEVELOPER-LABELED] Credible remaining threats include compromised App signing keys, misleading or delayed GitHub visibility, authorization changes during an in-flight request, stale cached data in other interfaces, unreviewed proxy/network behavior outside these clients, and incomplete cross-process revocation. The `trust_env=False` change intentionally disables inherited proxy and certificate overrides for these GitHub clients; environments requiring a proxy need a separately reviewed configuration. No independent security review was performed.

## User-controlled setup checklist

[DEVELOPER-LABELED] After reviewing the risks, the user—not RepoPilot—may register a GitHub App and select **one public personal repository they control**. A conservative candidate is `roshan-pandit1/daytona` only if the user confirms the account ownership, current public visibility, and an existing suitable PR. Do not select `psf/requests` as an installation target unless the user is independently authorized to install on that repository.

[DEVELOPER-LABELED] Configure repository permissions **Metadata: read**, **Contents: read**, and **Pull requests: read**, with no write permissions. The existing issue-sync path may require separate Issues: read permission if used; the PR pilot does not require a write grant. The implementation intentionally rejects PR installations whose Contents or Pull requests permission is not exactly `read`.

[DEVELOPER-LABELED] For a local browser on the same machine, set `WEB_ORIGIN=http://localhost:3000` and the exact OAuth callback `GITHUB_CALLBACK_URL=http://localhost:3000/api/auth/callback`; any other origin must match the configured callback exactly. A webhook, if used, needs a separately approved reachable HTTPS ingress forwarding to `/v1/webhooks/github`; GitHub cannot deliver to localhost directly. No public ingress or tunnel was created. Store App/OAuth secrets, signing key, webhook secret and token-encryption key only in protected server-side configuration; do not paste secrets into chat. Install on the selected public repository, sign in through RepoPilot, and verify selection before starting a read-only PR review.

## TypeScript boundary

| Control | Decision | Evidence |
|---|---|---|
| Trusted Node/compiler | ENFORCED for configured SHA-256 matches; publisher authenticity is not established by a hash alone. | [SYNTHETIC-FIXTURE] |
| Parse-only compiler API | ENFORCED by the project runner's `createSourceFile` path; test source was not executed. | [SYNTHETIC-FIXTURE] |
| macOS process restrictions | OBSERVED-ONLY for tested canaries; not a hardened sandbox. | [SYNTHETIC-FIXTURE] |
| Filesystem controls | OBSERVED-ONLY for tested denied reads/writes; the profile is not a complete allowlist. | [SYNTHETIC-FIXTURE] |
| Network controls | OBSERVED-ONLY: a tested loopback connection was denied. | [SYNTHETIC-FIXTURE] |
| Memory | NOT ENFORCED as a hard full-process ceiling; Node heap is bounded and RSS is sampled. | [SYNTHETIC-FIXTURE] |
| Timeout | ENFORCED for child execution; runtime staging is outside that timeout. | [SYNTHETIC-FIXTURE] |
| Termination | ENFORCED for tested crash/timeout/output-limit paths; process-fork denial is a canary observation. | [SYNTHETIC-FIXTURE] |
| Child environment | ENFORCED minimal environment; synthetic credential inheritance was denied in the test. | [SYNTHETIC-FIXTURE] |
| Output validation | ENFORCED for tested version, path, hash, PID, rule and line constraints; it is not an independent semantic oracle. | [SYNTHETIC-FIXTURE] |

## Reviewer package and measurements

[DEVELOPER-LABELED] **Reviewer package: NOT SHAREABLE.** The existing 20-case manifest remains unchanged. The offline form contains 16 original snippets and now captures decision, file, line, category, severity, rationale, confidence, actionability, time and comments. Four public HTTPX references do not have shareable excerpts in the form. The project owner must confirm redistribution terms for the original fixtures and review the four public files' license/notice and contextual excerpts before external sharing. The original examples were authored with knowledge of the rule and are not an independent holdout.

[REAL-BROWSER] WebKit opened the offline form and exercised its file/category response export contract with a synthetic reviewer reference; the download was intercepted for contract validation and was not evidence of an external reviewer or a native saved-file test. No invitation or upload was sent.

[DEVELOPER-LABELED] Once terms and context are cleared, give the same blinded packet to at least three independent developers, collect separate response files without sharing analyzer predictions, resolve disagreements with a distinct adjudicator, and freeze the adjudicated ground truth before loading predictions. The CLI writes a new freeze file without overwriting and requires matching frozen bytes before its scoring command. It cannot verify human identity, reviewer independence or prevent out-of-band prediction exposure. The evaluator reports sample sizes, supported coverage, precision, recall, location/rule matching, duplicates and Wilson intervals where denominators exist; small or biased samples do not establish commercial accuracy.

[SYNTHETIC-FIXTURE] The authorized PR-detail API now returns aggregate-only pilot metrics from stored review state: status, elapsed time for terminal reviews, counts of recorded checked/not-fully-checked files, returned findings and the current user's useful/dismissed feedback. It does not put source or file paths into the metrics object. Finding opens, patch opens, model invocation counts and compute cost are explicitly unmeasured rather than fabricated. File counts exclude unrecorded files; inventory limitations remain visible separately.

[REAL-BROWSER] In the final isolated synthetic run, one TypeScript finding and useful feedback survived refresh. A simulated repository removal then caused the displayed review and source identity to clear. The review was completed with partial coverage; the recorded creation-to-completion interval was 2.33 seconds for one fixture, not a production latency measure. No real developer's usefulness, willingness to return or cost per review was measured.

## Verification record

[MOCKED-GITHUB] The focused local security, review and evaluation selection passed 163 tests, failed 0 and skipped 1 PostgreSQL-only row-lock test. These tests use synthetic GitHub responses and overlap other selections.

[REAL-INFRA] The disposable PostgreSQL/Redis/Celery selection passed 93 tests, failed 0 and skipped 0, including real broker delivery and the PostgreSQL row-lock case. The database and broker used synthetic GitHub and source fixtures.

[SYNTHETIC-FIXTURE] The macOS TypeScript boundary and Python/TypeScript rule selection passed 63 tests, failed 0 and skipped 0. The reviewer reconciliation and scoring selection passed 16 tests, failed 0 and skipped 0. These counts overlap neither a human study nor a live GitHub review.

[DEVELOPER-LABELED] Frontend unit/contract tests passed 121, failed 0 and skipped 0; TypeScript compilation, ESLint and the Node 24 build passed. Ruff, offline dependency lock verification and `git diff --check` passed. The temporary build used symlinked dependencies and emitted standalone-tracing warnings; standalone packaging remains unverified.

[REAL-BROWSER] Desktop WebKit at 1440 × 900 verified the synthetic PR review, useful feedback after refresh, recorded-file coverage wording and revocation clearing. A separate WebKit check verified the offline reviewer form's synthetic response contract. Mobile behavior was not reverified in this run.

[REAL-INFRA] Owned disposable services, temporary credentials and databases were removed and their ports checked closed. Prior checkpoints and fixtures were preserved. No production migration, normal-service restart, reviewed-source execution, model inference, GitHub write, deployment or billing action was performed.

## Acceptance table

| Gate | Status | Evidence class and limit |
|---|---|---|
| Public GitHub connection | BLOCKED | [DEVELOPER-LABELED] No authorized installation supplied in the inspected environment. |
| Authenticated PR review | PARTIAL | [MOCKED-GITHUB] Synthetic user and GitHub responses only. |
| Public fork retrieval | PARTIAL | [MOCKED-GITHUB] Fork contract exercised with a synthetic head. |
| Source identity verification | VERIFIED | [SYNTHETIC-FIXTURE] Hash, blob and diff checks exercised on fixture bytes. |
| Python rule review | VERIFIED | [SYNTHETIC-FIXTURE] Narrow rule regressions, not an accuracy benchmark. |
| TypeScript pilot analysis | PARTIAL | [SYNTHETIC-FIXTURE] Controlled macOS local-only path; no production isolation claim. |
| Human feedback | PARTIAL | [REAL-BROWSER] Synthetic user action persisted; no actual developer evaluation. |
| Independent benchmark | BLOCKED | [HUMAN-LABELED] Zero independent reviewers and labels. |
| Production security | NOT ATTEMPTED | [DEVELOPER-LABELED] No independent production security review. |
| AI patch generation | NOT ATTEMPTED | [DEVELOPER-LABELED] Real-source inference remains guarded and unauthorized. |
| Billing readiness | NOT ATTEMPTED | [DEVELOPER-LABELED] Billing was not activated or assessed for launch. |

## Next actions before charging

[DEVELOPER-LABELED] First, independently review the public-only authorization and revocation path, then the user can configure their own read-only App and selected public repository. Next, complete one live authenticated PR workflow, obtain at least three independent reviewer responses after licensing clearance, establish private-data retention/deletion and incident operations, and review production isolation, deployment and the separate real-source inference approval boundary. No willingness to pay or customer value has been measured.
