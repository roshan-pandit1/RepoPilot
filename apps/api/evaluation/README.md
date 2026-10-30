# Retrieval evaluation

The separately versioned `repopilot-v2-956a4f9.json` pins local commit
`956a4f92983b222ce179891bbde39cb49a2022b2`. It contains 16 positive/ambiguous questions
with 30 reviewed ranges; two negative candidates remain unscored. Run
`python -m app.evaluation.verify_labels evaluation/repopilot-v2-956a4f9.json` from `apps/api`
to verify the committed Git source, symbol ranges and complete single-chunk coverage. No v2
snapshot or retrieval benchmark has been run. This local commit is not assumed to be on GitHub.
The required approval and unimplemented test-runner work are detailed in
`benchmark-v2-disposable-plan.md`.

`repopilot-6349190.json` pins the public repository and commit. Each query has an ID, natural
language question, rationale, and one or more binary relevance labels with a path, symbol, and
inclusive line range. Each label here anchors the definition line: a result counts only if it
has the same path and symbol and fully covers the labeled range. This is incomplete judgment,
not an assertion that all other chunks are irrelevant. It cannot test features introduced after
the pinned commit, including code chunking, indexing-job dispatch, source permalink generation,
and embedding cache reuse. Reindexing a later reviewed commit and adding labels is a separate task.
To recheck the 20 definition anchors and eligible chunk coverage against a local Git checkout,
run `python -m app.evaluation.verify_labels evaluation/repopilot-6349190.json` from `apps/api`.
This checks structural ground truth; it does not replace human review of relevance judgments.

The harness uses the existing same-origin authenticated search API and refuses non-loopback
origins. It makes no provider calls directly, performs no database writes, refuses non-fake
embedding job metadata, and never writes source snippets, cookies or credentials to reports.
It requires the published commit to match the dataset. On a signed-in local development stack,
the preferred `browser-capture.js` runs through the existing signed-in browser without manually
copying session values. From the project root, `pbcopy < apps/api/evaluation/browser-capture.js`,
then paste the inspected script into the DevTools console on `http://localhost:3000`; it downloads
`repopilot-eval-capture.json` with only citation metadata and timings. Process that capture locally:

```sh
cd apps/api
../../.venv/bin/python -m app.evaluation.retrieval --dataset evaluation/repopilot-6349190.json \
  --repository-id 1435878031 --capture ~/Downloads/repopilot-eval-capture.json \
  --output evaluation/results-local
```

Alternatively, an interactive terminal method is available from `apps/api`:

```sh
../../.venv/bin/python -m app.evaluation.retrieval \
  --dataset evaluation/repopilot-6349190.json --repository-id 1435878031 \
  --output evaluation/results-local
```

The program prompts privately for the local `rp_session` and `rp_csrf` browser cookie values.
Use the values from the browser's local cookie storage; do not paste them into chat, shell command
arguments, or reports. The session must belong to an authorized GitHub user. The application
continues to enforce authentication, CSRF, tenant, repository, and snapshot checks. These 60
requests invoke current GitHub authorization checks, and their elapsed wall times include those
checks and network latency. No concurrency or warmup is used; p50 and p95 are nearest-rank sample
percentiles, not service benchmarks. The harness aborts on HTTP errors rather than filling in
missing metrics. Reports are written only on a complete run.

Per-query recall is the fraction of unique labeled targets retrieved at each cutoff, macro-averaged
over questions. Repeated chunks matching the same target receive one gain. MRR uses the first
relevant rank; binary nDCG@10 uses one gain per unique label and a matching ideal ranking.
The report counts missing or structurally incorrect GitHub citations and backend-declared
fallbacks. The repository and snapshot must be public and reviewed before sharing reports;
query labels and repository identifiers are still written to output.

Fake semantic and hybrid metrics are **MECHANICAL TEST ONLY**. They can validate ranking and
regressions, not measure semantic understanding. **REAL SEMANTIC QUALITY NOT YET MEASURED.**

