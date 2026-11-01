# Sprint 5C1 retrieval audit and evaluation

**Status: current baseline and exploratory candidates measured; production PostgreSQL verification pending.** This audit describes the existing pipeline before any
retrieval strategy changes. The separately authorized 4F source-snapshot creation gate remains
in place. The 5C1 baseline runner reads the previously retained 4F disposable snapshot in a
read-only PostgreSQL session; it creates no jobs and publishes no new source snapshot.

The investigation worker retrieves authorized issue context, removes instruction/credential
lines from its bounded query input, and builds up to three `terms-v1` keyword queries. It
extracts up to two identifier-like terms from the issue and then up to eight title/label terms.
The PostgreSQL search uses English stemming, OR matching, underscored identifier splitting,
path matching and an exact-symbol boost. Each query has a 3-second database statement timeout
and a bounded result count. Results are deduplicated by chunk and merged by best per-query
rank, query order, path, line and chunk ID. The worker rechecks issue and repository access,
snapshot publication and lease ownership before persisting evidence. Evidence reads enforce
tenant/repository/snapshot checks, chunk fingerprints and commit-pinned citation construction.

Known weaknesses to evaluate:

- Mixed-case product names such as `GitHub` are treated as code identifiers and consume one
  of the limited queries. Title stop words can remove domain terms such as `repository`.
- Narrative body text contributes identifier-like tokens but otherwise is not searched. Stack
  traces, filenames and prose symptoms therefore receive little or no direct attention.
- Per-query rank merging can elevate a weak query's first result over stronger results from
  another query. Existing query rank and identifier do not preserve the SQL score.
- The English FTS expression is not covered by the existing simple-language indexes; the
  existing timeout bounds a query but does not establish production-scale performance.
- The pinned benchmark is small, synthetic and incompletely labeled. Unlabeled results are
  not automatically irrelevant; the generic/no-answer cases are not scored as exhaustive
  negatives. Neither retrieval rank nor a valid citation establishes a root cause.

In the saved historical 4F results, the labeled locations for `repository_access`,
`python_chunking`, `snapshot_publication` and `citation_boundaries` were absent from the
entire retained candidate lists, not merely ranked below 10. Reranking those retained lists
alone cannot recover those labels; a candidate-generation change would need fresh evaluation.
This is an observation about the old run, not a measurement of current code.

The historical 4F run used commit `30705da4c044192cab4ac207e253ab8e8a1bd100`, dataset
SHA-256 `416cbf9e46b9399cf78d118f581a882d16cf512da439d352d3af29674c447bf6`, 19 cases,
16 scored cases and 23 labels. Its Recall@1/3/5/10 was 0.375/0.500/0.5625/0.625, MRR
0.51414 and nDCG@10 0.52054. These are **historical** results, not a new current-code baseline.

The subsequent read-only current-code replay `eda70e4b43a14eb6` used that same retained 4F
database and snapshot and matched the historical relevance metrics: Recall@1/3/5/10
**0.375/0.500/0.5625/0.625**, MRR **0.514137**, nDCG@10 **0.520538**, and 12/16 scored
cases with a labeled top-10 hit. It checked **226/226** citations against committed Git
source. Direct-retrieval latency p50/p95 was **54.520/97.672 ms** for these 19 cases; this
is not end-to-end or load latency. The replay's recorded implementation hashes match the
source before any 5C1 ranking changes.

`apps/api/evaluation/run-5c1-baseline.sh` targets only the retained 4F container/database and
snapshot. It checks the container's dedicated 4F label and starts that retained disposable
container if stopped. It verifies the dataset, commit, snapshot, source chunks and read-only database
state; denies write statements, external HTTP transport and non-database Python sockets;
and writes new run-specific JSON/Markdown reports containing metadata rather than source
text or credentials. It calls the existing retrieval function directly, so its latency is not
an API/worker latency and it does not itself test authentication. Existing security tests and
a new disposable PostgreSQL regression run remain necessary.

Three **evaluation-only** candidates are prepared: append a bounded body-derived query,
additionally discard identifier queries that are existing generic stop words, and try body
before title while preserving explicit identifiers first. They reuse the current untrusted-text
filter and the same PostgreSQL retrieval and budgets; vague single-word or generic titles do
not expand into broad body queries. None is selected for production until same-snapshot
measurements and per-case regressions are reviewed. Run the read-only comparisons with
`bash apps/api/evaluation/run-5c1-baseline.sh candidates`.

The host's candidate run `1fdf3b79925eaede` used the same snapshot and labels. Plain body
expansion retained Recall@10 **0.6250**, reduced MRR from **0.5141 to 0.4898**, and moved
the webhook handler from rank 2 to 3. Filtering generic identifiers raised Recall@10 to
**0.6562**, but reduced Recall@1 from **0.3750 to 0.3438** and MRR to **0.4742**. Body-first
also reached **0.6562** Recall@10 while reducing Recall@3 to **0.3750**. None increased the
number of cases with a labeled top-ten result; all three made more queries and returned more
evidence. These measurements use the same incomplete synthetic labels.

An exploratory offline rerank of the already verified plain-body candidate set protected the
first four baseline chunks, then used deterministic symbol/issue token overlap to reorder the
remaining bounded candidates. Run `10c892705cc26aca` produced Recall@1/3/5/10
**0.3750/0.5000/0.5625/0.7188**, MRR **0.5177**, nDCG@10 **0.5469** and 13/16 cases with a
labeled top-ten hit. The snapshot-publication label moved from absent to rank 10; the
incomplete-tree label moved from rank 7 to rank 10. Other unreviewed candidates are not
confirmed irrelevant. This was an offline rerank of previously retrieved, Git-checked
results, not a direct PostgreSQL measurement of the new production implementation. The
plain-body run's direct p50/p95 was **77.391/137.332 ms**, versus baseline
**54.520/97.672 ms**; its latency excludes reranking. The strategy was selected on this same
small dataset and may overfit; a held-out benchmark is still needed.

New investigations now pin `terms-v2`. It preserves the `terms-v1` queries and, when room
and an informative title remain, adds distinct body-derived queries under the existing
untrusted-text filters and query budget. The PostgreSQL search and tenant/snapshot fences are
unchanged. The merge retains up to four original leaders, then orders the other already
bounded candidates by original merged rank minus twice the number of title-token matches and
half the number of body-token matches in the chunk symbol. Token splitting handles underscores
and simple camel-case boundaries; a limited suffix rule is not semantic search. Equal scores
keep their original deterministic order. `terms-v1` remains available for already queued and
historical jobs. Existing evidence exposes query version, query ID and query rank; the new
derived score is not persisted or presented as a proof of relevance.

The exact production strategy still needs a same-snapshot PostgreSQL replay and fresh
disposable PostgreSQL regressions. The latter excludes the separately gated committed-source
snapshot test. No production or live GitHub investigation was created for this evaluation.
