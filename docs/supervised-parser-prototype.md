# Test-only supervised parser prototype

The original prototype remains an opt-in **synthetic-only experiment**. Step
2B.3H.10 subsequently copied its reviewed supervision boundary into application
code behind a separate, disabled-by-default flag. Neither version is approved
for public-repository processing or normal-service activation. The existing
`INDEX_MULTILINGUAL_ENABLED` default is unchanged.

## Current boundary

`process_index` calls `collect_source` inside the Celery worker. By default the
collector calls `analyze_source` and then `chunk_python` for Python or
`chunk_multilingual` for other registered languages. Python analysis uses
`ast`; Tree-sitter constructs a language, parser and tree in `analyze_source`
and traverses node properties and named children there. Those native objects
do not cross an explicit thread or process boundary in this path; only plain
analysis and chunks return to the collector. Python exceptions can trigger
fallback, but SIGSEGV can terminate the whole worker. Existing job leases,
late delivery and retries must not be assumed to contain repeated native
crashes without further integration tests.

The original prototype is in `apps/api/evaluation/supervised_parser.py`, with its
separate child, controlled failure simulator and tests in the same directory.
For each request the parent creates a private temporary directory and copies
only the three current working-tree selection, analysis and chunking modules
and the fixed test child. The child uses the actual analyzer and chunker; it
never imports or executes source text. Each request gets a fresh interpreter.
There is **one attempt, no automatic retry**, and no process pool. A simulated
comparison child independently calls the same existing analyzer and chunker.

## Version 1 protocol

The request is a size-bounded, newline-delimited JSON object sent over stdin:
version, caller-provided 32-hex request ID, registered language, inert
`synthetic/` relative path, base64 UTF-8 source bytes, caller-expected SHA-256,
and a maximum chunk length. The parent checks the fingerprint and extension
before launching. Source is limited to 100,000 bytes; chunk length is 1–120
lines. No executable command, checkout path, model path, database URL,
credential or pickle object is accepted.

A complete response carries the request ID, source hash, path, language,
monitored worker PID, registry/parser version, grammar module and entry point,
parse status and fallback reason, imports, symbol metadata, and chunks with
inclusive line ranges, half-open UTF-8 byte ranges and content SHA-256. It
does not return source text or native Tree-sitter objects. The parent rejects
duplicate JSON keys, extra or missing fields, incorrect identities, mismatched
runtime/grammar versions, invalid line and byte ranges, gaps and overlaps,
incorrect source or chunk hashes, and more than 2,000 entries per list.
It reads at most 1,000,001 response bytes, rejecting anything over 1,000,000.
It never publishes a partial result. The hash of each chunk is a transport
integrity check; it is not the production evidence fingerprint, which also
binds snapshot, file and chunk identities. Production UUIDs remain random.

`parsed` means the analyzer reported success and a complete response passed
validation. `fallback` identifies analysis fallback, with its exact reason;
`unavailable` identifies a missing parser while retaining explicitly marked
line-window output. Python retains its existing `chunk_python` contract, so
an analysis fallback is not automatically proof that its independently run
chunker was lexical. A malformed Python syntax example did produce bounded
line windows. The collector normally skips certain line endings before
analysis; the prototype itself is not a substitute for collector screening.
Initialization failure, parser error, abnormal exit, timeout, memory-monitor
failure, sampled resource excess, oversized output, rejected output and
cleanup failure are distinct outcomes and return **no chunks**. A successful
structural validation cannot prove a native parser's semantic correctness.

## Isolation used for this experiment

On macOS the child receives a minimal environment and runs with `-I -S -B`,
so site initialization and `.pth` files do not execute. The disposable
environment's site-packages directory is added explicitly by the fixed child.
The profile denies network and Mach service lookup, process forks, reads under
`/Users`, `/Volumes` and `/private/var/folders`, data reads from unrelated
`/private/tmp` files, writes outside the private work directory and
`/dev/null`, and execution outside a small Python interpreter/launcher
allowlist. The profile permits system/runtime reads and temporary-path
metadata; it is not a complete filesystem allowlist. The venv itself is
readable and must contain only reviewed dependencies. Synthetic canaries
observed denial of loopback network access, an external temporary-file read
and write, and an unrelated executable replacement; `sandbox_check` reported
fork denial. Inherited credential/database variables were absent. These
canaries cover those specific operations, not every OS service or escape.

The child disables core dumps and sets CPU to 5 seconds soft/6 hard,
file-size to 1 MiB and open descriptors to 32. The parent imposes a default
10-second wall timeout (maximum configurable value 30 seconds) and samples
the monitored PID's RSS about every 100 ms using macOS `proc_pidinfo`; it
terminates the owned child above 768 MiB or on monitor failure. This is a
**sampled watchdog, not an enforceable hard memory limit**: a short spike can
be missed. Successful responses must identify the same PID the parent
monitors. Timeout and rejection tests confirm owned-child reaping; a failure
to kill or reap is reported explicitly as `cleanup_failed`. The no-fork
canary and executable allowlist do not by themselves prove that every
possible `posix_spawn` or native compromise is contained.

