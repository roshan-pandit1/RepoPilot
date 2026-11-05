# Sprint 5C1 retrieval audit and evaluation

## Authorized paired replay — 2026-11-02

**SPRINT 5C1 VERIFIED LOCALLY** for this synthetic retrieval benchmark and the scoped
security regressions, with the coverage and latency limitations below.

The user explicitly authorized one new isolated fixture. Run `68ed7b3fd6171439` created
container `repopilot-4f-disposable-68ed7b3fd6171439`, database
`repopilot_4f_disposable_68ed7b3fd6171439`, and snapshot
`95751038-f44e-4715-b4bd-932e446f457b` at commit
`30705da4c044192cab4ac207e253ab8e8a1bd100`. The snapshot contains 104 indexed files,
889 chunks and one screened file. Preflight checked repository `roshan-pandit1/RepoPilot`,
the unchanged dataset hash `416cbf9e46b9399cf78d118f581a882d16cf512da439d352d3af29674c447bf6`,
19 cases/23 labels, and the selected path/blob/size manifest hash
`3cfa6a2f97cfd5a5fddd042f956689b28606228f7fe34272c8b74631def030ee`. The empty dedicated
database preflight and Alembic `0013` passed. The fixture used fake GitHub and mock reports.

The read-only paired run `3d44ea7dbd159dd9` measured both strategies on that snapshot with
identical query/evidence budgets. `terms-v2` used the production versioned query builder and
retrieval/ranking implementation. These are direct retrieval timings including reranking,
excluding query building, citation verification and end-to-end worker/API work; 19 cases in
one sequential run are not a load benchmark.

| Metric | terms-v1 | terms-v2 |
| --- | ---: | ---: |
| Recall@1 / @3 / @5 / @10 | 0.3750 / 0.5000 / 0.5625 / 0.6250 | 0.3750 / 0.5000 / 0.5625 / 0.7188 |
| MRR | 0.5141 | 0.5177 |
| nDCG@10 | 0.5205 | 0.5469 |
| Labeled cases hit at 10 | 12/16 | 13/16 |
| Direct retrieval p50 / p95 | 39.372 / 93.896 ms | 82.396 / 124.066 ms |
| Citations checked against Git | 226/226 | 298/298 |

The snapshot-publication label appeared at rank 10, and a second installation-enrollment
label appeared at rank 10; the incomplete-tree label fell from rank 7 to rank 10. Other
scored cases retained their labeled ranks; the three unscored cases remain unscored. Full
per-case data are in [the comparison](../apps/api/evaluation/5c1-comparison-production-v2-3d44ea7dbd159dd9.md),
with machine-readable baseline, production and comparison artifacts alongside it. Retain
`terms-v2` for its measured recall gain, with the latency and regression tradeoff noted.
The synthetic, incomplete judgments and selection on this same dataset limit generalization;
unlabeled results are not established irrelevant and retrieved candidates are not root causes.

The fixture checked unauthenticated (401), revoked access (404), unpublished snapshot (409)
and other tenant (404) responses. Its 19 mock reports passed schema and provenance checks,
17/17 report references were valid, 19/19 duplicate replays were idempotent and 10/10
grounding probes passed. The [fixture log](../apps/api/evaluation/4f-fixture-68ed7b3fd6171439.log)
and [fixture report](../apps/api/evaluation/4f-issue-report-v1-68ed7b3fd6171439.md) record
the isolated run. No real provider, paid token count, live GitHub or normal application
database was used. The Python network fence is not an operating-system sandbox.

The final separate disposable PostgreSQL regression run `c92ea8e6468ed091` passed **586
tests**, **33/33** adversarial fixture cases, Ruff, Alembic `0013` and `alembic check`.
The pre/post source fingerprints matched and the script exited 0; see the
[regression log](../apps/api/evaluation/5c1-checks-c92ea8e6468ed091.log). This run
excluded the separately gated committed-source test; that fixture was instead executed
under the user's explicit approval as recorded above. No frontend files changed and no
frontend checks were needed. The fixture and regression containers and volumes are retained.
Next recommended sprint: 5C2, after human review; it has not been started.

**Earlier audit status, superseded by the paired replay above:** baseline and exploratory
candidates measured; production PostgreSQL verification pending. This audit describes the existing pipeline before any
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

## Follow-up verification attempt

**SPRINT 5C1 NOT YET VERIFIED.** The retained metrics above are prior host artifacts, not
new results from this follow-up. The production replay now calls the worker's versioned
`terms-v2` query builder directly instead of reaching it through the evaluation-only `body`
alias. A regression test checks that dispatch. The two 5C1 scripts now report a missing
project interpreter explicitly. These changes do not alter application retrieval, historical
jobs, authorization, evidence or benchmark labels. No new ranking candidate was selected:
direct production results are still needed to confirm the exploratory choice.

