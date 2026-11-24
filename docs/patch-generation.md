# Evidence-bound patch proposals

This is a staged implementation, not an activated fixing service. `PATCH_PROPOSALS_ENABLED`
defaults to false. The patch-provider registry defaults to **unavailable**; an Ollama adapter
can be selected explicitly, and the deterministic provider in the tests remains a synthetic
fixture, not AI. P7 did not install or invoke a model; P7.1 installed one without running
inference. P7.2 made two authorized synthetic local-inference calls, neither of which
produced an accepted candidate.
There is no paid provider, repository write, pull-request operation or automatic application.

A request is scoped to an authenticated user's completed evidence investigation, its
repository, tenant, session, pinned snapshot and commit. The existing GitHub access,
membership, CSRF, revocation and snapshot guards apply. Creation rechecks the evidence
manifest and reconstructs evidence-backed files from contiguous index chunks. Each complete
file must match its indexed SHA-256; source is bounded to five files, 128 KiB per file and
256 KiB total. If more than five eligible files are referenced, the first five in evidence
rank order are used; other files are not part of the proposal context. The published index
may itself be a partial snapshot, and this interface does not yet persist a separate context
truncation flag. Files with recognized credential patterns are withheld. Issue text is
bounded and sanitized. This is not a complete secret detector; external provider use needs
separate review and authorization.

The provider-neutral `patch-generation-v1` request has fixed trusted instructions separate
from untrusted issue text, source and evidence. It carries the repository and tenant IDs,
repository name, investigation and snapshot IDs, commit, issue ID, file IDs and SHA-256
hashes, plus the evidence ranges, fingerprints and commit-pinned citations. The builder
rechecks file hashes, bounds, identities, citation paths and line ranges before invoking an
adapter. The worker verifies that the assembled repository and tenant still match the
authorized job. Existing evidence-manifest verification remains responsible for the
database-backed chunk fingerprints; this request is not independent producer authentication.

`PATCH_PROVIDER_MAX_INPUT_BYTES` defaults to 524288, `PATCH_PROVIDER_MAX_OUTPUT_BYTES` to
307200 and `PATCH_PROVIDER_TIMEOUT_SECONDS` to 30. Each can be lowered, but cannot be raised
above its default. These limits cover canonical request bytes, returned response bytes and
the timeout passed to the adapter, respectively. The Ollama transport additionally enforces
its own streaming byte limit and asynchronous deadline; arbitrary other provider implementations
cannot be forcibly interrupted merely by passing a timeout. Configuration validates provider and model
identities and rejects missing required credentials before generation. Credentials are not
part of the request or the configuration's `repr`; recognized credential patterns and
the configured provider credential are rejected from request data. This screening is not
complete secret detection or a prompt-injection guarantee.

The shared response is strict JSON with a diff, rationale and evidence IDs. Unknown fields,
duplicate JSON keys, foreign citations and uncited changed files are rejected. A candidate
is statically checked before it is stored. Provider identity, diff, file IDs and before/after
hashes, evidence fingerprints and pinned citations are recorded. Stored patches are
revalidated against the snapshot and evidence before they are shown or reviewed. No native
code, shell command or model output is run. The only passing provider responses in P5 were
original deterministic test fixtures.

Under `/v1/repositories/{repository_id}/investigations/{job_id}/patch-proposals`, the API
supports list/create, detail, `static-validation`, `test-validation` and `review` operations.
Creation takes a UUID `request_id` for idempotency. Review decisions are
`approved_for_review` or `rejected`; neither publishes or applies a patch. Pending jobs can
be rejected/cancelled, fencing any late worker result. Cancellation does not forcibly stop
an arbitrary already running provider call. The Ollama adapter monitors the worker lease and
closes its HTTP request when cancellation is observed, but cannot guarantee that the Ollama
daemon stops processing immediately after the connection closes. Three active and 20 total proposals per investigation/user
are allowed; dispatch retries stop after 20 attempts. This is not a substitute for a
deployment-wide rate and cost policy.

