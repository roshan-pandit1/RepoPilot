# Patch workflow verification and release blockers

The synthetic workflow tests use an authenticated synthetic investigation, a deterministic
test-only provider, verified index chunks, a validated diff, a disposable temporary workspace,
the transactional outbox and an explicitly unavailable test executor. They do not execute
source, call a paid provider or write to GitHub. The frontend presents the proposal separately
from static validation, unavailable tests and human review. An approval means only approval
for further review.

Run the focused backend checks from `apps/api` with a prepared test environment:

```sh
python -m pytest -q tests/test_patch_proposals.py tests/test_patch_validation.py
```

The ordinary test fixture uses SQLite when `TEST_DATABASE_URL` is unset. That is useful for
synthetic application checks but is not PostgreSQL concurrency or migration evidence. Use the
reviewed [disposable PostgreSQL harness](tree-sitter-disposable-postgres.md) and its verified
test-only database before relying on database integration results. Never target the normal
application database; the fixtures drop tables.

Release blockers:

- No real patch provider has been reviewed or configured; no generated patch from a model has
  been evaluated, and the provider interface currently returns unavailable.
- A fixed registry and Docker adapter exist for two original test-only fixtures, but the
  real preflight failed its network-interface check. No actual before/after fixture test has
  run; no reviewed sandbox for untrusted repository code exists.
- No real repository patch, issue fix, production activation, normal migration, deployment or
  GitHub publication has been performed or authorized.
- An isolated test suite cannot establish correctness for an entire repository; independently
  assess test coverage, authorization, secrets, resource limits, network isolation, data
  retention and recovery before a release.
- The existing Tree-sitter native crash history and supervised-parser production-isolation
  limitations remain separate concerns. Both multilingual flags remain disabled by default.

On 2026-11-12, the reviewed disposable PostgreSQL harness ran with the patch tests added to
its required cases. The final run used a unique temporary, SCRAM-only PostgreSQL container,
verified its marker, loopback port, image identity and lack of application mounts, and
removed that container after testing. It reported **372 passed, 0 failed, 0 skipped,
1 deselected** in its selected PostgreSQL suite. This includes the synthetic proposal
lifecycle, cancellation fencing, tenant authorization and concurrent idempotency. A separate
native PostgreSQL suite reported **3 passed** and included upgrade to Alembic head `0017` and
a PostgreSQL schema-drift check. The native synthetic parser suite reported **120 passed**;
the harness safety checks reported **44 passed**. One real local Git-object benchmark fixture
was deliberately deselected. The earlier parser test results do not prove universal native
stability. See [verification](verification.md) for commands, other suites and limitations.

## P4 synthetic execution gate

The P4 registry, sandbox configuration checks, result validation, cancellation and stale
worker fencing have non-executing synthetic tests. Mocked driver results are explicitly
simulated. A real, trusted container probe on 2026-11-13 passed the inspected resource and
privilege policy but failed the loopback-only network-interface check; no fixture was run.
The status is **incomplete**, not a baseline-fail/patched-pass result. See
[patch validation](patch-validation.md) and [verification](verification.md).

The updated disposable PostgreSQL selection reported **398 passed, 0 failed, 0 skipped,
4 deselected**, including 26 synthetic/mock P4 cases. The three real P4 execution/preflight
cases were deliberately deselected; the fourth deselection was a separate local Git-object
fixture. The separate PostgreSQL migration/drift phase passed three tests. The test-only
executor therefore still has no successful actual before/after execution evidence.

## P4.1 isolation diagnosis

Read-only canaries in uniquely owned containers established that the sysfs count included the
`bonding_masters` control file and that the other nine non-loopback names were actual, down
virtual devices in the diagnostic processes' network namespaces. Concurrent containers had
distinct namespace identities. No external endpoint was contacted and no conclusion about
Internet connectivity is claimed. Runtime mount inspection also revealed three unapproved
read-only `/etc` mounts absent from Docker's declared `Mounts` list. The provenance and
information exposure of these mounts and kernel views remain unresolved.

The preflight now preserves its strict loopback-only and no-extra-sysfs-entry checks, checks
IPv6 records and the actual mount table, and rejects incomplete Docker security and network
inspection. The final real preflight returned `preflight_network_runtime_mounts`; **zero**
baseline or patched tests were executed. Mocked results cannot establish result propagation
for actual execution. The existing 398-test PostgreSQL result predates these changes; a new
database run was blocked because the verified uv 0.13.6 binary and offline wheelhouse were
missing. Restoring them and running the reviewed disposable harness requires separate
authorization to obtain any missing artifacts.