Files changed in this follow-up: `app/evaluation/issue_retrieval_replay.py`,
`tests/test_issue_retrieval_replay.py`, `evaluation/run-5c1-baseline.sh`,
`evaluation/run-5c1-checks.sh`, this report and `docs/verification.md`.
Python syntax parsing of the two changed Python files, shell syntax checks and
`git diff --check` passed. The new regression test, backend suite, Ruff, PostgreSQL,
security fixture and direct production replay were not run in this follow-up: the root
`.venv/bin/python` points to an unavailable Homebrew Python 3.14 interpreter, and system
Python lacks pytest and SQLAlchemy. A sandbox Docker inspection was denied. An escalated
production replay was attempted, but stopped at the missing interpreter before accessing
Docker. No new paid calls, real embeddings, jobs, source snapshot, or database migration
were performed.

On the Mac host, restore the existing Python 3.14 environment and its locked dependencies,
confirm `.venv/bin/python` is executable, and run from the repository root:

```sh
bash apps/api/evaluation/run-5c1-baseline.sh production
bash apps/api/evaluation/run-5c1-checks.sh
git diff --check
```

The first command requires the retained 4F container and compares directly against the saved
baseline; it does not create a replacement snapshot. The second creates and retains a new
disposable PostgreSQL container and volume, runs regression and adversarial checks and
migrations only there, and excludes the separately approval-gated committed-source test.
Inspect both generated reports and the check log, including per-case changes and exit status,
before deciding whether the selected strategy satisfies the acceptance criteria. The earlier
latency numbers exclude the production reranker and must not be substituted for that replay.
The benchmark remains small, synthetic, incomplete and selected on the same data; a held-out
evaluation is needed for generalization. After successful verification and human review, the
next recommended work is Sprint 5C2; it has not been started.

## Missing fixture recovery and replacement preparation

The host reported the original `repopilot-4f-disposable-4f762b71ae8d9569` container
unavailable. The saved JSON/Markdown contain results and citation metadata, not a database
dump or complete indexed source. They cannot restore its original database. A stopped
container, another Docker context, an independently retained volume or backup could still
permit recovery; inspect those on the host. The 4F runner used an image-managed data volume,
not a named volume that the artifacts identify. Do not attach or modify an unidentified volume.
If no verified original container/volume/backup is found, a fresh fixture is required.

The old fixture runner expected migration `0009` even though it upgraded to the current
head. It is prepared for head `0013`, and keeps both its exact-commit approval gate and
dedicated-empty-database preflight. It now explicitly disables real provider/count settings,
clears provider credentials, disables Git network protocols and fences Python network access
to the dedicated PostgreSQL port during fixture evaluation. These changes and the fresh
fixture path have not yet been executed. The fence is not an OS sandbox. Creation uses a
local Git snapshot and synthetic jobs in a new isolated database; it does not use live GitHub.

After **separate explicit authorization** for this new committed-source fixture, and only
after checking Docker context and ensuring the local image is available, run from the root:

```sh
REPOPILOT_4F_APPROVED_COMMIT=30705da4c044192cab4ac207e253ab8e8a1bd100 bash apps/api/evaluation/run-4f-disposable.sh
```

Record the printed 16-character suffix from the successful **4F fixture** container name
and confirm the command exits zero. The flag is a guard, not authorization. The resulting
report provides the new snapshot identity. Run a paired direct replay on that exact fixture;
enter its suffix at the prompt (not a 5C1 regression container suffix):

```sh
printf 'Enter the successful 4F fixture suffix: '
read -r fixture_suffix
bash apps/api/evaluation/run-5c1-baseline.sh paired "$fixture_suffix"
bash apps/api/evaluation/run-5c1-checks.sh
git diff --check
```

The paired run creates a fresh `terms-v1` baseline and a `terms-v2` measurement on the
same snapshot, checks citations against Git, and compares only those two reports. It refuses
mixed provenance. The production path calls `build_queries_for_version('terms-v2', ...)`
and the production retrieval/rerank function. New database/snapshot IDs, chunk IDs, current
indexer and database revision mean this is a new fixture; historical 4F figures remain
context, not the paired baseline. Inspect generated per-case comparisons and latency before
selecting a strategy. If creation or replay fails, preserve the output and stop rather than
relaxing safeguards. Both Docker containers and volumes are retained.

The host's later regression run `5bd90a0e63d784ee` succeeded with **585 tests**, **33/33**
adversarial cases, Ruff and Alembic `0013`/no drift; see its retained log and
`docs/verification.md`. That success also shows the pgvector image was available by that
run. After the replacement-fixture preparation, host run `6da0508fe05c84e5` passed **586
tests**, **33/33** adversarial cases, Ruff and Alembic `0013`/no drift, with matching source
fingerprints and exit 0. The attempted paired replay used the example suffix and stopped
with `Completed fixture report is missing`; no benchmark was run. A separately authorized
and successfully created 4F fixture is still needed for paired replay.
