# Retrieval evaluation

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