Proposals and their outbox are added by migration `0017`, which is **not applied to the
normal database by this work**. The dispatcher does not query the new outbox while the flag
is false. Generation uses a leased, idempotent worker and rechecks access, issue identity,
source and evidence before publishing. Unverified output is discarded; failures expose
sanitized codes only. The stored diff may contain repository source and requires an explicit
retention/deletion policy and access review before real use.

The existing OpenAI Responses client is specific to investigation reports and their approval
and usage ledger; it is not a patch provider and is not automatically reused. No hosted
provider is selected or used by the patch registry.

## Opt-in Ollama adapter

The adapter uses the [Ollama chat API](https://docs.ollama.com/api/chat) with a
[JSON schema](https://docs.ollama.com/capabilities/structured-outputs), streaming disabled,
temperature zero, a bounded context/output token configuration, and truncation and context
shifting disabled in the request. It expects a strict object with `status`, `diff`, `rationale`,
`uncertainty`, `evidence_ids` and the changed `source_files` identities. An
`insufficient_evidence` response abstains. Candidate file IDs and SHA-256 values must match
the request, and the changed-file inventory must match the diff. The adapter then converts
the response into the existing provider-neutral format; the existing deterministic patch
validator runs again before publication. The uncertainty is included in the saved rationale.
The supported diff is still the narrow `--- a/...`, `+++ b/...`, `@@ ...` format without
`diff --git` headers. No model output is executed or applied to a checkout.

After separate installation, model-download and inference approvals, the configuration
required in an isolated, reviewed environment is:

```text
PATCH_PROPOSALS_ENABLED=true
PATCH_GENERATION_PROVIDER=ollama
PATCH_LOCAL_MODEL_ENABLED=true
PATCH_LOCAL_MODEL_NAME=qwen2.5-coder:7b
PATCH_LOCAL_MODEL_DIGEST=dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364
PATCH_LOCAL_MODEL_ENDPOINT=http://127.0.0.1:11434
```

These are instructions for a later approved environment; P7 did not set them in normal
services. The default provider is `unavailable`, the model is disabled and both model name
and digest are empty. The adapter accepts only an explicit lower-case local model tag and
the literal `http://127.0.0.1:<port>` origin. It rejects cloud-named models, non-loopback or
ambiguous endpoints, redirects and configured HTTP/HTTPS/ALL proxy variables; HTTPX also
uses `trust_env=False`. It never falls back to a hosted provider.

Before submitting issue/source data, a metadata-only preflight requires Ollama's experimental
`/api/status` to report cloud disabled, `/api/tags` to report exactly one local GGUF model
with the configured full digest, and `/api/show` to report GGUF completion capability without
remote model/host metadata. Servers without those signals fail closed. Configure cloud
disabling on the **Ollama daemon itself**, not just in RepoPilot; see Ollama's
[local-only controls](https://docs.ollama.com/faq#how-do-i-disable-ollamas-cloud-features).
The availability API performs only these metadata checks after releasing database locks,
then rechecks repository authorization. Passing them does not establish actual model
generation or output quality.

The stored model identity uses `tag@sha256:<digest>` for the configured and preflight-reported
model. It is not cryptographic attestation of the model that eventually handled the request.

Only the bounded issue title/body, pinned repository/investigation/snapshot/commit identity,
file identities and hashes, citation metadata, and evidence ranges with up to three adjacent
lines are sent as untrusted user data. Each snippet is capped at 8 KiB and their total at
64 KiB; oversized evidence fails rather than being silently truncated. Tenant IDs, GitHub
credentials, database URLs and unrelated source lines are not included. Existing secret
screening is not complete, and a local model can still follow malicious instructions in
untrusted text; deterministic validation remains authoritative. Response bodies and source
are not intentionally logged.

Loopback and self-reported metadata do **not** authenticate the process listening on the
port or prove that it cannot relay data. A malicious local listener, a model/tag change
between preflight and generation, or a separately configured forwarding daemon remains a
potential disclosure risk. Before real source is sent, the operator must independently
verify the Ollama process, local model identity and daemon egress controls; the current
adapter does not enforce an OS-level sandbox on Ollama. In a container, `127.0.0.1` refers
to that container; reaching a host Ollama through `host.docker.internal` is deliberately
unsupported and fails closed. P7.2 exercised the installed model locally with synthetic
inputs; both responses abstained and no generated diff was accepted.

### P7.1 installed local artifacts

The official signed and notarized Ollama **0.40.16** app and the exact
`qwen2.5-coder:7b` model are retained under the owner-only
`~/Library/Application Support/RepoPilot/toolchains/ollama-p71` directory. The model reports
GGUF, Q4_K_M and 7.6B parameters. The registry manifest and local model metadata both identify
`dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`; every referenced
blob was independently hashed. Ollama 0.40's local legacy manifest is a wrapper containing
an additional reference to the unchanged registry manifest; its versioned alias resolves to
the verified registry-manifest blob. See the [P7.1 verification record](verification.md#step-p71--official-ollama-and-model-artifact-verification-2026-11-14).

The cloud-disabled setting is in this installation's **private** home, not the user's default
`~/.ollama`. The temporary server was verified on `127.0.0.1:11434`, then stopped; it was not
registered as a login item. A metadata-only call to RepoPilot's readiness method passed
against that server, but no model was loaded and no inference endpoint was called. The digest
above records the verified installed artifact; a future test must recheck it and independently
review the local daemon and egress boundary before sending any source. Any further inference,
real-source use and enabling RepoPilot in an environment require the appropriate separate
authorization. Normal-service configuration remains disabled.

### P7.2 synthetic inference result

P7.2 intended to submit two original, two-line Python fixtures to the verified local model.
The direct Ollama call and the actual RepoPilot adapter call both returned schema-valid
`insufficient_evidence` responses. The original request bodies were not retained, so the
historical contents seen by the model cannot be independently established. The adapter
correctly returned `local_model_insufficient_evidence`; it did not accept or statically
validate a candidate diff. This is evidence that local inference and the abstention path
work, not that the model can generate an acceptable patch. See the
[P7.2 verification record](verification.md#step-p72--local-synthetic-inference-2026-11-14)
for the exact fixtures, isolation, resource observations and limitations. No generated code
was executed, and before/after patch execution remains blocked.

### P7.3A offline abstention investigation

Intercepting the current adapter's final synthetic HTTP requests shows the exact fixture
implementations in `snippets[*].text`, with their issue descriptions, paths, line ranges,
hashes and evidence IDs. The system message requests a minimal diff for supplied
evidence-backed files and permits abstention; it does not explicitly explain the
`snippets[*].text` field to the model. The prompt uses JSON as untrusted data, and its
presentation may affect model behavior, but no application-side cause for P7.2's abstentions
was demonstrated. No production prompt or validator was changed on that hypothesis.

The P7.3A JSON schema required all six top-level fields, allowed the `candidate` and
`insufficient_evidence` statuses and forbids extra fields. It is not a discriminated union:
an empty `diff` is schema-valid for either status. At that stage a candidate with an empty
or invalid diff was rejected by the existing deterministic validator. A schema-valid abstention
is recorded as the sanitized `local_model_insufficient_evidence` failure with no patch;
the worker does not store the model's rationale as a separate abstention record.

The following are diagnostic distinctions, not new API statuses or guarantees that the
application can infer semantic sufficiency automatically:

- **Source available and sufficient:** an evidence-backed snippet can support a proposal;
  static validation checks identities and patch structure, not whether the fix is correct.
- **Source missing:** the current request builder rejects an empty file or evidence set
  before calling the provider; it does not ask the model to invent source.
- **Source incomplete, conflicting evidence, or patch not justified:** the model can
  abstain using the existing `insufficient_evidence` status; source reconstruction also
  rejects incomplete indexed files before provider invocation.
- **Provider unable to generate:** an abstention or a separate sanitized provider error may
  occur; it must not be represented as a validated fix.

The offline tests cover these contracts with synthetic inputs and mocked responses, not
model performance. The single recommended follow-up is a separately approved synthetic
call that privately captures the exact outgoing request and response and checks the existing
validators; no inference or request capture involving real source is authorized by P7.3A.

### P7.3B instrumented synthetic inference

One separately approved request ran through the actual local provider with its existing
prompt and validators. A test-only transport recorded the prepared request body before
passing that same request to the real local HTTP transport. The captured synthetic request
contained the entire two-line fixture, but the model returned a schema-valid
`insufficient_evidence` response and no candidate. The provider recorded
`local_model_insufficient_evidence`; diff validation and test execution did not occur.

The model's explanation acknowledged a signature and one code line but asked for the full
implementation. The captured request provides snippet start and end lines but no file-total
or end-of-file indicator, so it does not explicitly identify the snippet as the entire
synthetic file. This is a plausible ambiguity, not a proven cause of the model's response.
The exact synthetic request and response remain private; see the
[P7.3B verification record](verification.md#step-p73b--one-instrumented-synthetic-inference-2026-11-14)
for hashes and the bounded result. Further prompt changes or inference require separate
authorization. No actual model-generated patch has passed static validation or executed.

### P7.4 source coverage

The Ollama request includes `source-coverage-v1` metadata for each evidence snippet.
`COMPLETE_FILE` requires an internally supplied, complete pinned-file inventory record
whose snapshot, commit, repository, tenant, file ID, path, SHA-256 and independently
recorded byte length match the source bytes. The emitted snippet must also cover those
bytes exactly. `BOUNDED_EXCERPT` identifies a smaller verified range of such a file;
`UNKNOWN_COVERAGE` is used when a complete pinned-file record is unavailable or marked
incomplete. Unknown coverage does not claim a full-file size, line count, SHA-256 or byte
boundaries. A final visible line or a function boundary alone cannot establish completeness.

The identity record is an internal trust input and must come from an authenticated pinned
inventory; a caller-created record is not independent authentication. The current
`IndexedFile` schema does not persist the original byte length, so ordinary database-backed
patch contexts do not populate that record and remain `UNKNOWN_COVERAGE`, even if their
reconstructed content matches the indexed hash. No database schema or migration changed in
P7.4. The complete-file inference fixture used a separately fixed synthetic record, not a
real repository. Line ranges use one-based LF lines; verified byte ranges use zero-based,
end-exclusive UTF-8 offsets. Source text remains separate from the coverage notice.

One authorized local inference with the synthetic complete-file record still returned
`insufficient_evidence` and no diff. It does not establish why the model abstained. The
source-identity, evidence and diff validators remain unchanged in strength, and patch test
execution remains blocked. See the [P7.4 verification record](verification.md#step-p74--source-coverage-and-one-synthetic-retest-2026-11-15).

### P7.5 offline contract comparison

The current instructions allow an evidence-backed candidate without asserting a verified
root cause or tested fix, and also allow abstention. No contradiction explaining the four
observed abstentions was established. The model-facing flat schema still requires six
fields for either status and permits a `candidate` with an empty diff. The backend's
structured parser now rejects that empty candidate earlier; the same sanitized failure was
already produced by the downstream diff validator. Empty-diff abstentions still work. The
on-wire prompt and schema remain unchanged, as do source, evidence, path and diff validation.

A test-only discriminated alternative uses a nonempty candidate diff and a shorter
abstention branch with a missing-evidence description. It retains candidate source identities
and evidence IDs. Its shorter abstention shape is incompatible with the current production
parser, so it is not registered or enabled. In a mocked comparison with the same synthetic
source and identities, its system message was shorter but its generated schema and total
request were larger. This comparison does not predict model behavior. A prompt-only test
variant preserves the current schema for a future controlled experiment; any real inference
still requires separate authorization. See the [P7.5 verification record](verification.md#step-p75--offline-patch-contract-comparison-2026-11-15).

## P8 — Structured local source edits (2026-11-15)

The local Ollama adapter now supports a structured edit response: a `candidate` contains
exact `path`, `before`, `after`, and optional one-based `start_line` edits, a concise
explanation, and evidence references. `insufficient_evidence` remains a valid terminal
response and cannot contain edits. The model is asked for candidate changes, not to prove a
root cause or a tested fix. Source, issue text, and model output remain untrusted data.

RepoPilot binds the response to the existing candidate request: pinned snapshot and commit,
repository and investigation identities, source SHA-256, authorized file inventory, and
cited evidence. Each replacement must exactly match whole source lines inside an
evidence-visible range. Ambiguous matches require an exact line position; invalid paths,
stale identities, missing evidence, overlaps, unsupported text, and out-of-policy edits are
rejected. The model cannot supply executable commands or choose paths outside the supplied
source set. No path is opened and no file is changed by this conversion.

RepoPilot constructs a deterministic unified diff in memory and sends it through the
existing `validate_patch` checks for source context, paths, limits, and patch syntax. It
returns the existing `Candidate` contract, preserving proposal, outbox, worker, and UI
compatibility. The raw model edit response is not persisted as a new proposal format. The
provider is identified as `ollama_edits`; the direct-diff adapter remains available by
setting `PATCH_LOCAL_MODEL_STRATEGY=direct_diff`.

The safe strategy default is `source_edits`. This does not activate generation:
`PATCH_GENERATION_PROVIDER=unavailable`, `PATCH_LOCAL_MODEL_ENABLED=false`, and
`PATCH_PROPOSALS_ENABLED=false` remain the defaults. Strategy selection alone does not
create proposals or start a model. Do not change normal-service flags without separate
approval.

One actual local Qwen2.5-Coder 7B call using an original, complete 49-byte synthetic Python
file returned a candidate edit. RepoPilot verified the request's source SHA-256 and
evidence binding, constructed the minimal diff, and the existing static validator accepted
it. This demonstrates one synthetic candidate path only; it does not establish why earlier
requests abstained, prove a real-world root cause, or show that a fix works. No generated
code was run. Test execution remains unavailable behind the unresolved isolation gate.
See the [P8 verification record](verification.md#p8--local-structured-edit-generation-2026-11-15).

## P10 — persisted source provenance

Migration `0018` adds byte length, encoding, normalization and coverage to `indexed_files`.
Only the collector's whole-blob path can emit `COMPLETE_FILE`: the Git tree's declared
size is checked against fetched raw bytes, the bytes must decode as UTF-8 without
normalization, and SHA-256 is calculated over those exact bytes. Snapshot publication
reconstructs the indexed chunks and verifies both byte length and SHA-256 before it changes
the current publication. A mismatch aborts publication. Patch context repeats the hash,
length and encoding checks before creating a pinned file identity bound to snapshot, commit,
repository, tenant, file and path.

Migration backfills existing rows as `UNKNOWN_COVERAGE`; it does not infer completeness
from a chunk boundary or historical hash. Excerpts and records without the verified byte
identity remain unknown. A synthetic collector-to-persistence test exercises this forward
path and a legacy row; SQLite in-memory coverage is not PostgreSQL verification. Migration
`0018` is the source-tree Alembic head. The legacy migration regression applied the chain
through `0018` to temporary SQLite, but it has not been applied to PostgreSQL in P10.
The disposable PostgreSQL gate was blocked because the Docker daemon was unavailable and
no native PostgreSQL server tools were installed. No real source was sent to a model, no
new inference ran, and generation remains disabled in normal services.

### P11 PostgreSQL verification

P11 supersedes the preceding database-blocked status for disposable integration coverage.
The current proposal persistence and worker contracts passed on private PostgreSQL 16.16;
the full Alembic chain reached `0018`, with a clean fresh-schema drift check. No model call
was made and no generated patch was executed. The provider remains disabled by default.
See the [P11 verification record](p11-postgresql-verification.md).

### P18 proposal-only product

Candidate detail and review retain their existing contracts. Export reauthorizes access,
revalidates the current source and evidence, requires verified complete-file identities and
a saved patch SHA-256, and serves the exact candidate diff for manual use. Older records
without the digest need a static recheck; source records without complete identity need
verified reindexing. Approval is for further review, and automated execution remains
disabled. See the [P18 proposal-only record](p18-proposal-only-product.md).