The non-database patch selection reported **66 passed, 0 failed, 0 skipped, 8 deselected**.
The mocked disposable-harness and pure comparison selection reported **52 passed, 0 failed,
0 skipped, 0 deselected**, plus 14 passed subtests. Both emitted a pytest configuration warning
because the cache provider was deliberately disabled. Ruff and `git diff --check` passed.
See [verification](verification.md#p41--network-and-mount-isolation-diagnosis) for commands
and limitations.

## P5 provider and browser verification

The provider request is now versioned and bounded, with validated snapshot, repository,
source-hash, citation and evidence-range identities and fixed instructions separated from
untrusted data. Configuration rejects missing required credentials or model identity; the
registry still returns unavailable. No hosted adapter is selected, no source was sent to a
provider, and no model inference occurred. The existing report-specific OpenAI client and
ledger are not patch-generation authorization.

The selected backend tests reported **176 passed, 0 failed, 0 skipped, 6 deselected** using
original synthetic responses and in-memory SQLite with network access denied. The 30-case
provider-contract subset was also run separately and passed. SQLite covers application
behavior here, not PostgreSQL concurrency. The six deselections were three PostgreSQL-only
cases and the three actual P4 fixture/preflight cases. The previously verified offline uv and
wheelhouse were unavailable, so no current disposable PostgreSQL test ran.

The existing frontend checks reported **94 passed, 0 failed, 0 skipped**; TypeScript and
ESLint passed. They used Node 26.13.0, outside the declared `>=22 <25` range. No supported
Node 22–24 installation was found, and a supported-Node production build remains blocked.
The prior Node 26 build is not evidence for that gate.

The system WebKit harness ran three synthetic browser scenarios: proposal generation through
review with unavailable test execution, provider unavailable, and unauthorized request.
All API responses were intercepted synthetic fixtures; this does not verify a real session,
network proxy or backend worker in the browser. The harness did not apply a patch or publish
anything. To reproduce it on macOS, make a disposable copy of `apps/web` excluding `.env*`,
`.next` and `node_modules`; point that copy's `node_modules` at the existing installation.
From the copy, start a **separate** loopback preview with `APP_ENV=production`,
`DEMO_AUTH_ENABLED=false`, `API_INTERNAL_URL=http://127.0.0.1:1`,
`NEXT_TELEMETRY_DISABLED=1`, and `node node_modules/next/dist/bin/next dev --webpack
--hostname 127.0.0.1 --port 3159`. From the repository root run
`swift apps/web/tests/patch-workflow.browser.swift`; stop only that preview afterward. The
preview used in P5 and its copied files were removed. No package was installed.

### Release matrix

`Prior` means a disposable PostgreSQL result predating P5; it does not verify the changed
provider contract. Browser entries describe intercepted synthetic responses. Security review
here is an implementation review, not an independent security sign-off.

| Area | Implemented | Synthetic | Disposable PostgreSQL | Browser | Real provider | Real repository | Security review | Production status / blocker |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Patch proposal generation | Yes | Mocked Ollama and synthetic provider passed | Prior | UI only | Four synthetic inferences abstained | No | Partial | Blocked: no accepted model-generated candidate or real-source verification |
| Real-provider configuration | Opt-in local Ollama | Missing config and real metadata checks passed | Not run for P7 | Unavailable state | Local synthetic inference completed; no candidate accepted | No | Partial | Blocked: candidate-generation verification and daemon-security review |
| Provider request and data handling | Bounded local transport | Mocked trust-boundary checks passed | Not current | N/A | Four synthetic requests; two exact requests captured; no candidate accepted | No | Partial | Blocked: production daemon identity, egress and data-handling review |
| Static diff validation | Yes | Passed | Prior | UI only | No | No | Partial | Blocked: real-source evaluation absent |
| Tenant authorization | Yes | In-memory tests passed | Prior | Denial fixture only | N/A | No | Partial | Blocked: current PostgreSQL and live access checks |
| Worker and outbox | Yes | In-memory lifecycle passed | Prior | Mocked status | No | No | Partial | Blocked: current PostgreSQL concurrency and operational review |
| Patch execution isolation | Test-only | Guard mocks passed | N/A | Unavailable state | N/A | No | Incomplete | Blocked: real isolation preflight failed |
| Before/after tests | Comparator only | Mocked outcomes | N/A | Unavailable state | N/A | No | Incomplete | Blocked: no fixture test executed |
| Frontend workflow | Yes | Component tests passed on Node 24 | N/A | Synthetic WebKit passed on the production build | No | No | Partial | Blocked: real provider and database integration |
| Supported Node build | Build script | Node 24 production build passed | N/A | Node 24 production preview | N/A | N/A | N/A | Verified locally; existing frontend dependencies were not reinstalled with `npm ci` |
| Migration 0017 | Yes | N/A | Prior upgrade and drift passed | N/A | N/A | N/A | Partial | Blocked: normal migration needs separate approval |
| Full backend regression | Existing suites | Selected tests only | Not current | N/A | No | No | Partial | Blocked: full verified environment and suite |
| Observability | Sanitized error codes | Failure tests passed | Prior | Error fixture | No | No | Partial | Blocked: operational monitoring and incident review |
| Cleanup and retention | Disposable cleanup | Mocked and preview cleanup | Prior | Preview removed | No | No | Partial | Blocked: durable proposal/provider retention policy |
| Deployment and rollback | Documentation only | N/A | Prior migration tests | N/A | No | No | Incomplete | Blocked: release review and separate authorization |

Before further provider work, explicitly approve additional model inference; approve transmission of any
identified real issue/source data separately and review the local
daemon's identity, egress restrictions and data retention. Real repository execution needs
an independently reviewed execution boundary and explicit source/test authorization; no
sandbox preflight may be bypassed.

### P7 local provider checks

The opt-in Ollama adapter has only been exercised with mocked HTTP responses and synthetic
source. It requires verified cloud-disabled status, a local GGUF completion model and the
configured model digest before a prompt is submitted. The worker applies the existing
evidence and diff validation and fences cancellation or stale source before publication.
The selected offline backend suite reported **234 passed, 0 failed, 0 skipped and 6
deselected**; 14 existing frontend patch/proxy tests passed. The six deselections are three
PostgreSQL cases and three actual patch-sandbox cases. PostgreSQL was unavailable; no P7
database migration, real inference or before/after patch execution ran. Loopback metadata
does not attest the local daemon or enforce its network isolation. See
[patch generation](patch-generation.md#opt-in-ollama-adapter) and the
[P7 verification record](verification.md#step-p7--local-ollama-patch-adapter-2026-11-14).

P7.1 installed the official Ollama 0.40.16 app and the single approved
`qwen2.5-coder:7b` model. Its local manifest digest and all blob hashes match the registry,
and the actual RepoPilot readiness method passed against metadata-only requests with daemon
egress denied. No inference was performed, the server was stopped, and normal patch flags
remain disabled. The model-store wrapper/alias distinction and measured download totals are
recorded in [P7.1 verification](verification.md#step-p71--official-ollama-and-model-artifact-verification-2026-11-14).

P7.2 ran exactly two locally sandboxed synthetic inference requests against that model. Both
returned valid structured abstentions: the model asserted that the implementation was
missing. The P7.2 setup intended to send the snippets, but the original outgoing bodies were
not retained. The second call used the actual
RepoPilot provider, which returned `local_model_insufficient_evidence`; neither call
produced a candidate for diff validation. The 143-case offline provider and patch suite
passed with one PostgreSQL case deselected. See the
[P7.2 record](verification.md#step-p72--local-synthetic-inference-2026-11-14). The daemon
was stopped, no model output was executed, and real-repository execution remains blocked.

P7.3A reconstructed the request structure with the current adapter and a mocked HTTP
transport. Both original synthetic implementations appeared in the intercepted JSON, but
that does not prove what the P7.2 daemon or model received. No definite cause for the
abstentions or causally demonstrated production-code defect was found. The focused offline
suite passed **151 tests**, with one PostgreSQL case deselected; no inference, Docker or
PostgreSQL was run. See the [P7.3A verification record](verification.md#step-p73a--offline-abstention-investigation-2026-11-14).

P7.3B then made exactly one authorized local synthetic request through the existing provider.
The exact request was captured before transport and contained the complete synthetic
function; the model nevertheless abstained because it said the full implementation was
unavailable. The request did not explicitly identify its snippet as the entire file. That
is a possible explanation, not an established root cause. No candidate was returned, no
diff or executable test was validated, and the temporary daemon was stopped. See the
[P7.3B record](verification.md#step-p73b--one-instrumented-synthetic-inference-2026-11-14).

P7.4 adds a versioned, evidence-bound coverage description. The synthetic complete-file
fixture was checked against an independently fixed size and hash; existing indexed files
remain `UNKNOWN_COVERAGE` because their original byte length is not persisted. One local
request with the complete-file notice still produced an abstention, with no candidate diff.
The offline selection passed **176 tests** with one PostgreSQL case deselected. No model
output was executed. See the [P7.4 record](verification.md#step-p74--source-coverage-and-one-synthetic-retest-2026-11-15).

P7.5 compared the current prompt and schema with a test-only alternative using mocked
transport. No prompt contradiction or cause of the four abstentions was established. The
backend structured parser now rejects an empty candidate before diff validation, preserving
the existing error outcome and abstention behavior; the model-facing schema is unchanged.
The proposed discriminated abstention format is incompatible with the existing parser and
is not enabled. The offline selection passed **192 tests** with one PostgreSQL case
deselected; no model was called. See the [P7.5 record](verification.md#step-p75--offline-patch-contract-comparison-2026-11-15).

### P6 toolchain and release checks

Node 24.18.0 and npm 11.16.0 were verified from the official macOS ARM64 archive; the
production build, TypeScript, ESLint, 94 frontend tests and three synthetic WebKit scenarios
passed. Browser requests used intercepted responses, and the standalone preview had an
unreachable backend. The first build's symlinked `node_modules` caused 27 output-tracing
omissions; copying the existing dependencies into the private build workspace removed the
warning and the required standalone files were present. This was not a clean `npm ci`.
The 14 patch component/proxy tests also passed when rerun separately; they are part of the
94-test total. The persistent cache contains the Node runtime, not a backup of
`node_modules`. To repeat the build, make a private disposable copy of `apps/web` including
its existing dependencies and excluding `.env*` and `.next`, then run from that copy:

```sh
p6_node_bin="$HOME/Library/Application Support/RepoPilot/toolchains/p6/node-v24.18.0-darwin-arm64/bin"
env PATH="$p6_node_bin:/usr/bin:/bin" NEXT_TELEMETRY_DISABLED=1 \
  /usr/bin/sandbox-exec -p '(version 1)(allow default)(deny network*)' npm run build
```

The default `~/.npm/_cacache` directory was absent at the P6 check. If the existing
frontend dependencies disappear, restoring them is a separate prerequisite; no npm package
download was authorized or performed in P6.

The Python 3.14.10/uv 0.13.6 offline toolchain and the selected locked wheel closure are
retained privately. The offline lock check, 44 mocked database-harness safety tests,
120 synthetic native parser tests and 176 selected backend tests passed. The backend
selection used SQLite where a database was needed; six PostgreSQL or real-sandbox cases
were deselected. Docker's selected socket disappeared before the reviewed runner created a
container, so **the P5 PostgreSQL regression, migration 0017 and separate schema-drift
checks were not run in P6**. The earlier disposable PostgreSQL evidence remains historical.
No real provider or patch execution was enabled. See the [P6 verification record](verification.md#step-p6--verified-toolchains-and-blocked-postgresql-gate-2026-11-13)
and the [reproducible harness instructions](tree-sitter-disposable-postgres.md#p6-persistent-test-toolchain).

### P8 — local candidate generation

The Ollama provider now accepts exact structured source edits and turns verified,
evidence-visible replacements into the existing validated diff contract. One actual
loopback-only Qwen2.5-Coder 7B inference on original synthetic code returned an edit that
passed the existing static validator. This was not patch execution or a correctness test.
The inference daemon was stopped after the request. The selected offline backend suite
passed 284 tests, with 3 PostgreSQL-marked tests deselected; Ruff and `git diff --check`
passed. No PostgreSQL suite, migration, Docker patch execution, or normal service was run.
The strategy defaults to structured edits while provider selection and proposal generation
remain disabled. See the [P8 verification record](verification.md#p8--local-structured-edit-generation-2026-11-15).

### P9 — macOS isolation evaluation

Inert macOS sandbox canaries denied network access, child process creation, and a canonical
unauthorized host path. A noncanonical deny was insufficient, and nested sandbox execution
failed in the managed tool environment. These observations do not verify a complete native
test-execution policy. A trusted-fixture adapter requires its own effective-policy preflight;
the Docker policy remains unchanged. See the [P9 verification record](verification.md#p9--trusted-synthetic-execution).

The strict filesystem allowlist prevented Python startup; the broader working denylist
does not establish secret isolation. Native execution remains blocked. The separate P8
synthetic fixture registry and native result validator are offline-only and are not wired
to worker execution. The selected suite reported 123 passed and 5 deselected, including
9 native registry/report cases; no fixture executed. PostgreSQL remains unverified.

### P9.1 — VM prerequisite inspection

The Apple Virtualization framework and Swift tools were found, but no verified ARM64 Linux
guest image or dedicated VM launcher was discovered in the inspected locations. The
managed-context Virtualization support query returned false, which is not a host-wide
determination. No VM or guest fixture ran. The new non-executing contract remains disabled
and returns an unavailable outcome; effective VM isolation and PostgreSQL persistence are
unverified. See [P9.1 verification](verification.md#p91--vm-execution-prerequisites).

### P9 final — actual trusted synthetic test

Four real host child processes ran the fixed arithmetic assertion on disposable copies.
The original subtraction function failed (exit 1); the retained P8 patch was applied to
the second copy and the reviewed addition function passed (exit 0). Existing comparison
logic returned `BASELINE_FAILED_PATCH_PASSED`. A separate control using the exact reviewed
addition source in both workspaces passed twice and returned `BOTH_PASSED`.

These were trusted host executions, not sandboxed repository tests. The existing service
rejects a completed unsandboxed host report rather than treating it as a publishable job
result. No worker or normal service was configured to run this fixture, and PostgreSQL
persistence remains unverified. See the current verification record for the precise
fixture identities and regression counts.

## P10 — application integration and provenance (2026-11-15)

The application path is composed from authenticated investigation and tenant
authorization, snapshot-bound evidence assembly, proposal plus outbox insertion in one
transaction, provider selection, source/evidence-bound generation, deterministic edit to
diff conversion, static validation, lease-fenced worker completion, authenticated proposal
reads and review decisions. The selected synthetic API tests exercise proposal lifecycle,
provider-unavailable states, cancellation, duplicate delivery, stale completion, review,
and the 409 rejection of unsandboxed completed test results. Provider and external GitHub
boundaries are mocked; this is not a new AI inference or PostgreSQL end-to-end run.

P10 adds migration `0018` for file byte length, encoding, normalization and coverage. The
collector records complete-file metadata only for a size-checked raw blob. Publication
reconstructs chunks and rejects a hash or length mismatch before replacing the published
snapshot. Legacy files remain `UNKNOWN_COVERAGE`. The source migration chain reports `0018`
as head. The legacy Alembic regression applied it to temporary SQLite; the chain and schema
drift were not verified against PostgreSQL.

The final focused offline backend selection passed 295 tests, failed 0, skipped 5,
deselected 0. Four skips require PostgreSQL row locks/full-text search/locking; the fifth
requires disposable PostgreSQL for migration verification. This selection used in-memory
SQLite where database fixtures were needed. PostgreSQL-backed
transaction, locking, migration, schema-drift and concurrency claims remain unverified.
The production execution policy is unchanged: host evidence with `sandbox_used=false` is
not a completed production test result.

## P11 — PostgreSQL-backed workflow verification

P11 supersedes the preceding PostgreSQL-blocked statement for disposable synthetic
integration. On private PostgreSQL 16.16, migration 0018, fresh schema drift and the legacy
upgrade path passed. PostgreSQL-backed pipeline tests passed **309**, synthetic capture
passed **50**, token counting **81**, provider-count integration **54**, and the final
migration/drift/proposal selection **31**. The broad PostgreSQL selection reported **1,200
passed, 1 failed, 6 skipped, 2 deselected**; the sole failure needs optional NumPy and is
reported, not hidden. No repository source or generated patch executed and no model
inference occurred. Production completion still rejects unsandboxed reports. See the
[P11 verification record](p11-postgresql-verification.md).

## P12 — completed PostgreSQL regression

The prior NumPy failure was an optional-extra installation gap: the project already declares
`numpy>=2.3,<3`, locked to 2.5.4, but the P11 base test venv did not include that extra. P12
verified the official locked ARM64 wheel hash and installed only that wheel into a disposable
test venv. The full PostgreSQL selection then reported **1,201 passed, 0 failed, 0 errors,
5 skipped, 3 deselected**. Migration/drift/legacy-upgrade selection passed **3**, and the
synthetic capture database suite passed **50**. Skips and deselections are itemized in
[P12 verification](verification.md#p12--numpy-regression-and-backend-completion-2026-11-16).

P12 made no model calls and ran no source code. The previously completed P8/P9 synthetic
milestones were not repeated. Production patch execution remains blocked until the dedicated
Linux KVM/Firecracker host and independent isolation review satisfy the [host
specification](p12-execution-host-prerequisite.md).


## P13 — disposable running application (2026-11-16)

Synthetic API, PostgreSQL, outbox/worker functions and review persistence were exercised with a fixture provider. The WebKit desktop display check passed after the temporary standalone assets were copied; mobile was not verified. Redis/Celery delivery was unavailable and the readiness check was false, so full running-stack integration remains incomplete. PostgreSQL selection: 78 passed; frontend: 94 passed; no model inference or patch execution. See the [P13 verification record](p13-application-workflow-verification.md) for boundaries, cleanup and results.


## P14 — real Redis/Celery application workflow (2026-11-16)

A disposable Redis broker and actual Celery solo worker processed the synthetic application workflow via the real PostgreSQL outbox and dispatcher. The statically validated proposal and authenticated review persisted. Broker outage recovery, duplicate delivery, and late delivery after queued cancellation were observed. Three measured browser viewports passed; active-worker crash recovery and several live negative scenarios remain unverified. Focused PostgreSQL tests: 231 passed; frontend tests: 94 passed. See the [P14 verification record](p14-redis-celery-integration.md) for exact boundaries and results.


## P15 — local reliability (2026-11-16)

An actual synthetic in-flight cancellation and killed-worker recovery after test-induced lease expiry passed. Expired worker errors now require a live lease; worker-aware readiness and a proposal-detail error-race fix were added. PostgreSQL selection: 243 passed; frontend: 95 passed. A live superseded-owner race and several live HTTP/browser failure cases remain unverified. See the [P15 reliability record](p15-reliability-verification.md) for exact evidence and limitations.


## P16 — local reliability and security (2026-11-16)

Two actual Celery workers exercised natural test-configured lease expiry and fenced late success and error; live synthetic tenant, source and provider checks also passed. The readiness response now explicitly identifies dispatcher health as unchecked. PostgreSQL selection: 246 passed; frontend: 96 passed. The live two-worker harness was temporary, browser network failure used interception, and production execution remains blocked. See [P16 local reliability closure](p16-local-reliability-closure.md).


## P17 — local closure and execution-host handoff (2026-11-16)

Live synthetic pre-acceptance tampering was rejected before provider invocation; contradictory COMPLETE_FILE provenance now fails closed and stale snapshot/evidence classification was corrected. The retained guarded opt-in test exercised two real Celery workers and passed. Dispatcher progress remains not_checked; readiness returns sanitized dependency reasons. PostgreSQL selection: 259 passed. See [P17 local closure and handoff](p17-local-closure-and-execution-handoff.md) for exact evidence, CI prerequisites and the Linux KVM/Firecracker decision.

### P18 proposal-only product

Candidate detail and review retain their existing contracts. Export reauthorizes access,
revalidates the current source and evidence, requires verified complete-file identities and
a saved patch SHA-256, and serves the exact candidate diff for manual use. Older records
without the digest need a static recheck; source records without complete identity need
verified reindexing. Approval is for further review, and automated execution remains
disabled. See the [P18 proposal-only record](p18-proposal-only-product.md).

## P19.1 — scoped upstream investigation

Upstream issue identity and a pinned partial inventory are represented separately
from fork ownership in a disposable investigation. Upstream/partial patch and report
generation remain fail-closed pending a durable one-shot exact-request approval path;
no real-source inference or executable patch validation occurred. See the
[P19.1 verification record](p19-1-upstream-issue-and-partial-snapshot.md).
