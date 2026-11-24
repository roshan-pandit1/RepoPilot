# Synthetic retrieval capture and future dataset contract

The `synthetic-capture-v1` runner is a development-only mechanical test. It
loads only the registered, SHA-256-pinned fixture in
`apps/api/evaluation/fixtures/synthetic-capture-v1.json`, creates synthetic rows
in an explicitly marked disposable PostgreSQL database, and never loads a real
model or contacts GitHub. Its synthetic commit and GitHub-shaped citations are
fixture identities; they are not claims that a remote Git commit exists.

## Issue context and labels

`issue-context-v1` requires an issue ID and number, state, UTC creation and
update timestamps, title, body, ordered labels, comment count and complete
comment records. Each comment has an ID, UTC timestamps and body. Missing
fields, duplicate comments, inconsistent counts and malformed timestamps are
rejected. Comments are retained in the fixture and hashed context, and ordered
by `(created_at, id)`. Current production `terms-v2` does **not** use comments
for query construction or protected-symbol ranking; the capture records that
fact rather than silently adding them.

The runner calls the same `build_queries_for_version('terms-v2', ...)` and
`retrieve_candidates(..., ranking_context=(title, bounded_body))` used by the
investigation worker. For this declared configuration the body is bounded to
4,000 characters; the production builder bounds the title to 1,024 characters,
uses at most 20 labels of at most 100 characters, filters its existing
instruction-sensitive lines, and produces at most three queries. Identifiers
and stack-trace text are processed by that existing builder; there is no
separate invented stack-trace parser. Capture output stores hashes of the full
normalized context and generated query text, not raw issue text or comments.

In particular, the builder extracts up to two distinct snake-case or
camel-case identifier tokens from the bounded title, body and labels, adds
bounded title/label terms, and may append distinct body terms when the title is
informative. It applies its existing case-insensitive deduplication and stop
words. Error names or file references in a stack trace affect retrieval only
through those general token rules; they are not separately resolved as paths or
exceptions. The protected-symbol reranker uses its existing bounded title/body
tokens and retains the first four baseline candidates. Capturing the exact
builder output and ranking context avoids inventing extra semantics for this
benchmark.

The fixture has three source files, six explicit inclusive-line chunks, Python
and TypeScript, similar symbol names, two ordered comments, a stack trace, one
issue with two positive labels, and one insufficient-evidence issue. Its source
is artificial and is never executed. Every source file hash, chunk range,
chunk fingerprint, repository/tenant/snapshot binding and citation is checked.
The checked-in fixture contains annotation instructions, exclusion criteria,
fixture-derived provenance and adjudication status. Grades are 0–3; an
adjudicated example needs a positive label, while an insufficient-evidence
example has no asserted relevance labels.

## Fair comparison

All modes use the same verified six-chunk inventory. The fixed configuration
declares three query slots, ten lexical candidates per query, twenty lexical
evidence candidates, a semantic candidate pool of twenty, top ten results and
reciprocal-rank fusion `k=60`. The fixture uses explicit source-line chunks and
manually controlled three-dimensional unit vectors. The semantic query is
identified by the issue title; the vector is supplied by the fixture, not
generated from that text. Missing vectors reject the run, empty result sets
remain empty, and no fallback is silently substituted.

Lexical ranking and tie-breaking are the production `terms-v2` path. Semantic
ranking uses the existing exact pgvector cosine implementation, with its
path/line/chunk tie-breaks. Hybrid ranking uses the existing reciprocal-rank
fusion and its chunk-ID tie-break. Every returned item must belong to the same
verified inventory. Synthetic semantic and hybrid output is explicitly marked
`MECHANICAL_TEST_ONLY`; it is not CodeRankEmbed relevance evidence.

The deterministic `mechanical-report.json` uses the held-out scorer's
`score_query` function; timing observations are excluded from that stable
report. `captures.json` contains the scorer-shaped records and observed
latencies; `observations.json` separately labels those timings as synthetic.
All three files are created exclusively with mode `0600` in a new `0700`
directory. Raw source, issue text, comments, credentials and vectors are not
written into the capture files. A known-pattern credential screen is applied to
input text, but is not a comprehensive secret detector; the executable runner
therefore accepts only the pinned synthetic fixture.

