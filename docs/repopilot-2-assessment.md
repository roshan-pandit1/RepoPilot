# RepoPilot 2.0 — Step 1 multilingual indexing

**Current Go parser limitation:** a later synthetic diagnostic observed a
native Tree-sitter crash after parsing. The cause is unresolved and the
existing in-process fallback cannot catch SIGSEGV. The historical fixture
coverage below is not evidence that larger Go inputs are safe. Python-only
indexing remains the default; no mitigation has been deployed. See the
[synthetic crash investigation](benchmark-chi-1188-source-review.md#synthetic-only-native-crash-investigation).

## Architecture and scope

Python-only indexing remains the default. Set `INDEX_MULTILINGUAL_ENABLED=true`
in the API service environment **before submitting a new index job** to opt in.
The job records its chosen mode; retries do not change mode if configuration
changes. Legacy pending jobs with no mode remain Python-only. This does not
schedule or run a job by itself. Compose uses an explicit environment mapping:
setting a host shell variable alone does not propagate it to a container. A
separately reviewed Compose override or service deployment configuration is
required to pass the variable into the API service. Existing deployments and
the local application database were not changed.

The GitHub tree planner accepts only registered extensions in opt-in mode and
continues excluding unsafe paths, symlinks, dependency/build directories, and
credential-like filenames. In multilingual mode it also excludes recognizable
generated filenames such as `*.generated.*`, minified JavaScript, protobuf Go
output, and C# designer files; these safe-path omissions count as skipped. The
Python-only default keeps its previous selection rules. A previously indexed
generated-named Python file retains its citation eligibility.
Blob reads retain the existing Git SHA verification,
UTF-8, binary, sensitive-content, per-file, total-byte, file-count and chunk-count
limits. Unsupported source is never parsed or accepted. A known set of unsupported
source suffixes (`.rb`, `.php`, `.swift`, `.kt`, `.kts`, `.scala`, `.dart`,
`.vue`, `.svelte`) is counted as skipped and makes a snapshot partial; other
unrecognized extensions, including documentation and media, are ignored. These
counts do not measure the whole repository's source coverage.

`languages-v1` maps extensions to Python AST or pinned Tree-sitter grammars.
The collector keeps the existing Python chunker and its output unchanged. For
other languages it partitions all original lines into outer non-overlapping
syntax ranges and bounded 120-line windows. Nested symbols remain inside their
containing chunk, rather than producing overlapping chunks. For non-Python
files, malformed syntax, an unavailable parser, parser timeout, or node limit
produces line windows without symbol labels. In multilingual mode, files with
line separators that would make GitHub line numbers ambiguous are skipped and
counted as partial. Python
keeps its existing chunking even if the separate metadata analysis reaches its
node limit. CRLF and UTF-8 are preserved. Parser fallback is reported on files
and in index status; fallback does not mean source was skipped. Parsing does not
execute or import repository code. Import metadata contains line ranges, not
resolved dependencies.

Revision `0015` is additive. Nullable fields record each new job and snapshot's
indexing mode, a snapshot's recognized unsupported count, each file's language,
parser version/status and import ranges, and each chunk's symbol kind. Legacy
fields remain NULL; no snapshots, evidence, publication records or manifests
are rewritten. Tenant/repository foreign keys, existing source fingerprints,
publication provenance, commit-pinned citations and `terms-v2` remain in force.
The normal database requires a separately reviewed backup and migration approval
before running code that expects 0015.

## Fixture coverage

Search and citation use the same language-neutral lexical and citation paths;
the PostgreSQL integration fixture exercises TypeScript/TSX, Java and Go. Other
languages have syntax, symbol, import-range and chunk fixtures, but
do not have independently evaluated retrieval quality. This is not semantic
understanding or a claim of exhaustive grammar support.

| Language | Detection | Syntax parsing | Symbols | Imports | Chunking | Search | Citations | Tests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Python `.py` | Yes, default | AST | Top-level chunk labels; AST nested metadata | Line ranges | Existing Python partition | Existing lexical | Commit/lines | Existing and fixture |
| JavaScript `.js`, `.mjs`, `.jsx` | Opt-in | Tree-sitter | Supported definitions | Line ranges | Syntax + fallback | Shared lexical | Shared validator | Synthetic fixtures |
| TypeScript `.ts`, `.tsx` | Opt-in | Tree-sitter | Supported definitions | Line ranges | Syntax + fallback | Shared lexical | Shared validator | Synthetic fixtures; TSX PostgreSQL passed |
| Java `.java` | Opt-in | Tree-sitter | Supported definitions | Line ranges | Syntax + fallback | Shared lexical | Shared validator | Synthetic fixtures; PostgreSQL passed |
| Go `.go` | Opt-in | Tree-sitter | Supported definitions | Line ranges | Syntax + fallback | Shared lexical | Shared validator | Synthetic fixtures; PostgreSQL passed |
| Rust `.rs` | Opt-in | Tree-sitter | Supported definitions | Line ranges | Syntax + fallback | Shared lexical | Shared validator | Synthetic fixtures |
| C `.c`, `.h` | Opt-in | Tree-sitter | Supported definitions | Include ranges | Syntax + fallback | Shared lexical | Shared validator | Synthetic fixtures |
| C++ `.cpp`, `.cc`, `.hpp` | Opt-in | Tree-sitter | Supported definitions | Include ranges | Syntax + fallback | Shared lexical | Shared validator | Synthetic fixtures |
| C# `.cs` | Opt-in | Tree-sitter | Supported definitions | Using ranges | Syntax + fallback | Shared lexical | Shared validator | Synthetic fixtures |

`.h` is treated as C; headers requiring C++ syntax may fall back to line windows.
The adapters do not resolve dependencies, identify every export, or extract every
language construct. CIE-v1 remains Python-only and explicitly omits other-language
evidence. A lexical result is candidate evidence, not a verified cause.

## Dependency provenance

`apps/api/uv.lock` pins Tree-sitter 0.26.0 and grammar wheels: JavaScript 0.25.0,
TypeScript 0.23.2, Java 0.23.5, Go 0.25.0, Rust 0.24.2, C 0.24.2, C++ 0.23.4,
and C# 0.23.5. Package metadata and the Tree-sitter distribution license identify
MIT licensing. The lock was resolved with uv 0.13.6 and installed into a fresh
temporary environment with `uv sync --locked`. No grammar downloads occur during
parsing, and no AI model weights or calls are involved.

## Boundaries

This step does not implement real vector models, root-cause verification, or
automated repair. The existing fake embedding provider is not relevance evidence.
No existing application repository was reindexed, no normal database was
migrated, and no application investigation or report was created. See
[verification.md](verification.md) for actual test results and limitations.

## Step 2A — vector-search foundation

The backend now includes an opt-in local ONNX adapter, versioned representation
contracts and chunk fingerprints, exact pgvector search, and an offline held-out
capture evaluator. Revision 0016 is additive and has not been applied to the
normal application database. Legacy fake embedding records are preserved but
their unverified links are not reused by the new search. See
[vector-search-foundation.md](vector-search-foundation.md) for model candidates,
security and resource limitations, evaluation requirements and setup boundaries.
Controlled vectors and a synthetic graph validated mechanics only at that
checkpoint. The model artifacts and a later limited real-model smoke test are
described below; semantic relevance remains unevaluated.

## Step 2B — CodeRankEmbed preparation

The local adapter now separately binds the export and tokenizer revisions,
normalizes the CodeRank query instruction to exactly one prefix, and validates
the documented graph signature and BERT special-token positions. The contract
version changes, so existing local vectors from the previous contract are not
silently reused. Synthetic tests do not establish real-model behavior.

The selected third-party export's ONNX LFS SHA-256 and exact size are available
from public metadata. The tokenizer's downloaded bytes and Git blob ID were
verified and a SHA-256 calculated; an independently published tokenizer SHA-256
and the exact upstream commit used to build the export remain unverified. The
export and current upstream tokenizer Git blob IDs differ. The artifact
manifest, publisher parity claim, offline evaluation procedure and remaining
blockers are recorded in [vector-search-foundation.md](vector-search-foundation.md).

The first separately authorized real-model smoke test stopped at preflight:
the approved disposable runtime environment lacks the adapter's required
`tokenizers==0.23.3`, and installing it was not authorized for that test. No
real inference or application embeddings ran at that checkpoint. The prior
CPU-only synthetic graph passed, while kernel-registry introspection reproduced
a native crash.

After separate approval for the tokenizer dependency, a retry successfully ran
one CPU-only session using only a fixed synthetic query, code example and query
repeat. The 768-dimensional CLS vectors were finite, normalized and repeatable
in that run. The kernel-registry crash remains unresolved; upstream numerical
parity and retrieval quality remain unverified. No application repository
embeddings were generated. See [verification.md](verification.md) for results.

## Step 2B.3A — disposable synthetic retrieval capture

The development-only capture runner now joins the production investigation
`terms-v2` query builder and retriever to exact pgvector search and existing
reciprocal-rank fusion over one verified synthetic snapshot. It accepts only a
registered, hash-pinned synthetic fixture with manually controlled vectors;
the command requires a marked, empty disposable PostgreSQL database. Its
Python/TypeScript fixture, fake commit and fixture-derived labels test capture
and scoring mechanics only. The runner does not invoke CodeRankEmbed or accept
real repository data.

The `issue-context-v1` schema preserves title, body, labels, full ordered
comments and issue identity. Production `terms-v2` does not currently use
comments, which the capture states explicitly. The new `heldout-v2` contract
checks context and predeclared configuration against supplied captures;
`heldout-v1` remains available as legacy query-only input. See
[retrieval-capture-dataset-v1.md](retrieval-capture-dataset-v1.md) for the
fixture, command, scoring assumptions and independent labeling protocol, and
[verification.md](verification.md) for actual tests.

No independently labeled real held-out dataset, authenticated real-data
capture runner or CodeRankEmbed relevance benchmark exists yet. A future
real-data run requires a separately reviewed corpus, isolation and resource
plan and explicit approval for model inference on that corpus. The unresolved
kernel-registry crash, export provenance and upstream numerical parity remain
limitations.

## Step 2B.3B — real benchmark provenance preparation

An opt-in preflight now checks local Git commit/blob identities, exact source
ranges, SHA-256 content hashes and production chunk fingerprints against a
declared inventory, then compares snapshot/tenant/repository, query,
configuration, model and citation identities across supplied captures. It
rejects duplicate issue identities and straightforward pilot/held-out leakage.
Git replacement refs are disabled for the existing offline Git reader. These
are consistency checks: capture origin, live authorization, independent labels
and complete snapshot membership cannot be proved from supplied files.

The [dataset and execution proposal](retrieval-capture-dataset-v1.md#real-data-selection-and-independent-annotation-plan)
targets a 20–30 issue pilot and an eventual 100-plus issue held-out set across
multiple licensed projects; neither corpus exists yet. Local information was
insufficient to verify a three-to-five-repository shortlist, so selection is
pending. No public source or issue data was downloaded and no CodeRankEmbed
inference was run. On 2026-11-07 the focused synthetic Git and disposable
PostgreSQL suite passed **132 tests with no failures or skips**. The test used
a uniquely named, SCRAM-protected temporary database and did not access the
application database. See [verification.md](verification.md) for the prior
Docker interruption, the isolated rerun and the limits of these checks.

## Step 2B.3C — source-selection request

The [unapproved source manifest](benchmark-source-approval-v1.md) now proposes
three public repositories, one metadata-pinned commit each, and ten issue-title
leads for a possible pilot. Python, JavaScript and Go are represented. All
source/issue downloads, local retention, embeddings and inference remain
unapproved, and no real relevance judgments or held-out examples have been
created. A commit date before an issue-list date does not prove source
applicability or pre-fix status; every candidate remains subject to review.
Only public repository, commit and issue-list metadata and license files were
inspected. No issue body, comment, code, patch or diff was downloaded.

## Step 2B.3D–F — scoped HTTPX review

Subsequent separate approvals allowed four HTTPX issue contexts to be retained,
three pinned Python files to be reviewed for #3734, and a bounded #3734
historical-metadata check. GitHub reports that the pinned commit is an ancestor
of a later commit referenced by the issue, whose message claims a fix. The
reporter's actual HTTPX revision is still unknown, so #3734 remains
`SOURCE_APPLICABILITY_UNRESOLVED` and has no positive benchmark label. The
[review packet](benchmark-httpx-3734-source-review.md) records the evidence,
limits and three existing replacement leads. No other issue context or source,
CodeRankEmbed inference, embedding or real benchmark was authorized by the
historical-metadata review. The broader machine-readable source manifest
remains denied by default.

## Step 2B.3G — replacement issue triage

Three separately approved Express and chi issue contexts were retained
privately and validated against `issue-context-v1`. The
[triage record](benchmark-replacement-issue-triage-v1.md) recommends chi #1188
for a later source review: the reporter gives chi `v5.3.2` and a seven-character
master commit matching the proposed snapshot prefix. The full identity,
historical applicability, reported behavior and any source relevance remain
unverified. No source or Git object, model inference, embedding or benchmark was
included in this triage; no real relevance label was created.

## Step 2B.3H — chi #1188 pinned-source review

Under separate approval, GitHub metadata resolved the reporter's short SHA to
the proposed chi commit, and five Go files from that tree were retained and
hash-verified. The [review packet](benchmark-chi-1188-source-review.md) finds
`APPLICABILITY_SUPPORTED` for independent human review, not a reproduced bug,
root cause or relevance label. The selected files are a partial snapshot.
The local `tree_sitter` and `tree_sitter_go` packages were unavailable, so
only the explicit bounded fallback was checked on these files; syntax-aware
Go parsing remains an outstanding verification item. No Go code or test,
model inference, embedding or real retrieval benchmark was executed.

## Step 2B.3H.2 — synthetic Go parser crash investigation

The earlier larger synthetic failure was localized to node access during
traversal after parsing; its underlying cause remains unknown. The installed
Go grammar ABI falls within the runtime's reported supported range, and four
small synthetic cases plus the focused small Go test passed under an offline
sandbox. No larger crash-prone probe or retained chi file was run in this
step. A version comparison in disposable environments is a proposed next step,
not an implemented dependency change or a validated fix at that checkpoint. The five-file
syntax-aware check remains blocked; independent human source review may still
proceed without a gold label. See
[verification.md](verification.md#step-2b3h2--synthetic-only-tree-sitter-crash-investigation-2026-11-07).

## Step 2B.3H.3 — Tree-sitter 0.25.2 synthetic Go experiment

The separately approved disposable Go experiment passed four small cases, a
200-function case and four independent runs of a 700-function case using the
unchanged RepoPilot adapter and chunker. The grammar ABI was compatible and
no fallback was substituted for those successful cases. This makes 0.25.2 a
candidate for a separately approved cross-language compatibility matrix; it
does not establish universal safety or authorize a production dependency
change. The earlier 0.26.0 crash cause remains unknown, and the five retained
chi files were not read or parsed in the experiment. See
[verification.md](verification.md#step-2b3h3--tree-sitter-0252-synthetic-go-compatibility-2026-11-07).

## Step 2B.3H.4 — synthetic cross-language compatibility

The authorized disposable Tree-sitter 0.25.2 matrix passed all 15 registered
extensions, with an independent repeat per extension and a larger workload for
each grammar. The existing analyzer, chunker and in-memory collector were
unchanged. The [matrix report](tree-sitter-0252-synthetic-matrix.md) records
wheel and fixture hashes, ABI checks, fallbacks and resource limits.

Production snapshot, file and chunk IDs are generated with random UUIDs, so
deterministic ID generation across new publications is not provided. The
matrix tested fingerprint repeatability with fixed synthetic IDs; it did not
establish deterministic production IDs or run database publication tests.
The task-level compatibility verdict remains **incomplete** for that
requirement. No production dependency or application behavior changed.

## Step 2B.3H.5 — staged Tree-sitter runtime update

The user clarified that random publication UUIDs are the intended existing
contract: deterministic source processing does not require identical IDs
across publications. The local dependency declaration and uv lock now stage
Tree-sitter 0.25.2 without changing the eight grammar versions or any
unrelated locked package. Synthetic identity tests, the supervised 700-function
Go regression and the 40-process language matrix passed; the broader
disposable SQLite run passed 200 tests and skipped seven PostgreSQL-only
cases.

The Docker daemon was unreachable, so the required disposable PostgreSQL
publication, isolation and migration checks did not execute. The staged
update is **incomplete and not ready for activation**. The lock retains common
macOS and Linux x86-64/ARM64 wheels for CPython 3.12–3.14, but 0.25.2 lacks
the Linux RISC-V wheel present in the prior lock. No normal service, database,
snapshot, identity contract or production parser code was changed. See
[verification](verification.md#step-2b3h5--staged-tree-sitter-0252-update-2026-11-07)
and the [guarded rollback](tree-sitter-0252-synthetic-matrix.md#guarded-rollback-of-this-staged-pin).

## Step 2B.3H.6 — staged PostgreSQL recovery attempt

The Docker daemon was still unreachable, and the previously prepared
temporary runner, test environment, verified wheels and rollback backups were
no longer present. A reconstructed candidate runner stopped at its missing
environment preflight; none of its Docker or database guards ran. The seven
PostgreSQL-only cases therefore remain unexecuted, and the staged update is
still **incomplete and not ready for activation**. The prior exploratory
fixture-dependent failures remain unverified rather than being counted as
passes. See the [recovery record](verification.md#step-2b3h6--staged-postgresql-recovery-attempt-2026-11-07).

## Step 2B.3H.7 — durable verification harness

A repository-local [test-only procedure](tree-sitter-disposable-postgres.md)
now stages a hash-manifested working-tree copy and checks a fresh offline
environment and disposable database before running the release suite. Its
38 standard-library safety tests passed with fake external commands. The
actual offline installation, Docker isolation, PostgreSQL tests and migrations
were not run in this milestone. uv 0.13.6 and a verified wheelhouse have not
been supplied or verified. The prior temporary rollback copies are unavailable,
and the staged runtime is **not ready for activation**. The earlier exploratory failures
remain documented; this is not a full-suite regression result.

## Step 2B.3H.8 — disposable PostgreSQL gate

The selected staged-runtime suite ran against a new disposable PostgreSQL
instance with temporary data, SCRAM, loopback-only exposure and verified
ownership. It reported **260 passed, 0 failed, 0 skipped, 1 deselected**;
the seven previously skipped cases and the PostgreSQL migration test executed.
The container was independently confirmed removed. A verified local wheelhouse,
offline lock check, isolated environment and source manifest supported the
run. See the [verification record](verification.md#step-2b3h8--disposable-postgresql-gate-2026-11-07)
and [sanitized artifact manifest](../apps/api/evaluation/tree-sitter-0252-postgres-gate-3faa77a8ded7c798.json).

This passes the selected disposable database gate, not the entire backend
suite. The earlier exploratory failures are not individually fully accounted
for, and the native parser-process isolation decision remains open. The
staged runtime is eligible for a separate operational review; normal-service
activation and multilingual indexing remain unauthorized.

## Step 2B.3H.9 — supervised parser prototype

An opt-in [test-only supervisor](supervised-parser-prototype.md) now invokes
the existing analyzer and chunker in a fresh restricted child using synthetic
source. Its final failure-containment and language suite passed **64 tests**;
the existing small parser/indexing selection passed **53 tests** with three
database tests deselected. The supervisor rejects incomplete or mismatched
responses and records fallback separately from successful syntax parsing.
The RSS limit is sampled and the macOS profile is not a complete sandbox for
untrusted repositories. This is not integrated into ingestion and does not
authorize normal-service activation, reindexing or real-source parsing. Full
backend regression, a separate PostgreSQL schema-drift check and a reviewed
production isolation design remain outstanding.

## Step 2B.3H.10 — feature-flagged supervisor

The supervisor is now wired into ingestion behind a separate default-off
setting. Supervised admission is pinned in the existing job mode field; a
subsequently disabled flag fails that queued job closed. The selected macOS
boundary remains experimental and Linux is unsupported. **62** mocked-child
integration tests and **25** sandboxed child/transport checks passed;
**71** existing regressions passed, with **16** skipped and **17** deselected.
The pinned parser environment and verified PostgreSQL test dependencies were
unavailable, so the actual supervised multilingual and PostgreSQL integration
gates did not run. This milestone is **incomplete**, and no normal service,
database, model or real source was touched. See
[verification](verification.md#step-2b3h10--feature-flagged-supervisor-2026-11-08).

## Step 2B.3H.11 — supervised parser verification

The actual application supervisor and collector passed synthetic tests for
all 15 registered extensions in a restored, hash-verified disposable
environment. The native/prototype suite reported **119 passed**, selected
PostgreSQL regressions **322 passed and one deselected**, the native-child
PostgreSQL publication and migration/drift suite **3 passed**, and the
disposable harness safety suite **44 passed**. Two additional targeted
interpreter checks passed. There were no failures or
skips in those suites. Upgrade through 0016 and a separate PostgreSQL schema
drift check both passed. No production database or service was touched.

The PostgreSQL native phase uses a test-only socketpair broker to preserve
the database sandbox while calling the real supervisor and sandboxed child;
the exact unproxied worker-plus-database process arrangement remains untested.
This is selected verification, not a full backend regression or an activation
decision. Linux isolation, production resource limits and the previous 0.26.0
crash remain open. Both multilingual flags remain off by default. Real-source
processing and service activation require separate authorization. See the
[verification record](verification.md#step-2b3h11--supervised-parser-verification-2026-11-08).

## Patch proposals: staged, not production ready

The local implementation now includes an evidence-bound patch proposal and outbox,
strict in-memory diff validation, a disabled-by-default feature flag, a synthetic-only
test provider, review actions and an investigation-page panel. No live patch provider or
reviewed untrusted-test execution adapter is configured; by default, requests for test
execution report `VALIDATION_UNAVAILABLE`. A proposal cannot write to GitHub or modify the canonical checkout.
The isolated PostgreSQL regression and migration/drift check for revision 0017 passed, but
real-source behavior, provider privacy/cost controls, an execution sandbox, retention, and
production activation remain unverified. See [patch generation](patch-generation.md),
[validation](patch-validation.md), and [workflow verification](patch-workflow-verification.md).
Both multilingual feature flags remain disabled by default. The earlier native parser crash
remains unexplained and is not resolved by the patch work.

Step P4 adds a test-only, pinned synthetic execution adapter and result contracts. Its real
sandbox probe failed the network-interface gate on 2026-11-13, so no fixture test ran and
real before/after execution remains unverified. External repository execution remains
disabled; see [patch validation](patch-validation.md).

Step P4.1 identified nine down virtual interfaces in the actual diagnostic network
namespaces, plus a sysfs control file that explained the extra directory entry. It also
found three unapproved read-only runtime `/etc` mounts. The stricter preflight rejects both
conditions, so no trusted fixture test or real execution-result propagation has been
verified. Additional sandbox review and a passing real preflight are required before the two
synthetic fixtures can run; external repository execution requires a separately reviewed
untrusted-code boundary and authorization. No normal service activation is implied.

Step P5 adds a bounded, provider-neutral patch request and offline configuration checks.
The registry still has no live patch provider. A synthetic WebKit workflow passed using
intercepted API responses, and 176 selected offline backend cases passed with six deselected;
the database-backed local cases used in-memory SQLite and do not establish PostgreSQL locking.
Frontend checks passed on Node 26, which is outside the supported range. The supported-Node
production build, current PostgreSQL regressions, real-provider handling, actual patch
execution and real-repository evaluation remain unverified. This is not production ready.

Step P6 supersedes the Node limitation: the production frontend build, 94 frontend tests and
three synthetic browser scenarios passed on verified Node 24.18.0. The verified Python
toolchain and locked test wheels are retained in a private persistent cache; 120 native
synthetic and 176 selected backend tests passed offline. Docker's socket disappeared before
the disposable runner could create a database, so P5 PostgreSQL regression, migration 0017
and schema drift remain unverified for this milestone. The live provider is unconfigured,
patch execution remains blocked by the existing sandbox isolation gate, and normal-service
flags remain disabled. These results do not establish production readiness; see the
[P6 verification record](verification.md#step-p6--verified-toolchains-and-blocked-postgresql-gate-2026-11-13).

Step P7 implements an explicitly disabled-by-default Ollama patch adapter and tests it with
synthetic mocked responses. It checks loopback routing, cloud-disabled and model metadata,
bounded source excerpts, model digest, structured output and existing diff/evidence guards;
it also cancels the HTTP request when the job lease is lost. Those checks do not authenticate
the listening process or independently prevent daemon egress. No Ollama runtime or model was
detected at the checked default locations, and no real inference or PostgreSQL P7 test ran.
Local runtime/model installation, a reviewed daemon isolation boundary and separately
authorized inference remain necessary. Patch execution remains blocked by its existing
sandbox gate; normal application flags and service state were not changed. See
[patch generation](patch-generation.md#opt-in-ollama-adapter).

P7.1 installed the signed and notarized Ollama 0.40.16 app and verified the one approved
`qwen2.5-coder:7b` model against its official registry manifest and blob hashes. A
metadata-only RepoPilot readiness check passed; no model was loaded or invoked. The local
server was stopped after verification, has no identified login item, and normal application
flags were not changed. Further inference needs separate approval, while real-source
handling also requires review of the daemon's identity and egress controls. PostgreSQL and
the patch-execution sandbox remain blocked. See the [P7.1 record](verification.md#step-p71--official-ollama-and-model-artifact-verification-2026-11-14).

Step P7.2 ran two authorized synthetic local-model requests and stopped the isolated daemon.
Both returned structured `insufficient_evidence` responses. The setup intended to send source
snippets, but the exact outgoing request bodies were not retained. The actual RepoPilot provider rejected the second with
`local_model_insufficient_evidence`; no model-generated candidate passed static validation.
The focused offline suite passed 143 tests with one PostgreSQL case deselected. The model's
abstentions are not evidence that the patch generation workflow is ready for real source.
No generated code ran; patch execution, current PostgreSQL coverage and production
activation remain blocked. See the [P7.2 record](verification.md#step-p72--local-synthetic-inference-2026-11-14).

Step P7.3A examined the retained responses and reconstructed the requests offline through
the current provider with a mocked transport. The reconstructed messages include the
synthetic source, but the historical model input cannot be independently verified. The
reason for the abstentions remains unresolved; no production prompt or validation code was
changed. **151** selected offline tests passed, with one PostgreSQL case deselected. Further
inference requires separate approval, and no patch execution or production activation is
authorized. See the [P7.3A record](verification.md#step-p73a--offline-abstention-investigation-2026-11-14).

Step P7.3B captured one actual synthetic provider request and response. The request contained
the complete two-line fixture, but the model again returned `insufficient_evidence` and no
candidate. The response asked for the full implementation; the request's snippet metadata
did not state whether the snippet covered the whole file. That is a plausible contract
ambiguity, not a proven cause. The daemon was stopped, and **124** selected offline tests
passed. No generated code ran, and static candidate validation and patch execution remain
unverified. See the [P7.3B record](verification.md#step-p73b--one-instrumented-synthetic-inference-2026-11-14).

Step P7.4 adds versioned source-coverage metadata and verifies a complete synthetic file
against a separate pinned size and hash. Existing database-backed files remain unknown
because the current indexed-file record lacks an independently persisted byte length. The
one authorized local synthetic retest again returned `insufficient_evidence`; no candidate
was statically validated or executed. **176** selected offline tests passed with one
PostgreSQL case deselected. The original abstention cause remains unknown, patch execution
remains blocked, and production activation and further inference need separate authorization.
See the [P7.4 record](verification.md#step-p74--source-coverage-and-one-synthetic-retest-2026-11-15).

Step P7.5 compared the existing patch contract with a test-only alternative, entirely
offline. The production structured parser now rejects an empty candidate earlier, without
changing the on-wire schema or downstream patch validators. The alternative's abbreviated
abstention format is not compatible with the current parser and remains test-only. The
selected suite passed **192 tests** with one PostgreSQL case deselected. No inference ran,
and the cause of the four model abstentions remains unresolved. Real-source use, execution
and production activation remain blocked. See the [P7.5 record](verification.md#step-p75--offline-patch-contract-comparison-2026-11-15).

### P8 — synthetic local patch candidate

The Ollama provider now supports a structured source-edit strategy, deterministic diff
construction, and the existing static validator. One actual local Qwen2.5-Coder 7B request
on an original complete synthetic file produced a candidate edit accepted by static
validation. This is a successful synthetic generation demonstration, not evidence of a
verified bug fix: generated code was not run. Offline focused coverage passed 284 tests,
with 3 PostgreSQL-specific tests deselected; Ruff and diff checks passed. Patch provider and
proposal flags remain disabled by default, and the frontend was preserved. PostgreSQL
verification, migration 0017 verification, execution isolation, real-source provenance,
production security review, and explicit activation approval remain outstanding. See the
[P8 verification record](verification.md#p8--local-structured-edit-generation-2026-11-15).

### P9 — trusted synthetic execution isolation

The macOS native isolation investigation confirmed that simple sandbox profiles can deny
network, child creation, and canonical unauthorized file reads in inert canaries. A path
alias initially bypassed a literal file denial, so an effective policy must be evaluated
using resolved paths. The canaries alone do not establish a trusted execution adapter or
production security boundary. The Docker isolation gate remains blocked. See the
[P9 verification record](verification.md#p9--trusted-synthetic-execution).

The restrictive filesystem policy stopped Python startup and the working broader policy
does not demonstrate complete secret isolation. Actual synthetic execution is blocked.
The new fixed-fixture registry and report validator have offline tests but no worker
integration. The selected suite passed 123 tests with 5 deselections; PostgreSQL,
before/after execution, and production readiness remain unverified.

### P9.1 — VM-backed execution

No verified Linux guest artifact or dedicated VM launcher was found. The non-executing VM
contract fails closed; no VM configuration, baseline, patched test or guest isolation was
verified. No production flag was enabled. A reviewed launcher and hash-verified ARM64 guest
must be provisioned and assessed before trusted synthetic VM tests can run. PostgreSQL,
real-repository execution, and production activation remain separate outstanding gates.

### P9 final — trusted host demonstration

The exact retained P8 synthetic patch was tested on the host under a narrow explicit
authorization. Baseline failed, patched passed, and the existing comparison returned
`BASELINE_FAILED_PATCH_PASSED`; an unchanged-good control returned `BOTH_PASSED`.
Four real child processes ran, with private workspaces cleaned up. This was not sandboxed
execution and does not authorize real repositories. The application service and frontend
require a sandboxed completed report and do not accept the honest host result, so the
full application contract milestone remains incomplete. PostgreSQL persistence and
production execution remain unverified. See [verification](verification.md#p9-final--trusted-host-arithmetic-demonstration).

## P10 — application integration status (2026-11-15)

P10 added forward-only source provenance at ingestion and persistence. New complete-file
records carry exact raw byte length, UTF-8/identity metadata and SHA-256; publication
reconstructs chunks and rejects an inconsistent hash or length before publication.
Historical rows remain `UNKNOWN_COVERAGE`. Alembic source head is `0018`. A synthetic
collector-to-persistence path and patch proposal/API/worker contracts passed the selected
offline regression, but the PostgreSQL runtime was unavailable. PostgreSQL migration
application, schema drift, locking and transactional integration are still blocked. The
Alembic chain reached `0018` only on the legacy temporary SQLite migration test.

The backend contract is connected through deterministic provider tests and the existing
proposal lifecycle; no new model call occurred. On supported Node 24.18.0, the modern
frontend passed its production build, typecheck, ESLint and 94 tests. Browser rendering
against a running application was not repeated. The frontend source was not changed in P10.

| Release area | P10 status |
|---|---|
| GitHub issue ingestion and investigations | IMPLEMENTED BUT NOT VERIFIED end to end against live GitHub |
| Multilingual code indexing | VERIFIED ON SYNTHETIC DATA ONLY; defaults remain off |
| Evidence-backed retrieval and source provenance | VERIFIED ON SYNTHETIC DATA ONLY; migration 0018 awaits PostgreSQL |
| Local AI patch generation | VERIFIED ON SYNTHETIC DATA ONLY; prior synthetic inference, no P10 inference |
| Static patch validation | VERIFIED ON SYNTHETIC DATA ONLY |
| Proposal persistence and outbox | IMPLEMENTED BUT NOT VERIFIED on PostgreSQL in P10 |
| Worker lifecycle and API authorization | VERIFIED ON SYNTHETIC DATA ONLY; selected offline contract tests |
| Issue-to-review end-to-end workflow | IMPLEMENTED BUT NOT VERIFIED as one PostgreSQL-backed application run |
| Frontend review workflow | VERIFIED ON SYNTHETIC DATA ONLY; Node 24 build/tests, no live browser workflow |
| Actual patch execution | BLOCKED pending reviewed Linux microVM runtime; P9 host demonstration is not a sandbox |
| PostgreSQL migrations and schema drift | BLOCKED; disposable PostgreSQL unavailable |
| Tenant security | VERIFIED ON SYNTHETIC DATA ONLY; not a production security certification |
| Monitoring, retention and deployment rollback | IMPLEMENTED BUT NOT VERIFIED for production operations |
| Production deployment | BLOCKED; feature flags remain disabled |

The preferred future execution design is a dedicated Linux KVM worker pool with a Firecracker
microVM per job, subject to provisioning and security review. No experimental execution
adapter was added in P10. Next action: restore an already approved disposable PostgreSQL
runtime and run migration 0018, schema-drift and focused transaction tests; keep production
patch execution disabled until the separately reviewed microVM service exists.

## P11 — PostgreSQL-backed integration status (2026-11-15)

P11 closes the disposable PostgreSQL verification gate for the current synthetic patch
workflow. PostgreSQL 16.16 with pgvector 0.8.7 was privately provisioned; the empty-database
chain reached `0018`, fresh schema drift was clean, and the historical upgrade test passed.
Patch/source persistence and worker/outbox PostgreSQL selections passed. The broad selection
is not fully green because one vector test requires optional NumPy (`1,200 passed, 1 failed,
6 skipped, 2 deselected`). Do not confuse that optional dependency gap with PostgreSQL
availability or hide it by skipping the test.

| Release area | P11 status |
| --- | --- |
| PostgreSQL migrations through 0018 | VERIFIED on disposable PostgreSQL |
| Source provenance persistence | VERIFIED ON SYNTHETIC DATA ONLY |
| Patch proposal persistence and outbox | VERIFIED ON SYNTHETIC DATA ONLY |
| Worker claims, fencing and cancellation | VERIFIED ON SYNTHETIC DATA ONLY; broad suite retains optional NumPy failure |
| Broad backend regression | IMPLEMENTED BUT NOT FULLY VERIFIED (one optional NumPy failure) |
| Real-repository patch execution | BLOCKED pending reviewed Firecracker/KVM worker and security acceptance |
| Live provider in normal services | BLOCKED; remains disabled by default |
| Frontend | Existing modern frontend preserved; no P11 frontend changes |
| Production readiness | BLOCKED |

P11 fixed UTC normalization of aware datetimes used in PostgreSQL-backed token-count
identity, and isolated Alembic version bookkeeping in migration/drift tests. See the
[P11 verification record](p11-postgresql-verification.md) for exact tests, artifact
identities, cleanup and limitations. The private disposable database was shut down and
removed; no normal database or service was accessed or restarted.

## P12 — backend regressions and execution readiness (2026-11-16)

The NumPy test failure was caused by running a base/dev environment without the project's
already-declared optional `local-embeddings` dependency. The locked NumPy 2.5.4 ARM64 wheel
was SHA-256 verified and installed only in a disposable P12 venv; no package pin changed.
PostgreSQL 16.16/pgvector 0.8.7 migrated from empty to `0018`, fresh drift was clean, the
legacy upgrade/drift tests passed **3**, and synthetic capture passed **50**. Broad PostgreSQL
selection: **1,201 passed, 0 failed, 0 errors, 5 skipped, 3 deselected**. The suite is green
for selected cases, with optional ONNX/tokenizers and parser-broker coverage still skipped;
the trusted host report case was not loaded, and fixture execution/sandbox preflight were
deselected by design. The private database was stopped and removed.

| Release area | P12 status |
| --- | --- |
| PostgreSQL migrations through 0018 and schema drift | VERIFIED on disposable PostgreSQL |
| Source provenance | VERIFIED ON SYNTHETIC DATA ONLY; persistence tested on PostgreSQL |
| Local AI patch generation | VERIFIED ON SYNTHETIC DATA ONLY (prior P8); no P12 inference |
| Static patch validation | VERIFIED ON SYNTHETIC DATA ONLY |
| Proposal persistence, outbox and worker regressions | VERIFIED ON SYNTHETIC DATA ONLY; PostgreSQL suite passed |
| Authenticated API/tenant contracts | VERIFIED ON SYNTHETIC DATA ONLY |
| Frontend compatibility | IMPLEMENTED BUT NOT RE-TESTED in P12; frontend unchanged |
| Firecracker request contract | IMPLEMENTED BUT NOT TESTED against a real runner |
| Dedicated Linux KVM/Firecracker host | BLOCKED; not provisioned |
| Effective untrusted-code isolation review | BLOCKED; not performed |
| Production patch execution | BLOCKED; disabled by default |
| Production readiness | BLOCKED |

The next required external decision is to authorize/provide a dedicated Linux host with
working KVM (`/dev/kvm`) and reviewed guest-artifact provisioning. The bounded host and
acceptance requirements are in [P12 execution-host specification](p12-execution-host-prerequisite.md).
P12 did not choose or purchase cloud infrastructure. Feature flags, frontend, normal
services and normal database were untouched. P8/P9/P11 remain completed; production
execution remains a separate gate.


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

## P19.1 — upstream issue and partial snapshot

The application now has direct-parent issue identity and job-scoped pinned partial
inventory contracts. A disposable Daytona investigation persisted real-source
evidence with synthetic application authentication. Local inference remains blocked
until exact-request one-shot approval and durable identity restoration are verified.
No production execution, real-source inference or verified fix is claimed. See
[P19.1 verification](p19-1-upstream-issue-and-partial-snapshot.md).

## P19.2 — durable approval work

The P19.2 internal ledger, guarded transport and checkpoint validation/restoration helper
were added without enabling scoped model calls. They are not an approval-ready invocation
path: shared authority binding, authenticated human approval, real worker integration,
independent daemon/egress checks and end-to-end restoration/replay verification remain
open. The prior request is unapproved; no inference or source execution occurred. See
[P19.2 durable inference approval](p19-2-durable-inference-approval.md).


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


## Commercial beta foundation follow-up

GitHub App token issuance is opt-in and mock-verified, and pinned reviews persist
bounded rate-limit scheduling. Live installation access, organization/private
onboarding, fork-head provenance, safely contained TypeScript analysis and independent
quality evaluation remain release gates. The real-source inference guard remains
closed. See [commercial-beta-foundation.md](commercial-beta-foundation.md).


## Commercial beta gate-closure follow-up

PR worker source-read authorization was strengthened and a stale synthetic
evaluation test corrected. Live installation-backed access, organization/private
onboarding, fork-head provenance, TypeScript containment and independent labels
are not verified. See [commercial-beta-gate-closure.md](commercial-beta-gate-closure.md).


## Commercial alpha follow-up

Synthetic public-fork identity, source verification, review and feedback were
tested. Live GitHub, TypeScript parser safety, organization/private access,
independent labels and production security remain open. See
[commercial-alpha-product-milestone.md](commercial-alpha-product-milestone.md).


## TypeScript and real-fork follow-up

A narrow local-only TypeScript rule is verified on synthetic fixtures; live GitHub
App access, independent review labels, production parser isolation and private
repository readiness remain open. See
[commercial-alpha-typescript-and-live-fork.md](commercial-alpha-typescript-and-live-fork.md).