The policy is macOS/CPython 3.14-specific and fails closed when its disposable
environment or sandbox is unavailable. Real hostile-source processing needs a
separately reviewed OS isolation boundary, filesystem and secret mediation,
network/IPC restrictions, hard resource enforcement where supported, and a
supervisor that handles all child descendants. It also needs platform-specific
work for Linux deployment. The present sandbox and small fixtures do not prove
universal Tree-sitter stability.

## Synthetic verification

On macOS ARM64 with the existing disposable CPython 3.14.10 environment,
Tree-sitter 0.25.2 and the eight locked grammar packages, the final prototype
suite reported **64 passed, 0 failed, 0 skipped, 0 deselected**. All 15
registered extensions were checked against separate direct-parser child
processes, including Unicode and CRLF. Eleven malformed-syntax fixtures
reported fallback. Fingerprint and GitHub citation checks used fixed synthetic
snapshot identities. Simulations covered exceptions, explicit errors,
nonzero exit, SIGTERM, disappearance, timeout, truncation, invalid JSON,
oversized output, wrong request/process/source/parser/grammar/chunk identity,
bad ranges, missing coverage, unavailable grammar status and resource-monitor
failures. After each simulated worker failure, another request succeeded.
No native SIGSEGV was induced.

The separately run existing small parser and indexing regressions reported
**53 passed, 0 failed, 0 skipped, 3 deselected**. The three deselections were
the tests requiring publication/evidence database fixtures. Both pytest runs
reported one configuration warning because the cache plugin was disabled.
No database, Docker service, retained chi source, model or real repository
source was used. See [verification.md](verification.md#step-2b3h9--supervised-parser-prototype-2026-11-07)
for commands and earlier failed test attempts during development.
The temporary test environment has since disappeared; reproducing these
results requires a separately prepared disposable environment with the same
approved dependencies. No environment was installed or recreated in this step.

## Required production design and approvals

Any later integration would require a separate change: call a reviewed
supervisor from the collector/worker before publication; bind each response to
the tenant, repository, snapshot, commit, blob and source fingerprint in the
parent; and retain the existing authorization and source screening. Start with
one bounded request per child, not shared native objects. A future batching or
worker-reuse design needs independent review of lifetime and crash isolation.
Parser crashes and timeouts must be recorded as explicit file failures, with a
bounded per-file and per-job retry policy, lease/redelivery safeguards and
partial-snapshot warnings. An explicit product policy must choose skip versus
marked bounded fallback; neither may be described as syntax-aware success.
Publish only validated results atomically and expose sanitized failure metrics.

Before any activation, require review and approval of the production
integration, sandbox/OS portability and resource policy; tests for native
crashes, hostile input, process cleanup, lock ordering, concurrent retries,
tenant and snapshot fencing, publication atomicity, citations and evidence;
the outstanding full backend regression and separate PostgreSQL schema-drift
check; and a reviewed operational plan. Keep multilingual indexing disabled
until independently authorized. Rollback would disable the future supervisor
feature flag and stop admitting new multilingual jobs, then drain workers
under an approved operational plan. Do not rewrite old snapshots or silently
return to an unsafe in-process path. At the prototype checkpoint no such flag
or integration existed; the staged integration is described below.

## Step 2B.3H.10 — disabled-by-default integration

`app/modules/ingestion/supervised_parser.py` and its fixed child are derived
from the prototype. Test simulators stay under `evaluation/`. The original
prototype remains a separate historical test fixture, so the common boundary
currently has two copies; an AST regression test checks that the profile,
RSS monitoring, termination, pipe supervision and fixed child remain identical.
Consolidation and review of future changes are still needed to prevent drift.

The new `INDEX_MULTILINGUAL_SUPERVISED_PARSER_ENABLED` setting defaults to
`false`, as does `INDEX_MULTILINGUAL_ENABLED`. Python-only jobs retain their
existing path. A stored multilingual job uses the existing in-process parser
when the new flag is false, with the known native-crash risk. When the new
flag is true, multilingual jobs use the supervisor; a job's stored mode is
retained even if new multilingual admission is subsequently disabled. No
Compose or environment configuration was changed to enable either flag.
New jobs admitted with both flags set store `multi_supervised` in the existing
job mode field; snapshots retain the existing `multilingual` mode. If the
supervision flag is disabled before such a job is claimed, the job fails with
`supervised_parser_disabled` before source collection. A legacy queued
`multilingual` job uses supervision if the worker flag is enabled. No schema
or historical job record is changed. A legacy job's stored mode and snapshot
alone do not attest which parser path was used.

The collector correlates each response to an opaque request ID derived from
the repository, pinned commit, blob ID, path, source SHA-256 and a fresh nonce.
Only the opaque ID and necessary source metadata reach the child. It validates
the returned protocol again before constructing `SourceChunk` objects. A
parser or isolation failure raises a sanitized `CollectionError`; the worker
marks the job failed with `supervised_parser_<outcome>`, exposed by the
existing authorized index-status route. It does not retry the child or publish
any partially collected files. Explicit syntax fallback or missing-grammar
line windows preserve their existing `parser_status`, and are not described as
syntax-aware output. Existing tenant checks, fenced publication transaction,
random UUIDs, source hashes and citation handling remain in place.
Unavailable isolation reports `supervised_parser_isolation_unavailable`;
`sandbox-exec` exit 71 reports `supervised_parser_isolation_or_launch_failed`
because that exit does not distinguish policy failure from executable launch
failure. Child initialization failure remains a separate status. A child
terminated by a signal records only its signal number in the sanitized job
error code; it does not record source, paths or credentials.

The implementation intentionally retains the prototype's macOS-only
prerequisites: `sandbox-exec`, a disposable venv under `/private/tmp`, and the
reviewed profile. Missing prerequisites fail closed. Linux containers, the
normal macOS application venv and any environment without that boundary do not
silently fall back to in-process parsing when supervision is requested. A
separately designed and tested Linux filesystem, process, network and
resource isolation mechanism is still required. The prototype's 10-second
wall timeout, 5-second soft CPU limit and sampled 768 MiB RSS watchdog are
experiment limits, not demonstrated production limits; up to 1,000 files could
also exceed the current worker's overall deadline. The 200-character path,
100,000-byte source, item-count and response limits may reject otherwise valid
input. Such rejection fails the job rather than publishing partial chunks.

The current step's **62** synthetic integration tests passed using controlled
child responses and in-memory SQLite. They test all extension dispatches and
the actual validator, but do not prove real grammar behavior. A separate suite
passed **25** sandboxed child/transport checks using an existing base
interpreter: normal, malformed and long synthetic Python, an explicit
missing-Go-grammar fallback, 20 controlled failure cases and one isolation
canary. That suite deliberately does not bypass or claim to exercise the
production `run()` isolation-availability gate. An existing regression
selection reported **71 passed, 16 skipped, 17
deselected**. The skipped/deselected cases and missing disposable environment
are described in [verification](verification.md#step-2b3h10--feature-flagged-supervisor-2026-11-08).
No new PostgreSQL run or complete supervised multilingual run was possible.

Before activation, separately authorize restoration of a disposable environment
with the locked Tree-sitter and grammar wheels, including any required verified
downloads or installation. Run the complete actual child/collector matrix and
failure-containment tests under the approved isolation boundary, then the
reviewed disposable PostgreSQL publication, retry, tenant, evidence and
schema-drift gates. A production sandbox and resource-policy review, Linux
implementation and operational rollout approval are still required. Roll back
by leaving or setting the new flag false in an independently approved rollout;
do not silently replace supervised execution with in-process parsing for jobs
already admitted under an isolation guarantee. No runtime was activated here.

## Step 2B.3H.11 — synthetic integration verification

The requested disposable environment and database were subsequently restored
under separate authorization. The actual application `run()` gate and
supervised collector passed synthetic native checks for all 15 registered
extensions, including the installed Go grammar; the native/prototype suite
reported **119 passed**. The selected PostgreSQL regressions reported
**322 passed and one deselected**, and a separate native-child PostgreSQL
publication and schema suite reported **3 passed**. The fresh-schema upgrade
to 0016 and a separate `alembic check` passed. The runner's safety suite passed
**44 tests**. Afterward, **2** targeted `run()` checks for an unavailable or
unreviewed interpreter also passed. No suite had failures or skips.

The PostgreSQL native-child test uses a test-only socketpair broker because
macOS does not allow the two Seatbelt profiles to nest. The database test
process retains its one-port sandbox; a clean broker without database
credentials calls the real `run()`, which launches the network-denied parser
child. Only the worker's `_execute` transport is proxied in that test. The
broker's own IP socket guard is Python-level, not an OS sandbox. Direct
collector-to-`run()` execution was separately exercised in the native matrix;
unproxied worker-plus-PostgreSQL execution in one process remains untested.
See the [verification record](verification.md#step-2b3h11--supervised-parser-verification-2026-11-08)
for the artifact inventory, exact commands and remaining scope limitations.

Both flags remain off in normal services. The macOS sandbox is not a reviewed
Linux isolation mechanism or a complete hostile-source security boundary.
The 10-second timeout, five-second soft CPU limit and sampled 768 MiB RSS
watchdog are still experimental; full backend regression and native-crash
root cause remain open. Further OS isolation and operational review, real
source processing, and activation each require separate authorization.