## Proposed paid experiment — not approved or executed

The current pinned snapshot has 169 nonempty chunks, 168 distinct content hashes and 107,162
distinct-content UTF-8 bytes. The 20 questions total 1,000 UTF-8 bytes. As a rough planning
heuristic only, four bytes per token suggests about 26,800 source tokens and 250 query tokens
for one query pass (about 500 for separate semantic and hybrid passes). Actual model tokenization
may differ substantially; a tokenizer is not installed and no provider usage was measured.

For `text-embedding-3-small`, plan 1,536 dimensions (its documented default), 168 unique input
chunks and up to 40 query embeddings. At the documented $0.02 per million input tokens, the
rough estimate is **$0.00055** before retries; three billed attempts for all requests would be
approximately **$0.00164** using the same heuristic. A proposed experiment ceiling is **$1.00**,
subject to user approval and an independently enforced provider/account spending limit. Retries,
timeouts, tokenizer error, provider pricing changes, and repeated evaluation can increase cost;
the present adapter has no hard cost cap and timeout retries may be billed. No actual cost is known.
See [model pricing](https://developers.openai.com/api/docs/models/text-embedding-3-small) and
[embedding dimensions](https://developers.openai.com/api/docs/guides/embeddings).

Cache identity already includes tenant, repository, provider, model, version and dimensions, so
fake and real vectors are kept separate and the query filters the same fields. The current job
and search endpoints intentionally reject real-provider use. Before any paid experiment: review
all source for sensitive data (the existing filter is incomplete), add enforceable token/request
and cost budgets, verify model limits and rate, establish account-side spend limits, separately
verify the real-provider workflow, and obtain explicit user approval. Do not simply set the paid
configuration flag; it is not an authorization or a spending cap.

## Investigation evidence fixture v1

`investigation-evidence-v1.json` is a separate six-case synthetic issue dataset, pinned to
local Git commit `956a4f92983b222ce179891bbde39cb49a2022b2`. `cases` contain `id`, issue
`title`/`body`, `kind` (`positive`, `no_match`, or `no_query`), `labels` and `rationale`.
Positive labels contain a path, symbol and an inclusive line range that must be fully covered
by a single returned chunk. The four labels were reviewed against Git objects and checked
against eligible chunks. Labels are incomplete; unlabeled candidates are not automatically
irrelevant. The two synthetic no-match terms were checked for absence in the pinned Python
source. The malicious case checks an abstention from query construction, not a claim that a
keyword filter is a security boundary.

`tests/test_investigation_evaluation_pg.py` builds a snapshot from that commit in the test
database, drives the existing authenticated job flow with mocked GitHub and a direct worker,
checks result chunks and citation structure against local Git blobs, and records per-case hit
ranks, no-match behavior and direct-worker latency. `run-4c-disposable.sh` writes
`4c-evaluation-local.json` and `.md` only after that test executes. It does not test real
Celery, remote GitHub resolution or semantic/AI quality; six latency samples are descriptive,
not a load benchmark. The older v1/v2 retrieval datasets and reports remain separate.

## Mock investigation report fixture v1

`mock-report-v1.json` is a separate synthetic mechanics fixture. Seven valid model cases and
two deliberately malformed or foreign-reference cases exercise schema and grounding checks;
two additional worker-security scenarios exercise duplicate delivery and revoked access with
mock GitHub. `tests/test_report_evaluation.py` measures local in-process model construction
and validation time and verifies synthetic reference structure. Its output under
`4d-evaluation-local.json` and `.md` is **mock mechanics only**: it is not a measure of root
cause accuracy, real AI behavior, remote GitHub resolution, Celery delivery, or load capacity.

For PostgreSQL verification, `bash apps/api/evaluation/run-4d-disposable.sh` creates a new
separate pgvector container and randomly named database, checks that the database is empty,
runs the full backend suite, Ruff, Alembic upgrade/current/check and the fixture evaluation,
and retains the new container and volume. It does not connect to the application's Compose
database. Do not point destructive fixtures at the normal database. A separately approved
application migration and report task are required before real Redis/Celery verification; the
prepared host/browser helpers do not themselves grant that approval.

## Adversarial mock-report fixture v1

`adversarial-report-v1.json` is a separate synthetic security fixture. Its input cases attack
issue titles, bodies, comments, labels, source excerpts and source metadata; its output cases
attempt role/tool instructions, exfiltration, malformed JSON and forged evidence. The
deterministic evaluator runs the actual mock projection and server-side output validator:

```sh
cd apps/api
../../.venv/bin/python -m app.evaluation.adversarial
```

The generated `4e-security-evaluation.json` and `.md` contain case IDs and outcomes, not the
attack payloads. Separate pytest integration tests cover tenant and snapshot isolation,
revocation, retries, duplicate publication and redaction. These tests use a mock provider and
do not establish real-model prompt-injection resistance. `run-4e-disposable.sh` creates and
checks a new disposable PostgreSQL database; it does not connect to the application database.
The user reported 269 passing PostgreSQL tests, no skips, Ruff passing, Alembic 0009 without
drift and all 33 security cases passing in the dedicated 4E disposable database.

## Issue-to-code and mock-report fixture v1 (checkpoint 4F)

`issue-report-v1.json` contains 19 synthetic scenarios pinned to commit
`30705da4c044192cab4ac207e253ab8e8a1bd100` and its recorded Git tree. Sixteen cases have
23 reviewed source-location labels; two are ambiguous, and three cases (insufficient detail,
an unreviewed negative candidate, and malicious text) are excluded from relevance scoring.
`issue-report-v1-provenance.md` lists the verified symbol, inclusive label and eligible chunk
range for each label. Git verification does not create a database snapshot or assign chunk IDs.
Labels are incomplete, and the scenarios do not assert a verified bug or root cause.

From `apps/api`, `../../.venv/bin/python -m app.evaluation.issue_report` verifies the labels
against local Git blobs, source selection and the existing Python chunker. This read-only
check needs no PostgreSQL. `bash apps/api/evaluation/run-4f-checks.sh` creates a new empty
disposable pgvector database, runs the backend suite, security fixtures, Ruff and Alembic
checks, and retains the new container and volume. It excludes the existing 4C test that
publishes a committed-Git source snapshot; no application database is used.

Creating a new committed-source snapshot requires separate user approval. Once approved,
`run-4f-disposable.sh` checks the exact commit approval flag, creates a fresh isolated
database, applies migrations there, and uses the existing indexing worker, authorized test
client, fake GitHub and direct investigation/report workers. It creates one real database
snapshot and generated chunk IDs only inside that database. It records a unique JSON/Markdown
run pair without overwriting earlier runs. The explicit flag is a safety guard, not permission.

The scorer reuses the v1/v2 binary relevance calculation, with macro recall@1/3/5/10, MRR and
nDCG@10 over scored cases only. It records per-case results and per-query hashes and retained
evidence after deduplication, citation checks against local Git, worker latency and evidence
budgets. An unlabeled result is not necessarily irrelevant. Reports are checked mechanically
against persisted evidence and replayed; malformed, foreign and contradictory-reference
probes exercise the server validator. The snapshot is the committed source under test; the
evaluator is the current working tree, whose relevant implementation hashes are recorded in
each run, including any uncommitted 4E hardening. Results from different commits, datasets or
snapshot IDs must be reported separately.

`issue-report-v1-rubric.md` describes a future independent human review of substantive claims;
it is not a diagnostic-quality measurement. No paid provider, real model, real GitHub issue,
live Celery workflow or remote citation-resolution check is involved in the disposable 4F
runner. The separately approved host run is recorded in
`4f-issue-report-v1-4f762b71ae8d9569.json` and `.md`; see `docs/verification.md` for the
measured metrics and the subsequent fixture-logging safeguard. Keep this run separate from
v1/v2 and 4C/4D results.