Unjudged results are reported as such. Judged precision and precision bounds
do not turn unjudged results into verified negatives. The current nDCG
calculation assigns unjudged results zero gain, so it must be interpreted with
the reported judgment coverage. An insufficient-evidence issue has undefined
recall and MRR rather than an invented negative judgment.

## Future held-out data

The context-aware `heldout-v2` scorer contract requires `split: held_out`, a
predeclared `retrieval_config`, dataset-level annotation instructions,
adjudication protocol and exclusion criteria, plus per-query repository,
40-character commit, query, language, category, label provenance,
adjudication status, complete `issue_context` and source-range relevance
grades. A valid config uses `capture-config-v1` fields for query version and
limits, candidate pools, top-k, fusion, chunking, semantic-query representation
and missing-data policies. The scorer validates pinned Git ranges and checks
that captures agree on the snapshot, universe digest, context digest, semantic
query digest, query-builder hashes, configuration and vector-space identity.
Those fields detect inconsistencies; supplied capture provenance and label
independence are not authenticated by the scorer.

`heldout-v1` remains available for existing records but is labeled
`legacy-query-only-unverified`. The synthetic fixture is development data and
is rejected by the held-out Git validator unless a real matching Git source is
provided; its fake commit must not be presented as one. Tests use an in-memory
synthetic source adapter for scorer integration. The split-separation helper
rejects overlapping example/issue identities or normalized title/body pairs,
but cannot detect paraphrases or prove independent labeling.

For future real data, choose licensed repositories and exact commits, define
exclusion rules and eligible source chunks before judging, and have reviewers
independently identify graded source ranges without seeing candidate rankings.
Record reviewer provenance, adjudicate disagreements and unknown cases, freeze
the development and held-out manifests separately, and audit overlap and
dataset hashes. Do not create labels by copying model results. No such real
dataset or authenticated real-model capture exists in this milestone.

## Running the registered synthetic fixture

From `apps/api`, the following creates a new loopback-only PostgreSQL container
with a temporary filesystem. It uses trust authentication only for the isolated
synthetic database, so other local users could connect while it is running; do
not put private data in it. `--pull=never` requires an already available image.
It does not start or connect to either Compose project.

```sh
bash <<'SH'
set -eu
capture_id=$(.venv/bin/python -c 'import secrets; print(secrets.token_hex(8))')
capture_container="repopilot-capture-${capture_id}"
capture_db="repopilot_capture_disposable_${capture_id}"
docker run -d --pull=never --name "$capture_container" \
  --tmpfs /var/lib/postgresql/data:rw \
  -e POSTGRES_USER=capture_fixture -e POSTGRES_DB="$capture_db" \
  -e POSTGRES_HOST_AUTH_METHOD=trust -p 127.0.0.1::5432 pgvector/pgvector:pg16
ready=0
for attempt in $(seq 1 30); do
  if docker exec "$capture_container" pg_isready -U capture_fixture -d "$capture_db"; then
    ready=1
    break
  fi
  sleep 1
done
test "$ready" = 1
docker exec "$capture_container" psql -X -v ON_ERROR_STOP=1 -U capture_fixture \
  -d "$capture_db" -c "COMMENT ON DATABASE ${capture_db} IS 'repopilot-synthetic-capture-v1'"
capture_port=$(docker inspect --format '{{(index (index .NetworkSettings.Ports "5432/tcp") 0).HostPort}}' "$capture_container")
test -n "$capture_port"
capture_url="postgresql+psycopg://capture_fixture@127.0.0.1:${capture_port}/${capture_db}"
env -i PATH=/usr/bin:/bin LC_ALL=C REPOPILOT_CAPTURE_DATABASE_URL="$capture_url" \
  .venv/bin/python -B -m app.evaluation.capture_synthetic \
  --output-dir "/private/tmp/repopilot-capture-${capture_id}"
SH
```

