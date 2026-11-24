# P18: Proposal-only patch review and handoff

RepoPilot's existing investigation, evidence, source identity, structured-edit generation,
static validation and review services remain the basis of this workflow. An authenticated
user can inspect the candidate diff, changed paths, pinned snapshot, evidence references,
coverage classification and validation and review states. A candidate is not a verified
fix: automated tests may not have run, and approval means further human review only.

## Export contract

Copy and download fetch the canonical diff again through the authenticated API and Next.js
proxy. The API reauthorizes repository and tenant access, rejects stale, rejected or
unvalidated proposals, checks evidence and source identity and reruns static validation.
Each changed file must have independently verified complete-file provenance. The UTF-8
bytes must match both the digest bound to the saved static-validation record and the
requested SHA-256; the proxy and browser verify the hash again. The attachment name is
constructed from the proposal UUID. The response does not apply or execute the patch.
Legacy records without a bound patch digest require an explicit static recheck; older source
records without verified complete identity require verified reindexing before export.
Bounded evidence is labeled as an excerpt even if the full file is independently verified.

## Using the local workflow

In an isolated development environment with an authorized provider and proposal feature
configured, create an investigation with indexed source evidence, generate a candidate,
inspect its evidence and diff, then approve for further review or reject. A user may copy
or download an eligible candidate and manually decide how to apply and test it elsewhere.
Feature flags remain disabled by default. This milestone did not enable the normal service,
run the model, or execute source. Follow the existing configuration guidance in
[patch generation](patch-generation.md); do not connect real source to a provider without
separate authorization.

## Verification and remaining gates

A disposable PostgreSQL/Redis/Celery application with a deterministic synthetic provider
produced a statically validated candidate and served its exact 133-byte patch, SHA-256
`8d74d6e35955c7e3c7068fc709b09b4d59b2b4efcd6f17076d9b032e159150e7`.
Anonymous, cross-tenant and wrong-digest export attempts were rejected. A separate
PostgreSQL regression selection passed 259 tests and the export selection passed 15, with
no failures or skips. The in-process backend selection passed 309 with three PostgreSQL-only
skips; the frontend suite passed 99. Live WebKit displayed the proposal; an intercepted
download yielded a Blob with the canonical digest. OS file saving and the OS clipboard
were not exercised; clipboard behavior was checked in a unit test. This is synthetic
integration, not a new local-model or real GitHub test. See the P18 summary in
[verification.md](verification.md) for the final test and browser results.
Production patch execution remains disabled and needs a separately reviewed isolation
boundary. A future real-repository pilot also needs explicit source-transmission and
operational authorization; neither static validation nor review approval establishes that a
patch has been executed, tested, or is safe to merge.

### P18.1 — native download and clipboard verification

An isolated WebKit test used a native mouse event on the actual proposal Download button
(`isTrusted=true`). `WKDownloadDelegate` saved the browser-initiated file to a private
temporary directory. Its safe `.patch` filename, 133-byte size, exact equality to the
independent synthetic fixture and SHA-256
`8d74d6e35955c7e3c7068fc709b09b4d59b2b4efcd6f17076d9b032e159150e7` passed. The
proposal and export responses in this browser test were synthetic mocks; the existing
application authorization and exact-byte API checks were tested separately. This result
supersedes P18's earlier limitation that only an intercepted browser Blob was verified.

No isolated native system clipboard was established. The system clipboard was not read,
replaced, cleared or restored. Mocked tests cover clipboard gesture-time initiation,
verified bytes and permission denial; download failures and Blob URL cleanup are also
covered. The WebKit harness also removed its private files after a forced digest mismatch
and after a bounded timeout from an invalid download destination. These tests do not
establish a native clipboard write. If the user later chooses to replace their clipboard, an optional manual acceptance check is to click Copy on a
synthetic proposal, paste into a new UTF-8 text file without editing it, and compare that
file's bytes and SHA-256 with the downloaded patch.

The frontend selection passed 102 tests with no failures or skips; TypeScript, ESLint and
the Node 24 production build passed. The private-copy build warned that 27 traced files were outside the build root
because existing dependencies were symlinked. The focused in-process backend
security selection passed 126 tests with three PostgreSQL-only skips and no failures; it
covered authorization, stale source, hashes and rejected proposals. These are not new
PostgreSQL, model-inference or execution results. Temporary downloads and test processes
were removed. Automated real-repository execution remains disabled, and real-source use
and production release require separate authorization and security review.

P18.1 changed `apps/web/tests/patch-download.browser.swift`,
`apps/web/tests/patch-proposals.test.mjs`, and the three documentation records
`docs/p18-proposal-only-product.md`, `docs/verification.md`, and
`docs/repopilot-2-assessment.md`. No production application code changed. The opt-in
WebKit harness can be run with `swift apps/web/tests/patch-download.browser.swift` after
starting an isolated, test-only Next.js preview on `127.0.0.1:3817`; it supplies synthetic
application API responses and requires a macOS GUI session. It does not access the
clipboard or establish real API authorization.
