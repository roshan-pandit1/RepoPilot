# RepoPilot 2.0 — local vector-search foundation

## Status and model review

Controlled synthetic vectors and a tiny synthetic ONNX graph have been used in
tests. A separately approved CPU-only smoke test also loaded the pinned real
CodeRankEmbed export for two fixed synthetic inputs and one repeat. Lexical
search remains the default; investigation `terms-v2` ranking has not changed.
Semantic retrieval quality and production performance remain unevaluated.

| Candidate | Verified properties | Decision and limitations |
| --- | --- | --- |
| [CodeRankEmbed](https://huggingface.co/nomic-ai/CodeRankEmbed) | MIT; 137M-parameter code-retrieval bi-encoder; 768 dimensions; 8192-token model context; query instruction prefix; CLS pooling | Primary candidate for future evaluation. The upstream Python example requires custom model code; this implementation never enables it. A third-party ONNX export passed a limited CPU smoke test; its exact upstream revision and numerical parity remain unverified. The adapter caps inputs at 512 tokens. |
| [Jina embeddings v2 base code](https://huggingface.co/jinaai/jina-embeddings-v2-base-code) | Apache-2.0; 768 dimensions; 8192-token model context; code-focused; mean pooling | Alternative for research, not implemented by the adapter. Its documented Python loading uses custom code; license and data terms still need deployment review. |
| [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) | Apache-2.0; general-purpose 384-dimensional embeddings; default 256-token truncation; mean pooling; [official ONNX artifact](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/tree/main/onnx) | Fallback and general-language baseline. Not trained specifically for code. It has no task-specific query prefix. |

As rough arithmetic only, 137M FP32 parameters require about 548 MB for weights
before runtime, tokenizer, inputs and intermediate tensors. MiniLM's published
FP32 ONNX artifact is about 90 MB. These sizes are not performance results. The
current adapter uses CPU; [PyTorch MPS](https://docs.pytorch.org/docs/main/notes/mps.html)
is an alternative Apple Silicon backend, but this implementation does not use or
verify MPS. The later CodeRank smoke test recorded one Apple Silicon session's
memory and timing; broader compatibility and performance remain unmeasured.

## Provider and identity

`EMBEDDING_PROVIDER` defaults to `disabled`. A local operator must explicitly
set it to `local`, enable `EMBEDDING_LOCAL_ENABLED`, configure an allowlisted
model and dimensions, a full 40-character export revision, absolute local artifact
directory and SHA-256 hashes for `model.onnx` and `tokenizer.json`. No application
job is scheduled by configuration. The optional `local-embeddings` dependency
extra contains ONNX Runtime, tokenizers and NumPy; it is not imported at API
startup. Artifacts are read locally and hashed before use. The operator must
independently verify that the artifact hashes really correspond to the claimed
model revision; a supplied revision string alone does not prove provenance.

The specific settings are `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`,
`EMBEDDING_LOCAL_PATH`, `EMBEDDING_LOCAL_REVISION`,
`EMBEDDING_LOCAL_TOKENIZER_REVISION`, `EMBEDDING_LOCAL_MODEL_SHA256`, and
`EMBEDDING_LOCAL_TOKENIZER_SHA256`. An omitted tokenizer revision defaults to
the export revision. These commit IDs identify the artifact sources claimed by
the operator; they do not establish the upstream revision used for the export.
CodeRank requires 768 dimensions; MiniLM requires 384. Passing settings into a
Compose service requires a separately reviewed service configuration. Do not
start these updated services against the existing database before an approved
backup and migration to 0016.

The adapter loads model bytes into ONNX Runtime with the CPU provider, accepts
no model-provided Python or custom-op library, and does not invoke a network
client or download weights. `ORT_DISABLE_TELEMETRY=1` is set before importing
ONNX Runtime; an already initialized runtime without that setting is refused.
The adapter limits artifact size, input characters, batch size (8), tokens,
runtime threads (2), concurrent inference per process (1), and ONNX execution
time (10-second termination request). Artifact hashing and session creation do
not have a hard wall-clock or OS memory limit; process-level concurrency scales
with the number of API and worker processes. Production deployment needs an
independent egress policy and resource limits. The separately approved smoke
test exercised the selected CodeRank export through ONNX Runtime directly; it
did not exercise the application adapter end to end or validate other exports.

Local query and document prefixes, maximum tokens, right-truncation, pooling,
padding, pinned ONNX Runtime/tokenizer versions, L2 normalization and both
artifact hashes and tokenizer revision form a canonical contract digest. An
already prefixed query is normalized to exactly one instruction prefix. CodeRank
also checks the documented graph signature and the placement of `[CLS]` and
`[SEP]` tokens before inference. Runtime versions are checked
before use; incompatible installations fail closed.
The exact revision and full digest are stored on each job and cache record;
the existing version field binds the revision to a digest prefix. A vector link
stores the existing source chunk fingerprint, which includes snapshot, file,
path, source hash, symbol, range and text. Tenant and repository composite
foreign keys remain in force. Content-addressed cache reuse is restricted to
the same tenant, repository, model and contract. Migration 0016 adds nullable
metadata and does not backfill old records. Existing legacy fake links lack a
trustworthy fingerprint and are not eligible for the new search; fake provider
version 2 creates new links when explicitly run in a test/development context.

## Exact and hybrid search

The user must pass the existing current session, tenant, repository and active
installation checks. The endpoint requires a current published, non-revoked
snapshot and a completed embedding job with matching provider, revision,
dimensions, contract, normalization and completed count. The exact pgvector
cosine query uses `<=>`, caps its returned candidate set, disables index scans
locally so a future ANN index cannot silently change the exact baseline, and
orders ties by path, start line and chunk ID. All matching links are checked
against their original fingerprint, content hash and commit-pinned citation;
incomplete or changed evidence causes an explicit lexical fallback. A missing
local model is reported as `MODEL_NOT_AVAILABLE`; it never switches to fake
embeddings. Existing fake vectors remain explicitly mechanical tests.

Hybrid search reuses reciprocal-rank fusion with bounded candidate windows and
stable chunk IDs. The standalone code-search endpoint uses the existing shared
keyword SQL; issue investigations apply their additional `terms-v2` query and
reranking logic and are unchanged. Do not label the standalone hybrid endpoint
as a measured `terms-v2` hybrid benchmark.

No ANN index is created or enabled. [pgvector documentation](https://github.com/pgvector/pgvector)
notes that HNSW trades recall for speed, and filtering can reduce the number of
matches; multi-tenant indexes may also influence recall between tenants. Future
experiments must use dimension/model-specific index design, filtered ANN tests,
planner inspection, resource measurements and recall against exact neighbors.

## Held-out evaluation

`app.evaluation.retrieval_heldout` scores supplied paired captures only after
validating explicit repository roots, full pinned Git commits, source files,
line ranges, label provenance fields and a held-out split. It supports graded
judgments, missing-evidence queries, keyword/semantic/hybrid captures, snapshot
matching, citations, per-language/repository recall, latency, fallback and
missing-embedding counts, ANN-versus-exact overlap, and seeded paired bootstrap
intervals when at least five paired queries are available. Precision is
reported over judged results plus lower/upper precision-at-k bounds; unjudged
results are unknown, not asserted irrelevant. nDCG uses available labels and
must be interpreted as incomplete when judgments are incomplete. Captures must
declare `terms-v2` for the lexical/hybrid comparison. The scorer does not
generate captures or establish their provenance. `heldout-v2` also validates a
complete versioned issue context, predeclared retrieval configuration, query
hashes, and a shared candidate-universe identity across the paired captures.
The older `heldout-v1` format is retained but labeled
`legacy-query-only-unverified`.
All non-fallback semantic captures must share an explicit provider/model/revision/
dimension/contract/normalization identity; fake-provider results are marked mechanical only.
Every returned citation is checked against the pinned local Git tree and blob,
including its line range and, when supplied, its exact source snippet. Missing,
invalid, or oversized source blobs are counted as invalid or unverifiable.
Label provenance is supplied metadata; the evaluator cannot independently prove
that judgments were made independently or kept out of the tuning set.

To score previously captured, independently labeled data without network access,
run the following from `apps/api` after replacing the example paths:

```sh
python -m app.evaluation.retrieval_heldout \
  --dataset /path/to/heldout.json \
  --captures /path/to/captures.json \
  --repository owner/repository=/path/to/local/git/repository \
  --output /path/to/new-report.json
```

Repeat `--repository` for each repository. The capture file is a JSON array of
objects with `mode`, `query_id`, `latency_ms`, and `response` fields; every
query needs one record for each mode. Responses must include the pinned commit,
snapshot, results, and the applicable lexical and semantic identities. Inputs
are limited to 8 MB each. The report is created with owner-only permissions and
an existing file is never overwritten. Capturing queries from a running system
and validating their provenance remain separate steps.

The registered [synthetic capture runner](retrieval-capture-dataset-v1.md)
now produces controlled-vector development captures using the actual
investigation retriever and exact pgvector search. Its synthetic fixture and
GitHub-shaped citations are not real source provenance, and the runner cannot
capture a real repository. Controlled vectors test mechanics, not semantic
relevance. A real-data capture workflow remains to be prepared and reviewed.

Before real-model retrieval evaluation, obtain separate approval for the source
dataset, capture procedure and resources. Reverify the pinned artifacts and
maintain an offline runtime boundary. Collect independently judged held-out data
across repositories and languages, and report actual coverage, failures, latency,
memory and paired uncertainty.
No training-set or synthetic metric is evidence of real semantic quality.

## Step 2B — CodeRankEmbed artifact review

The selected candidate is the third-party
[zuliaio/coderankembed-onnx export](https://huggingface.co/zuliaio/coderankembed-onnx/tree/72d8b338380c0b83d02b1e38b40b7b778c1c8703),
not a Nomic-published ONNX artifact. Public model metadata and the
[export commit](https://huggingface.co/zuliaio/coderankembed-onnx/commit/72d8b338380c0b83d02b1e38b40b7b778c1c8703)
were initially inspected without downloading model or tokenizer files. After
separate approvals, both files were downloaded and verified as recorded below.
The full manifest remains **incomplete** because the upstream model revision
used for the export is unverified. The later static inspection and separately
approved real-model smoke test are described below:

| Item | Metadata observed |
| --- | --- |
| Model and license | `nomic-ai/CodeRankEmbed`, MIT; export card also declares MIT |
| Observed upstream HEAD | `3c4b60807d71f79b43f3c4363786d9493691f8b1`; its use as the export's input is **not established** |
| Export repository revision | `72d8b338380c0b83d02b1e38b40b7b778c1c8703` |
| `model.onnx` | 547,637,263 bytes; locally verified SHA-256 matches publisher Git LFS SHA-256 `12ba359756210927940f8a9ec569cc7d6d6f091e7fcfae6cbe09bba6aab8830d` |
| `tokenizer.json` | 711,650 bytes; verified Git blob ID `a8472b8cccbf1668d306ec32780fd096b4a00bfb`; locally calculated SHA-256 `ea725c60b9022a7a491ffc348b5622a199853c806d625f673d0e2ebf1c3b5312` |
| Artifact directory | `/Users/roshan/Library/Application Support/RepoPilot/models/coderankembed/72d8b338380c0b83d02b1e38b40b7b778c1c8703/` |

The tokenizer was obtained from the exact approved URL:
`https://huggingface.co/zuliaio/coderankembed-onnx/resolve/72d8b338380c0b83d02b1e38b40b7b778c1c8703/tokenizer.json`.
Its exact size, Git blob identity and SHA-256 were checked at the final path;
the file is owned by the current user and has mode `0600`. JSON parsing succeeded,
including structural checks for a WordPiece vocabulary and the expected PAD,
UNK, CLS and SEP token IDs. No tokenizer code was executed. The SHA-256 is a
locally calculated fingerprint after checking the publisher's Git blob ID, not
an independently published SHA-256 from the exporter.

The model was obtained from the exact approved URL:
`https://huggingface.co/zuliaio/coderankembed-onnx/resolve/72d8b338380c0b83d02b1e38b40b7b778c1c8703/model.onnx`.
Its verified storage path is
`/Users/roshan/Library/Application Support/RepoPilot/models/coderankembed/72d8b338380c0b83d02b1e38b40b7b778c1c8703/model.onnx`.
The exact size and SHA-256 matched before an exclusive atomic rename and were
rechecked at the final path; the file has mode `0600`. The tokenizer SHA-256 was
rechecked without modifying it. At the download checkpoint, no model graph
inspection, loading or inference had been performed. The two files total
548,348,913 bytes (about 548.35 MB decimal).

A Git blob ID is not a SHA-256 content digest. The tokenizer at the observed upstream HEAD has a
different Git blob ID (`3c0e6344ec45a9a6e5a621d6711baf109c2d9f87`) and is
711,649 bytes; this establishes different bytes, not whether the tokenizers
behave differently. The export script accepts an upstream revision but defaults
to the latest and does not establish which revision produced this artifact.
Do not label the observed upstream HEAD as the export's verified input.

The [export author](https://huggingface.co/zuliaio/coderankembed-onnx) reports
FP32/opset 17 parity with upstream for several input lengths. This is a publisher
claim, not an independent reproduction. The card declares `input_ids`,
`attention_mask`, and `token_type_ids` as graph inputs and `last_hidden_state`
as the output; the subsequent bounded wire scan found the same signature. The intended
contract is the exact query instruction prefix, no document prefix, a 768-value
CLS vector, L2 normalization and cosine distance. RepoPilot deliberately caps
tokenization at 512 tokens, below the model card's 8192-token limit. Runtime
checks cover the expected graph signature and special-token placement, but do
not prove equivalence to the upstream tokenizer or model.

The adapter is CPU-only. A synthetic graph and a later, separately approved
two-input test of the selected graph ran on this Apple Silicon host. Those
limited observations do not establish general runtime compatibility or
production memory and latency.
ONNX files are untrusted native-runtime input: structural checking does not prove
execution safety. Run real inference only within an approved offline and
resource-limited boundary.
No exporter or remote model code was executed, and `trust_remote_code` is not
enabled.

### Offline static graph inspection — incomplete

After separate approval, both artifact SHA-256 values and the model's exact size
were checked again. A bounded, custom protobuf-wire metadata scanner inspected
the model in a macOS sandbox denying network access and file writes. It skipped
raw tensor contents and did not create a full graph dump. The scan observed:

| Property | Observed metadata |
| --- | --- |
| IR and opset | ONNX IR 8; default `ai.onnx` opset 17 |
| Producer | `pytorch`, version `2.6.0`; no model metadata properties found |
| Inputs | `input_ids`, `attention_mask`, `token_type_ids`: each `int64[batch, sequence]` |
| Output | `last_hidden_state`: `float32[batch, sequence, 768]` |
| Graph | 3,593 nodes; 112 initializers; no nested graphs or model-local functions found |
| Operators | 26 distinct operator types, all in the default `ai.onnx` domain |
| External data | No external-data references found in the initializer or node-attribute tensor fields examined |

The 26 observed operator types were recognized at the declared opset in the
installed ONNX Runtime's static schema registry, with no arity or attribute-name
mismatches found by the scanner. The scanner also found no unresolved main-graph
inputs or outputs, duplicate main-graph output names, or byte-length mismatches
among the 1,560 raw tensor fields it checked. It did not inspect tensor values.
The runtime was imported **only** to enumerate static schemas: no graph was passed
to it and no `InferenceSession` was created. A separate graph-independent probe
of the runtime kernel registry exited with status 139; kernel availability is
therefore unverified.

The names, element types and ranks match the adapter's declared signature;
the output's last dimension is 768, which is compatible with extracting the
first token before L2 normalization. Batch and sequence axes are symbolic,
and the scan did not establish a maximum sequence length or prove that 512-token
inputs execute correctly. It does not establish tokenizer compatibility,
numerical correctness, upstream parity or semantic relevance.

The scan imposed a 60-second CPU limit, bounded metadata reads and a sampled
384 MiB RSS guard; observed peak RSS was 59,195,392 bytes. The operating system
did not permit a hard address-space limit, so the RSS guard was not a hard
kernel memory limit. The installed environments did not contain the `onnx`
parser/checker package, and no package was installed or downloaded at that
checkpoint. That scan was **not** a complete ONNX protobuf parse or
`onnx.checker` structural validation. The later official checker result is
recorded below; runtime kernel support and safe execution remain unverified.

### Official checker attempt — blocked before installation

The later approved checker procedure requires an existing macOS ARM64 CPython
3.12 interpreter. `uv python find --offline 3.12`, interpreter discovery and a
search of common local locations found no such interpreter; the available
interpreters were CPython 3.14.10 and 3.9.6. In accordance with that procedure's
stop condition, no temporary environment was created and no package was
installed. [PyPI metadata](https://pypi.org/project/onnx/1.23.0/) lists the
specified `onnx-1.23.0-cp312-abi3-macosx_13_0_universal2.whl` with the supplied
SHA-256 `6cc93aa89502acbf453a16d79b465d47d9c454f3a3cb3fc5507a8cb59ab53208`;
the wheel itself was not downloaded or verified locally at that checkpoint.
Both model and tokenizer hashes were rechecked and matched. A subsequent approval
permitted the Python 3.14 procedure recorded below.

### Official ONNX 1.23.0 static validation

The user separately approved CPython 3.14.10 ARM64 in place of 3.12. The
GIL-enabled interpreter (`cpython-314-darwin`) ran on macOS 27.2. The approved
CPython 3.12 `abi3` universal2 wheel was compatible; the free-threaded wheel
was not used. A new environment was created at
`/private/tmp/repopilot-onnx-check.EAOtHoEC/venv`, outside the repository.
Official PyPI metadata was used to review and pin all dependencies before
installation. Each downloaded binary wheel was SHA-256 checked against that
metadata, including the independently specified ONNX wheel hash. The wheels were
installed offline with no dependency resolution or source builds; `uv pip check`
found the five installed packages compatible.

| Installed wheel | Verified SHA-256 |
| --- | --- |
| `onnx-1.23.0-cp312-abi3-macosx_13_0_universal2.whl` | `6cc93aa89502acbf453a16d79b465d47d9c454f3a3cb3fc5507a8cb59ab53208` |
| `numpy-2.5.4-cp314-cp314-macosx_14_0_arm64.whl` | `956555e0603a4d38019ae6925711cb9dc43195c076a928accf7ea5d50bddfe53` |
| `protobuf-7.36.2-cp310-abi3-macosx_10_9_universal2.whl` | `cbc70b17ee27e28894c7fee8bb04be1abead49e936bc70eb60052531eee2079e` |
| `typing_extensions-4.16.0-py3-none-any.whl` | `481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8` |
| `ml_dtypes-0.5.4-cp314-cp314-macosx_10_13_universal2.whl` | `2b857d3af6ac0d39db1de7c706e69c7f9791627209c3d6dedbfca8c7e5faec22` |

Model and tokenizer hashes matched before and after inspection. Official ONNX
1.23.0 fully parsed the model protobuf with external-data loading disabled.
In a second process, `onnx.checker.check_model` passed using the model path,
`full_check=False`, opset compatibility checking enabled and custom-domain
checking enabled. Optional shape inference was not run. The official parser
confirmed the IR, opset, I/O signatures, 3,593 nodes and 112 initializers shown
above. It found no external tensor-data references, custom operator domains,
unknown operator schemas, nested graphs or model-local functions. The actual
signature structurally matches the CodeRank adapter's three inputs and
`float32[batch, sequence, 768]` output for CLS pooling; it does not prove that
512-token inference, tokenizer behavior, normalization or cosine search work.

Both phases ran separately under a macOS sandbox denying network access,
filesystem writes and unrelated home/repository reads. Each had a 90-second
CPU limit, a 120-second wall timeout and a sampled 2 GiB RSS watchdog. Peak
RSS reported by the processes was 1,155,350,528 bytes for parsing and
1,157,316,608 bytes for checking. The watchdog is sampled rather than a hard
kernel memory limit. An initial sandbox configuration aborted Python startup
with status 134 even without importing ONNX or opening the model; the adjusted
profile retained and successfully tested the required network, write and secret
read denials before either model phase ran.

Neither phase imported ONNX Runtime, initialized an inference session, executed
graph operators or generated embeddings. The earlier separate
`onnxruntime.capi._pybind_state.get_all_opkernel_def()` probe exited with
status 139 without loading the model; it was not repeated. Its cause and runtime
kernel support remain unverified. Upstream export revision, numerical parity,
real-model inference, and semantic retrieval quality also remain unverified.

### Runtime diagnostic checkpoint — 2026-11-06

The host reports macOS 27.2 (build 26B123), ARM64 and approximately 16 GiB of
physical memory. The selected GIL-enabled CPython is 3.14.10 on ARM64 with
`cpython-314-darwin` ABI. RepoPilot pins `onnxruntime==1.31.1` for its optional
local adapter, but that pin is not evidence of a current installation. The
previous `/private/tmp/repopilot-step2a-venv` runtime and the separate
`/private/tmp/repopilot-onnx-check.EAOtHoEC/venv` static-checker environment
are no longer present. ONNX Runtime was not importable in the project root or
API virtual environments, Homebrew Python 3.14.10 or Apple Command Line Tools
Python 3.9.6. A search of the checked Homebrew and common cache locations found
no installed runtime binary; this is not a claim about every possible Python
environment on the machine. A later filename and Spotlight search covering
accessible home, project, temporary, Homebrew and `/usr/local` locations also
found no runtime binary; the model directory was excluded and some filesystem
paths could not be searched. The earlier runtime wheel's exact installed
version and dynamic dependencies cannot be rechecked from the missing binary.
No package was downloaded or installed.

Two existing, separate macOS crash reports from 2026-11-05 at 22:27:12 and
22:27:26 show `SIGSEGV` / `EXC_BAD_ACCESS`, a null-address fault, and frames in
`onnxruntime_pybind11_state.so` while returning a vector of `KernelDef` objects
through the Python binding. They identify both Python 3.14.10 and the runtime
binding as ARM64; an architecture mismatch is not apparent from those frames.
The reports are `Python-2026-11-05-222713.ips` and
`Python-2026-11-05-222726.ips` in `~/Library/Logs/DiagnosticReports`; the
binding's Mach-O UUID is `c230574f-20c3-3c2c-a746-acfbd3af12ef` in both.
The earlier recorded call was `get_all_opkernel_def()` and did not load the
CodeRankEmbed model. These reports localize the native failure but do not prove
its underlying cause, general session behavior or whether sandboxing contributed.
No runtime or kernel-registry probe was repeated at this checkpoint.

A fresh standalone Python startup passed in a macOS sandbox with a scrubbed,
minimal environment, network and file writes denied, and home, repository
and unrelated temporary-directory reads denied. Its home and repository
canary reads, scratch-file write and loopback connection were each denied.
The process had a 20-second CPU limit, 64-file descriptor limit, 25-second
wall timeout and sampled 512 MiB RSS watchdog; it reported a 16,269,312-byte
peak RSS. The watchdog is sampled, not a kernel-enforced memory limit. The
runtime's provider discovery, dynamic-library inspection, current crash
reproduction and synthetic inference could not run without an installed
runtime. The prior synthetic tests remain historical engineering evidence, not
a current runtime-readiness result.

Before a separately approved real-model test, first resolve the runtime
availability and native crash using isolated, bounded import, CPU provider and
synthetic-only checks. Any later model process must deny network and database
access, receive no credentials, allow read-only access to the verified model,
tokenizer and required interpreter/runtime libraries while blocking other
application files, use CPU with bounded threads, have a private
temporary output directory, and enforce a finite timeout and a monitored memory
budget chosen against available RAM. The static checker previously peaked near
1.16 GiB; real inference requirements are unknown. This requires a narrower
read exception for the artifacts than the diagnostic sandbox, which denied
the entire home directory, and must not execute external model code. Static
validation, these startup checks and prior synthetic tests do not establish
runtime safety, numerical parity, upstream provenance or retrieval quality.

### Disposable ONNX Runtime diagnostics — 2026-11-06

With separate approval, a new environment was created at
`/private/tmp/repopilot-ort-runtime-fjkjao5k/venv` using the existing `uv 0.9.5`
binary with `--no-project`, offline and without Python downloads. This was an
isolated environment operation, not a project lock or dependency update. The
host was macOS 27.2 ARM64; the selected GIL-enabled CPython was 3.14.10 with
ABI `cpython-314-darwin`. The runtime and its four required dependencies were
downloaded from official PyPI storage after reviewing
[ONNX Runtime 1.31.1 metadata](https://pypi.org/pypi/onnxruntime/1.31.1/json)
and the dependencies' corresponding release metadata. The exact wheels and
their published SHA-256 hashes matched the downloads and the project lock:

| Installed wheel | Verified SHA-256 |
| --- | --- |
| `onnxruntime-1.31.1-cp314-cp314-macosx_14_0_arm64.whl` | `8536ac43682caa7492c46d6cfd4c3c8db288dcf0619508431a22170b670ee1d0` |
| `flatbuffers-25.12.19-py2.py3-none-any.whl` | `7634f50c427838bb021c2d66a3d1168e9d199b0607e6329399f04846d42e20b4` |
| `numpy-2.5.4-cp314-cp314-macosx_14_0_arm64.whl` | `956555e0603a4d38019ae6925711cb9dc43195c076a928accf7ea5d50bddfe53` |
| `packaging-26.3-py3-none-any.whl` | `d7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c` |
| `protobuf-7.36.2-cp310-abi3-macosx_10_9_universal2.whl` | `cbc70b17ee27e28894c7fee8bb04be1abead49e936bc70eb60052531eee2079e` |

The runtime wheel was 20,883,427 bytes. Installation used those files only,
offline, with `--require-hashes`, `--no-index`, `--no-deps` and `--no-build`.
The disposable environment contained exactly the five packages above. The
initial `uv` install attempt inside the outer sandbox panicked in macOS system
configuration with exit 101; the offline install then succeeded outside that
outer sandbox, with a scrubbed environment. The execution probes below used a
separate, more restrictive macOS sandbox.

Static binary inspection found the installed binding to be ARM64 with Mach-O
UUID `c230574f-20c3-3c2c-a746-acfbd3af12ef`, matching both earlier crash
reports. Its direct dependencies include CoreML, CFNetwork, Network,
SystemConfiguration, CoreFoundation, Foundation, SQLite, zlib, libc++ and
libSystem. Linkage to networking libraries does not override the sandbox's
network denial.

Five phases ran in separate subprocesses with a scrubbed environment, denied
network, file writes, home and repository reads, fork and subprocess spawning;
exec was restricted to the trusted framework interpreter. Denial canaries
passed, including a loopback connection, home and repository reads, file write,
fork and spawn. Each phase had 20 seconds of CPU, 64 file descriptors, core
dumps disabled, a 30-second wall timeout and a sampled 768 MiB RSS watchdog.
The watchdog was not a hard kernel-enforced memory limit. The ordinary macOS
Python launcher initially failed because its framework `posix_spawn` was
blocked; launching the same framework interpreter directly preserved all of
the above denials and correctly selected the disposable virtual environment.

| Phase | Result |
| --- | --- |
| Python startup and isolation | Passed; CPython 3.14.10 ARM64, disposable environment active. |
| NumPy import | Passed; NumPy 2.5.4 and a small numeric addition. |
| Runtime import and discovery | Passed; ONNX Runtime 1.31.1 reported CoreML, Azure and CPU providers. |
| Synthetic inference | Passed with **CPUExecutionProvider only**; a tiny Cast/Unsqueeze/Tile graph produced exact expected values 2 and 3, shape `(1, 2, 384)`. Session creation plus inference took 0.003649 seconds; process-reported peak RSS was 58,310,656 bytes. This is not a performance benchmark. |
| Kernel-registry call | **Crashed** on the single `get_all_opkernel_def()` attempt with signal 11, the subprocess equivalent of shell status 139. No repeat was attempted. |

The new `Python-2026-11-06-074725.ips` crash report records a null-address
`SIGSEGV` / `EXC_BAD_ACCESS` and the same `KernelDef` binding frames and Mach-O
UUID as the earlier reports. The fault is reproduced and localized to that
binding call; the underlying cause, including any Python ABI or sandbox
contribution, is not established. Successful CPU inference establishes only
that this tiny graph worked in this process configuration. Since a native
runtime call still crashes, broader runtime reliability and readiness for real
model execution remain **blocked**. The source model's precise upstream
revision, numerical parity and semantic relevance remain unverified. No real
model, tokenizer, application database or running service was accessed.

The ephemeral wheel manifest and sanitized subprocess results were retained
inside `/private/tmp/repopilot-ort-runtime-fjkjao5k`; they may disappear when
the operating system clears temporary files.

### Real-model smoke-test preflight — blocked, 2026-11-06

The separately authorized smoke test stopped before model access. The approved
disposable environment still had CPython 3.14.10 ARM64, ONNX Runtime 1.31.1
and NumPy 2.5.4, but had no `tokenizers` distribution or importable module.
RepoPilot's local adapter requires `tokenizers==0.23.3`; installing another
dependency was explicitly outside this smoke-test authorization. No replacement
tokenizer or hand-written substitute was used.

A search of the application Python source found no direct calls to
`get_all_opkernel_def` or other private ONNX Runtime pybind APIs. The local
adapter uses the public `InferenceSession` API. This source audit does not
establish the behavior of all runtime internals; the kernel-registry fault
described above remains unresolved.

Because the prescribed environment was incompatible, neither pinned artifact
was opened or rehashed during this preflight, no current provider probe or real
model session was run, and no query or code embeddings were produced. The
earlier artifact hashes and CPU-only synthetic-graph result remain historical
observations, not results from this smoke test. Explicit authorization for an
appropriate isolated tokenizer dependency or another compatible approved
environment is required before a new preflight. The export's upstream revision,
numerical parity and semantic relevance remain unverified; application
embeddings were not enabled.

### Real CodeRankEmbed smoke-test retry — 2026-11-06

With separate authorization, the existing disposable environment at
`/private/tmp/repopilot-ort-runtime-fjkjao5k/venv` was retained and
`tokenizers==0.23.3` plus its required dependencies were installed from
verified wheels. The GIL-enabled CPython 3.14.10 ARM64 interpreter, ONNX
Runtime 1.31.1 and NumPy 2.5.4 were unchanged. The stable-ABI tokenizer wheel
and the complete dependency closure were matched to both official PyPI release
metadata and the project lock before offline installation. The already
installed `packaging==26.3` satisfied its requirement; its verified wheel hash
appears in the earlier runtime-diagnostics table. The 15 newly installed wheels
were:

| Installed wheel | Verified SHA-256 |
| --- | --- |
| `tokenizers-0.23.3-cp310-abi3-macosx_11_0_arm64.whl` | `68649e97d5b43c44c031d8d848874a6eecae8f8fe40ea989aa777a5a83aca716` |
| `huggingface_hub-2.4.0-py3-none-any.whl` | `42ecfd93ede47bdd333daebbf66a32d7bfe2e18752754fe4d2d4f98a0179d801` |
| `click-8.5.0-py3-none-any.whl` | `255bc9599cf7748b4b1a446ccc735421bd08a2ae529a8b88597d3de5664ee360` |
| `filelock-4.2.9-py3-none-any.whl` | `a379c50a729e5b68c8519a4d26489f755d9769960a236ecd838190e2a78db2e9` |
| `fsspec-2026.9.0-py3-none-any.whl` | `8dd6e646e99ea382bd85f97a45e6b526a442d79423a7dc673f1e2756d05fcb5f` |
| `hf_xet-1.8.0-cp38-abi3-macosx_11_0_arm64.whl` | `3e8934784425781f0f779b91044df441f3a7af4dab47375d7e3aeaecbb8eecb4` |
| `httpx2-2.16.0-py3-none-any.whl` | `fd2c5d7909e8d86fe92d53020c310ca0e4e431b838c207c5754b9bbf0308d49a` |
| `pyyaml-6.0.3-cp314-cp314-macosx_11_0_arm64.whl` | `34d5fcd24b8445fadc33f9cf348c1047101756fd760b4dacb5c3e99755703310` |
| `tqdm-4.70.1-py3-none-any.whl` | `c293e525e6fef9c20e8728fd4612df02a0aa31bb5fe91ecd93e123b1b7bffa73` |
| `typing_extensions-4.16.0-py3-none-any.whl` | `481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8` |
| `anyio-4.15.1-py3-none-any.whl` | `6152fdbbf9a77fdec97731721bebf7c4c44f7c29b424b0065826173efc7ed101` |
| `httpcore2-2.16.0-py3-none-any.whl` | `5c4358319f2602d984ad93182c9fee5160f22e9da7babdda870a5e7c4e2dc34f` |
| `idna-3.20-py3-none-any.whl` | `ab7ae7122974553370f0bdb919e1a960b2cd1bc1ef0276416d896db81c14582c` |
| `truststore-0.10.5-py3-none-any.whl` | `9aaaedaefaf06d8b206278cf8b5012bc897f485a874503501e12d776df78951c` |
| `h11-0.16.0-py3-none-any.whl` | `63cf8bbe7522de3bf65932fda1d9c2772064ffb3dae62d55932da54b31cb6c86` |

Installation used `--offline --no-index --no-deps --require-hashes --no-build`
and no downloaded installation scripts. Wheel dependency metadata was compared
with PyPI after normalizing equivalent requirement formatting. Installed
dependency-version checks passed. Neither the project environment nor the
project lock was modified.

Before execution, `shasum -a 256` rechecked model SHA-256
`12ba359756210927940f8a9ec569cc7d6d6f091e7fcfae6cbe09bba6aab8830d`
and tokenizer SHA-256
`ea725c60b9022a7a491ffc348b5622a199853c806d625f673d0e2ebf1c3b5312`.
The worker rechecked both hashes again against the exact bytes used. The model
was 547,637,263 bytes and the tokenizer 711,650 bytes. The export revision was
`72d8b338380c0b83d02b1e38b40b7b778c1c8703`.

The macOS sandbox denied network, unrelated home and repository reads, fork,
and child spawning; it permitted read-only access to the two pinned artifacts
and writes only within a private temporary output directory. Canary checks for
those permissions passed. The worker used a scrubbed environment, CPU-only
execution, one intra-op and one inter-op thread, sequential execution, batch
size one and at most 64 tokens. A 180-second wall timeout, 120-second CPU limit
and sampled 3 GiB RSS watchdog applied. The attempted address-space limit
raised `ValueError`; consequently the memory watchdog was sampled and **not**
a hard kernel-enforced memory limit.

The pinned tokenizer imported and validated PAD/CLS/SEP IDs 0/101/102, right
truncation, exactly one query instruction prefix, no code-document prefix,
and int64 IDs, attention masks and token-type IDs. The fixed query used 18
tokens; the fixed code used 14. One ONNX Runtime 1.31.1 session initialized
with `CPUExecutionProvider` only and ran the approved query, code and one query
repeat. Float32 outputs had respective shapes `(1, 18, 768)`, `(1, 14, 768)`
and `(1, 18, 768)`. All values were finite, the first-token CLS vectors were
nonzero, each normalized vector had length 768 and norm 1.0, and the repeated
query's maximum normalized-vector difference was 0.0 at `rtol=1e-5`,
`atol=1e-6`.

Session initialization took 0.632447 seconds; query, code and repeated-query
inference took 0.010723, 0.006546 and 0.006737 seconds respectively. The
worker reported peak RSS 1,473,921,024 bytes. These are single-run observations,
not benchmarks. No complete vector was persisted. The earlier kernel-registry
introspection crash was not invoked and did not affect this session, but its
cause remains unresolved. The export's exact upstream source revision,
numerical parity and semantic retrieval quality remain unverified. No
application repository embeddings, database operations or service changes
were made. A real held-out retrieval evaluation requires separate approval,
independent labels and a reviewed isolation and resource plan.

### Evaluation readiness and procedure

No independently labeled held-out dataset, authorized real-model retrieval
capture, or retrieval-quality result is available to this workflow. The
two-input real-model smoke test above is a compatibility observation. Before
evaluation, select and license the repositories and independent labels, pin
their commits and source ranges,
record label provenance, and freeze tuning choices before opening the held-out
set. Use only approved disposable PostgreSQL and source fixtures, with no
network access during inference or source transmission. Preserve each snapshot,
chunk fingerprint, model contract and citation for all compared rankings.

The new synthetic runner freezes complete fixture issue context and calls
production `build_queries_for_version` and `retrieve_candidates` with the same
`terms-v2` ranking context, snapshot-fenced exact `search_vectors`, and existing
reciprocal-rank fusion. It verifies one shared fixture inventory, chunk
fingerprints, citation structure and controlled-vector identity across all
three modes. Production `terms-v2` currently uses the title, bounded body and
labels; comments are recorded and ordered in the context but are not inputs to
that worker's retrieval. The full schema, fixed fairness settings and executable
disposable procedure are in [retrieval-capture-dataset-v1.md](retrieval-capture-dataset-v1.md).

The real-data runner and independently labeled dataset do not yet exist. Future
work must verify source fingerprints and citations against pinned Git blobs and
produce paired captures of actual `terms-v2`, CodeRank semantic and hybrid
rankings under an approved offline isolation plan. The standalone search
endpoint's keyword branch is not the full investigation `terms-v2` pipeline.
The scorer validates supplied capture consistency but does not authenticate
capture provenance or prove label independence. This synthetic implementation is
not authorization to generate real embeddings or benchmark repositories.

The Step 2B.3B [provenance preflight](retrieval-capture-dataset-v1.md#git-and-capture-provenance-preflight)
now validates supplied paired captures against source chunks reconstructed from
local pinned Git objects and checks strict pilot/held-out metadata. It does not
authenticate the supplied capture producer, prove inventory completeness or
perform real-data capture. A selection and annotation protocol and an offline
resource proposal are documented alongside it. No real repositories, issues,
labels or CodeRankEmbed embeddings were collected in this step.

Step 2B.3C subsequently prepared an unapproved, metadata-only
[source-approval request](benchmark-source-approval-v1.md) for three
repositories and ten pilot issue leads. It did not collect issue bodies,
comments or source, establish relevance labels, or run real inference.

Score the frozen captures with the command above, recording Recall@1/5/10,
MRR, nDCG@10, per-language and per-repository recall, invalid citations, missing
embeddings and retrieval p50/p95. Separately record generation batch sizes,
warm-up policy, embedding-generation latency, process peak RSS, hardware,
runtime versions and limitations. Report unjudged results as unknown and use
paired uncertainty estimates where the sample permits. There are no Step 2B
quality or performance measurements to report yet.

### Go source preparation risk — 2026-11-07

The separately approved chi #1188 source-applicability review is suitable for
independent human review, but its five-file syntax-aware indexing check remains
blocked by a Tree-sitter native crash. The subsequent
[synthetic-only investigation](benchmark-chi-1188-source-review.md#synthetic-only-native-crash-investigation)
located a prior failure during node access after parsing; it did not establish
the native cause. Four small synthetic Go cases and the focused small Go test
passed, which does not establish safety for larger source files. The existing
in-process parser fallback cannot catch SIGSEGV. Do not treat this partial
source selection as a complete benchmark corpus or as validated Go indexing.

A separately approved Go-only experiment then exercised Tree-sitter 0.25.2
with the existing Go grammar and unchanged RepoPilot adapter in a disposable
environment. Four small cases, a 200-function case and four independent runs
of a 700-function case passed. These synthetic results make 0.25.2 a candidate
for further testing; they do not prove universal stability or authorize a
production dependency change. The retained chi files were not re-read or
parsed, and the five-file syntax-aware check remains outstanding. See the
[experiment results](verification.md#step-2b3h3--tree-sitter-0252-synthetic-go-compatibility-2026-11-07).

A separately approved [synthetic cross-language matrix](tree-sitter-0252-synthetic-matrix.md)
subsequently passed all 15 registered extensions with the locked grammars
under Tree-sitter 0.25.2, including a fresh-process repeat of each and a
larger workload per grammar. Existing production chunk IDs are random UUIDs,
however, so deterministic ID generation across new snapshots is not
provided; repeatable fingerprints were checked only with fixed synthetic
identities. No dependency pin or production code changed.

The subsequent staged update changes the local Tree-sitter declaration and
lock to 0.25.2 while preserving every grammar and unrelated lock record.
The user clarified that random publication UUIDs are the intended identity
contract; the new synthetic identity tests passed on disposable SQLite.
An earlier PostgreSQL attempt was blocked by Docker access; Step 2B.3H.8
later passed the selected disposable PostgreSQL gate with **260 passed,
0 failed, 0 skipped and 1 deselected**. The seven previously skipped cases
and the PostgreSQL migration test executed. No normal service was restarted
or reconfigured. See
[verification](verification.md#step-2b3h8--disposable-postgresql-gate-2026-11-07).

Production rollout and a later real-source retry remain distinct approval
steps. Parser process isolation is still worth reviewing because in-process
fallback cannot contain SIGSEGV. This issue is separate from the unresolved
ONNX Runtime kernel-registry crash. The ONNX export's exact upstream source
revision and numerical parity remain unverified, and semantic retrieval
quality remains unmeasured. No model inference or embeddings were run in
these parser experiments.

### Test-only parser supervision — Step 2B.3H.9

A disconnected [synthetic-only subprocess prototype](supervised-parser-prototype.md)
now exercises the existing parser and chunker behind a bounded JSON contract.
The final prototype tests passed **64 cases**; separately, **53** existing
small parser/indexing tests passed and **3** database-dependent cases were
deselected. Child crashes, timeouts and invalid responses were simulated
without triggering a native SIGSEGV. The current ingestion worker still
parses in-process; neither the prototype nor multilingual indexing was enabled.
The sandbox and sampled RSS watchdog are not a complete security boundary for
hostile repositories. A production integration requires separate approval.
The previous Tree-sitter and ONNX Runtime native-crash causes, ONNX export
provenance and parity, and semantic retrieval quality remain unresolved.

### Disabled-by-default ingestion integration — Step 2B.3H.10

The [supervisor integration](supervised-parser-prototype.md#step-2b3h10--disabled-by-default-integration)
is wired into multilingual collection behind
`INDEX_MULTILINGUAL_SUPERVISED_PARSER_ENABLED=false`. Supervised jobs retain
their required mode and fail closed if the flag or reviewed isolation is
unavailable. The normal Python and unsupervised multilingual paths remain as
before. **62** mocked-transport integration tests and **25** sandboxed
child/transport tests passed; real multilingual grammar integration and the new
PostgreSQL gate remain unverified because the disposable dependencies are
missing. No model, real repository or normal service was used.

### Supervised integration verification — Step 2B.3H.11

The restored disposable environment passed **119** synthetic native
supervisor/child tests across all 15 registered extensions, **322** selected
PostgreSQL and synthetic regression tests with one deselection, and **3**
native-child PostgreSQL publication, migration and schema-drift tests. The
separate harness safety suite passed **44**; **2** later interpreter checks
also passed. The actual `run()` availability
gate and fail-closed isolation checks were exercised; no selected test failed
or skipped. The PostgreSQL native phase uses a test-only IPC broker, so the
exact unproxied worker-plus-database process arrangement remains untested.
See [verification](verification.md#step-2b3h11--supervised-parser-verification-2026-11-08).

These are synthetic parser and publication checks, not semantic retrieval
quality evaluation. Both multilingual flags remain disabled by default; no
normal service, real repository or model was used. Linux isolation, the
sampled memory limit, the earlier native crash, ONNX export parity and real
retrieval quality remain unresolved.