The command rejects anything except the registered fixture, a clean environment,
loopback with an explicit non-default port, the `capture_fixture` user, a
randomly named `repopilot_capture_disposable_...` database, the database
comment marker and an empty public schema. It refuses existing output paths.
The test fixture creates and drops tables, so integration tests must receive a
**separate, empty, marked disposable database** through `TEST_DATABASE_URL`;
they validate the target before invoking the destructive fixture. No database
or Docker volume is deleted by the command above.

The runner needs only a loopback database connection and makes no external
request, but the command does not itself impose an OS-level network or
filesystem sandbox. Its clean environment is not a substitute for an isolation
boundary when evaluating real data; future real-model runs need their own
reviewed offline sandbox and approved source access.

## Real-data selection and independent annotation plan

At Step 2B.3B no real pilot or held-out issue had been selected or independently
labeled: verified counts were **0 pilot, 0 held-out**. Available local
documentation does not establish the licenses, issue histories, source sizes
and exact usable commits of three to five independent public repositories, so
there is no approved shortlist. `roshan-pandit1/RepoPilot` is a locally known
source lead, but its license and suitability for a new corpus have not been
established here. Existing project benchmark questions and labels were used in
development and tuning; they must not be reused as independent held-out data.
Step 2B.3C subsequently proposed ten unapproved pilot leads in the
[source-approval manifest](benchmark-source-approval-v1.md); there are still
zero approved or independently labeled real examples.
Step 2B.3D separately authorized and captured four HTTPX issue contexts for
triage only. That did not approve their benchmark inclusion or create source
labels; two of the complete contexts exceed `issue-context-v1` limits.
Step 2B.3E separately reviewed three Python files at the pinned HTTPX commit
for issue #3734; see the [source review](benchmark-httpx-3734-source-review.md).
The named function and stream classes exist in that source, but the reporter's
exact HTTPX revision remains unknown and no positive labels have been created.
The three-file selection is a partial private review, not a complete snapshot,
Git-object repository, production index or benchmark input. The other retained
issue contexts were not modified or re-fetched.
Step 2B.3F's authorized metadata review found that GitHub reports the pinned
HTTPX commit as an ancestor of a later commit referenced by #3734, whose
message claims a fix. The reporter's source version and actual behavior remain
unverified, so #3734 stays outside positive held-out labels. It is only a
potential diagnostic or abstention case; no expected result is independently
established. The [review packet](benchmark-httpx-3734-source-review.md)
records alternative existing pilot leads, not approved replacement examples.
Step 2B.3G separately captured three of those existing leads under bounded,
private issue-context approval. All three complete contexts validate as v1;
[chi #1188](benchmark-replacement-issue-triage-v1.md) is recommended for a
future source review because the reporter names a version and a short commit
matching the proposed snapshot prefix. That claim and source applicability
remain unverified, and no real relevance label or benchmark capture exists.
Step 2B.3H subsequently linked the reported chi short SHA to the approved
full commit through GitHub metadata and statically reviewed five verified Go
files. [Applicability is supported for independent review](benchmark-chi-1188-source-review.md),
not a reproduced bug or a gold label. The files are a partial selection, and
the local Go syntax-aware parser was unavailable; no complete real capture or
benchmark was produced.

After separately approved source discovery, select approximately three to five
public projects with verifiable permissive source licenses at the chosen commits,
usable issue text and accessible immutable source history. Aim for Python,
TypeScript/JavaScript, Java and Go coverage where supported and genuinely
available. Record repository identity, license file and revision, size, selected
commit and issue provenance. Reject inaccessible, unsuitable, secret-bearing or
unverifiable cases. Check whether issue text and comments can be retained under
their applicable terms; a source-code license alone does not settle issue-text
rights. These are selection criteria, not claims about any particular project.

The pilot target is 20–30 issues across multiple repositories, used to check
mechanics and tune only on development data. The separate long-term held-out
target is at least 100 independently judged issues when feasible; these are
targets rather than fabricated counts. Freeze the collection and tuning policy
before opening the held-out set. Group related issues, duplicate reports,
backports, forks and the same underlying defect into one split. Prefer
repository-level separation if enough independent projects are available, and
disclose any overlap. Exclude issues whose reliable historical context or
pre-fix source state cannot be established; do not silently use later fixes or
comments as query inputs. Record the capture date and any known context edits.

For each included `heldout-v2` query, the stricter preflight requires the
existing repository, pinned 40-character commit, `issue-context-v1`, semantic
query, language, category, label provenance, adjudication status and graded
source ranges, plus:

| Field | Requirement |
| --- | --- |
| `annotation_record.annotators` | One or more distinct pseudonymous IDs; two independent reviewers are the target. |
| `annotation_record.adjudicator` | Pseudonymous reviewer ID; record the adjudication process. |
| `annotation_record.uncertainty` | Nonempty uncertainty description, including unresolved alternatives. |
| `annotation_record.single_annotator_reason` | Required for a single reviewer; otherwise `null`. |
| `annotation_record.exclusion_reason` | `null` for evaluated examples. Keep excluded cases and their reasons in a separate audit manifest. |
| `adjudication_status` | `adjudicated` with at least one positive graded range, or `insufficient-evidence` with no relevance labels. |
| `semantic_identity` | Dataset-level, predeclared vector contract, identical in both splits and all semantic/hybrid captures. |

Independent reviewers should inspect the issue context and pinned source
without seeing CodeRankEmbed, lexical or hybrid rankings. They may use verified
fix history for adjudication while recording its provenance, but must not copy
model results as labels. Compare judgments and adjudicate disagreements; use
disjoint source intervals and retain unjudged candidates as unknown. The
preflight rejects overlapping label intervals to avoid counting one source
range twice. Record disagreement and excluded cases separately. Neither a
reviewer ID nor any automatic check proves independence.

## Git and capture provenance preflight

`app.evaluation.benchmark_provenance` is an opt-in stricter wrapper around the
existing held-out scorer. It accepts separate nonempty development and held-out
`heldout-v2` inputs, matching frozen retrieval configurations and semantic
identities, an inventory array, and paired captures. Included issues need the
annotation record above. Comments must already be in `(created_at, id)` order;
the validator rejects missing, duplicate or out-of-order comments. It rejects
reused query/issue identities and exact normalized context or semantic-query
overlap both within and across splits. Manual review must still detect
paraphrases and shared underlying defects.

Each `git-source-inventory-v1` entry binds a repository, full commit SHA-1,
tenant ID, repository ID, snapshot UUID and bounded chunk list. Each chunk
records its UUID, file UUID, normalized path, language, symbol, inclusive lines, Git blob
SHA-1, whole-file SHA-256, chunk SHA-256 and RepoPilot chunk fingerprint. The
validator reads only local Git objects with network protocols, lazy fetching
and replacement refs disabled. Git subprocess output is bounded to 4,000,000
bytes per command and each command has a 30-second timeout. It recomputes the
commit object ID, file blob
ID, file and line-slice hashes, and production `fingerprint_chunk` value; it
validates paths, supported file-language mappings, ranges, nonoverlapping chunks and citations. It recomputes the
same canonical sorted `[chunk_id, fingerprint]` universe digest used by the
synthetic capture format and requires each capture item to match that inventory.

Each response must carry the inventory's repository, tenant, repository ID,
snapshot, commit and digest. The existing scorer also checks `terms-v2` query
hashes, context digest, configuration, missing-vector policy and paired modes.
The stricter wrapper rejects invalid citations instead of counting them as
ordinary retrieval misses. Its two accepted semantic-query policies are
`issue-title-v1` and `issue-title-body-v1` (title, two newlines, then bounded
body when present). Comments remain preserved context and are not added to the
production lexical baseline. Both splits and every semantic/hybrid capture
must declare the same model, model revision, tokenizer revision,
representation-contract hash, dimensions, normalization, pooling, query prefix
and document prefix. For `local-onnx`, the preflight requires the declared
CodeRankEmbed 768-dimensional CLS/L2 contract and full pinned revisions.

These checks establish **consistency with the supplied local Git objects**, not
GitHub ownership, signed-commit authenticity, live repository authorization,
snapshot membership in a database, independent labeling or trusted capture
execution. They cannot prove that an inventory includes every eligible snapshot
chunk. A future reviewed exporter must establish full snapshot membership,
tenant authorization and capture origin independently. Real inference and
real-data capture are not implemented or authorized by this command.

After separate approval and preparation of all input files, the offline preflight
would be invoked from `apps/api` with explicit local paths:

```sh
.venv/bin/python -B -m app.evaluation.benchmark_provenance \
  --development /path/to/frozen-development.json \
  --heldout /path/to/frozen-heldout.json \
  --inventories /path/to/git-inventories.json \
  --captures /path/to/paired-captures.json \
  --repository OWNER/REPO=/path/to/approved/local-git-repository \
  --output /private/tmp/new-provenance-report.json
```

Repeat `--repository` for different local projects. Input files are capped at
8 MB each; an output inside a bound source repository or an existing output is
rejected. The report is owner-only and does not include source snippets. The
command does not download Git objects, execute repository code, connect to a
database, load a model or create captures.

## Later offline execution and resource proposal

The host reported 16 GiB physical RAM, 12 logical CPUs and approximately
76.2 GB (70.95 GiB) free on `/private/tmp` on 2026-11-06. Free disk and memory
change; check them again before a separately approved run. The earlier
two-input smoke test peaked at 1,473,921,024 bytes RSS, which is not an upper
bound for repeated inference.

For a first pilot, propose no more than three repositories, 5,000 indexed
chunks per repository and the existing per-snapshot source byte limits. Use one
CPU-only model process, one intra-op and one inter-op thread, sequential
execution, batch size one, and the adapter's 512-token maximum. At 768 float32
components, 15,000 vectors contain 46,080,000 bytes (about 43.95 MiB) of raw
vector values; PostgreSQL rows, indexes, WAL, source, working files and copies
are additional and have not been measured. Reserve at least 10 GiB free disk
before staging and check actual corpus, database and WAL growth. These bounds
are a conservative proposal, not a performance estimate or approval.

Give the inference worker read-only access only to the two hash-reverified
model artifacts and approved inputs, a private temporary output directory,
no secrets or application database, no external network and no child processes.
Keep the capture/database process separate, allow it only the disposable
PostgreSQL socket or loopback endpoint, and deny external network egress. The
previous 3 GiB RSS watchdog was sampled, not enforced; use a reviewed hard
process/VM memory boundary where available, plus timeouts and a sampled
watchdog, and stop rather than weaken isolation. Never assume a Docker container
alone is a complete hostile-code sandbox. Do not run repository code.

On interruption, mark the run incomplete and retain sanitized diagnostics;
resume only after rechecking chunk fingerprints, source snapshot, vector
contract and missing-vector coverage, or create a new disposable run. Do not
mix partial vectors into a scored comparison. Keep manifests and reports with
documented access controls and a reviewed retention period; cleanup of
temporary data or containers must follow the operator's separate approval.
Never delete an application volume. The existing kernel-registry crash, exact
upstream export revision and numerical parity remain unresolved.

## Blind partial-source human review — chi #1188

The [human review protocol](chi-1188-human-labeling.md) defines a separately
versioned, pilot-only partial-source inventory and annotation contract. It
binds each reviewer submission to the verified issue context, commit, tree,
source-file hashes and line ranges; it preserves the existing 0–3 rubric and
distinguishes unjudged and abstained cases from reviewed negatives. Two
independent reviewers and a distinct adjudicator are the target. Validator
checks are consistency checks, not authentication of people or independence.

The five retained files are a partial selection and are not a complete Git
inventory. Their review cannot establish full-repository retrieval quality or
be automatically promoted into `heldout-v2`. The case is development data,
not an untouched held-out example. Do not show initial reviewers prior audit
ranges or model rankings. Full-corpus collection, license-notice handling,
offline model inference and benchmarking remain separate approval decisions.
Two private blank review copies have been prepared, with zero human labels;
the [protocol](chi-1188-human-labeling.md) records their path and identities.

The separate [full eligible-corpus approval request](chi-1188-full-corpus-approval-v1.md)
is a proposal only. It does not make the fixture-only capture runner suitable
for real source, authorize collection or replace independent human review.
