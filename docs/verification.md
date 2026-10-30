# Verification record

## Sprint 3 Phase C3 — final local verification

**PHASE C3 VERIFIED LOCALLY**, with the limits in the evaluation record below. The matched
host log `/tmp/repopilot-v2-20261029-160824.log` and `apps/api/evaluation/v2-local.json`
identify the same dedicated disposable database `repopilot_c3_disposable_a47f7b87227215f9`
and published snapshot `2207c4a6-2717-4c81-ab3c-eb777e97d557`. The host log records an
empty dedicated database, 128 PostgreSQL tests passing, Ruff passing, migration 0006 at head
with no pending operations, 30 validated labels and runner completion. The user reported exit
status 0; the saved log itself does not separately record a shell exit code. The snapshot has
77 files, 556 chunks and one screened file. The existing v1 regression and synthetic scale
reports remain separate. The checkpoint commit was local-only at evaluation time; GitHub
citation availability was not verified by that evaluation. This local result is not a
production-readiness claim.

The following preparation records describe earlier points in time and are superseded where
they report a provisional verdict, uncommitted source, or an unexecuted v2 evaluation.

## Sprint 3 Phase C3 — committed-source v2 preparation

**NOT YET VERIFIED.** The user created local-only commit
`956a4f92983b222ce179891bbde39cb49a2022b2`. Read-only Git comparison confirmed that its 53
changed files exactly match the approved checkpoint manifest with `.env.example` excluded and
`apps/api/evaluation/browser-capture.js` included. Its parent is
`63491908290e6874dbaaf2b15c2a96473aad1324`. No `apps/web/` path is in the commit; the seven
frontend Git status entries match the pre-commit status record. The earlier record did not
capture content hashes, so this is a status comparison, not a byte-for-byte proof.

The separately versioned working-tree dataset `apps/api/evaluation/repopilot-v2-956a4f9.json`
pins the local commit and contains 16 positive/ambiguous questions with 30 inclusive evidence
ranges. The two ambiguous questions have multiple relevant labels; two negative candidates are
kept unscored pending exhaustive review and a suitable no-answer metric. The 30 labels were
checked against actual committed Git source, symbol/decorator ranges, source-selection policy,
and single-chunk coverage. The original 20 labels were also revalidated. This validates the
labels structurally; no v2 retrieval scores, local source snapshot or live GitHub permalink are
claimed. The Git commit's remote availability is unknown.

The user approved and created the local checkpoint; no push, deploy or live reindex was performed.
The committed 53 files passed a limited recognizable credential-pattern scan, which is not
comprehensive; the private-key marker in a source-client test is synthetic fixture text. The
working-tree label verifier was extended to validate full interior ranges and decorators. A
disposable evaluation plan, explicitly not yet executable until its Git source adapter and test
runner are implemented, is in `apps/api/evaluation/benchmark-v2-disposable-plan.md`. Explicit
approval is required before creating the test snapshot, and separate approval is required for
any future push, live reindex or paid API use.

Local backend tests after these changes: **118 passed, 9 PostgreSQL-only skipped**, and Ruff
passed. `git diff --check` passed. No PostgreSQL test or database mutation was performed in this
preparation; the prior user-reported disposable PostgreSQL run passed 125 tests.

## Sprint 3 Phase C3 — v2 provenance preparation

**NOT YET VERIFIED.** Read-only Git inspection found HEAD
`63491908290e6874dbaaf2b15c2a96473aad1324`; the newer indexing and embedding modules remain
uncommitted. The 18-question v2 proposal has 14 concrete implementation questions, two ambiguous
questions and two unverified negative candidates. Of the concrete questions, two have all listed
function bodies unchanged from HEAD, eleven depend on new or changed implementations, and one
mixes committed and uncommitted functions. The per-question ranges, exact proposed backend source
checkpoint, exclusions and disposable local-evaluation design are recorded in
`apps/api/evaluation/benchmark-v2-provenance.md`. No v2 score or GitHub citation is claimed.

This preparation reran the existing pinned-label verification (**20 matches**), local backend
tests (**116 passed, 9 PostgreSQL-only skipped**), Ruff and `git diff --check`. No PostgreSQL test
was executed in this preparation; the earlier host result of 125 passes is documented below. A
limited pattern scan found one test fixture containing a private-key marker string, not key
material; it is not comprehensive secret detection. No stage, commit, push, database mutation,
deployment, reindex or paid API call was performed.

## Sprint 3 Phase C3 — scale and retrieval coverage

**NOT YET VERIFIED.** The user ran the generated-corpus PostgreSQL workload in a dedicated
disposable database. It creates only temporary fixture tables and compares existing-style
indexes to candidate English-expression GIN indexes. For 1,000 / 10,000 / 50,000 generated
chunks (800 / 8,000 / 40,000 in the target tenant and snapshot), the current-index p50/p95
were 5.881/11.066 ms, 55.416/112.333 ms, and 280.509/554.890 ms respectively, with 36 samples
per condition and no timeouts. Candidate English GIN p50/p95 were 6.136/10.877,
55.654/112.459, and 288.401/559.828 ms. All plans used sequential scans, a hash join and top-N
sort; the candidate indexes were not selected. The candidate indexes increased total index size;
no migration or new application index was introduced. Detailed query plans, buffer counts,
index sizes, build times, correctness checks and caveats are in `apps/api/evaluation/c3-scale.md`
and `.json`. CPU and total memory were not measured; p99 is not reported from 36 samples.
These are generated temporary tables with simplified IDs/projections, not production or
authenticated API timings. The largest case exceeds current indexing limits.

The first host workload attempt failed before measurements because psycopg interpreted a literal
modulo operator as a placeholder; the fixture generator was fixed and the second run succeeded.
The original C1 benchmark remains unchanged. The newer modules do not exist in any available
committed revision; `apps/api/evaluation/benchmark-v2-proposal.md` is explicitly unpinned and
must not be scored as ground truth. A suitable committed revision and any new source snapshot
still require separate review and approval. The paid-provider reservation design remains
unimplemented, and paid background generation is disabled; no paid calls were made.

Local backend: **116 passed, 9 PostgreSQL-only skipped**, Ruff and `git diff --check` passed.
The user then reported **125 passed**, Alembic **0006** with no drift, and Ruff passed against a
fresh disposable PostgreSQL database, including the CamelCase and bounded-result test. Explicit
cross-model and cross-dimension vector assertions were added afterward; the user reran the full
suite and reported **125 passed**, Alembic **0006**, no drift, and Ruff passed. No C2 search SQL or app indexes were changed, and no application database or
source snapshot was modified during the generated workload.

The user reran the original benchmark through the authenticated API against the same commit,
model configuration, questions and result limit. Keyword Recall@1/3/5/10 remained
.25/.60/.60/.80, MRR .434 and nDCG@10 .521, with no labeled-rank changes for any question.
There were zero keyword fallbacks and zero structurally invalid citations among 198 returned
results. Keyword p50/p95 were 1150.9/1426.7 ms compared with 1301.6/1789.3 ms in the C2 run;
these samples include network and authorization and do not establish a performance improvement.
Fake semantic and hybrid labeled ranks were also unchanged; these are mechanical checks only.
Detailed per-query results are in `apps/api/evaluation/c3-comparison.md` and `.json`.
After adding the comparison-report safeguard, the local focused tests passed 11 tests and Ruff.

## Sprint 3 Phase C2 — lexical retrieval and session security

**PASS locally, with performance and coverage limitations.** The C1 benchmark and labels remain unchanged. A host-run,
read-only PostgreSQL diagnostic on the same 278-chunk published snapshot compared the original
simple-language AND query with English-language OR variants. The original produced zero candidates
for every question even across this repository's snapshot history, so snapshot filtering did not
discard any matches for those queries. English OR and English OR plus an exact-symbol boost each
had diagnostic Recall@1/3/5/10 of .25/.60/.60/.80, MRR .434 and binary nDCG@10 .521. This
operator-level diagnostic is not the authenticated after-change API benchmark. Per-question
candidate counts and ranks are in `apps/api/evaluation/c2-diagnostic.md` and `.json`.

The candidate implementation uses English stemming/stop words and splits underscores, safely
constructs an OR tsquery from PostgreSQL-quoted parsed lexemes, adds an exact-symbol boost, and
uses a stable ID tie-breaker. It retains bound parameters, authorization, tenant and published
snapshot predicates, and the three-second SQL timeout. Existing simple-language FTS expression
indexes do not directly cover the new English expressions; this version can scan the bounded
snapshot, and performance on large repositories remains unverified. No migration or reindex has
been performed. The user reported **122 passed**, Alembic **0006** with no drift, and Ruff passed
on a new disposable PostgreSQL database. The authenticated after-change run on the same commit,
questions and limit returned 198 keyword results, zero structural citation failures, and no
fallbacks. Recall@1/3/5/10 was .25/.60/.60/.80; MRR .434 and binary nDCG@10 .521. Four queries
had no labeled result in the top ten; all 20 returned at least one result. Before the change,
all keyword values were zero and all 20 returned zero results. Wall-clock p50/p95 changed from
1206.9/1774.4 ms to 1301.6/1789.3 ms; these include GitHub authorization and network time and
are not a load benchmark. Full per-query comparisons and metadata are in
`apps/api/evaluation/c2-comparison.md` and `.json`. Fake-vector semantic/hybrid scores remain
mechanical checks, not real semantic quality. Structural citation checks do not open every link.

Security: logout revokes the server-side session and clears its stored encrypted GitHub token;
the authorization dependency rejects revoked and expired rows. The user reported a read-only
account count of **1 active, 4 revoked, 3 expired**, and an unauthenticated request returned
401. A later host count showed **1 active, 5 revoked, 3 expired**. These counts do not identify
either exposed session. The user then approved an account-wide active-session revocation and
ran the documented host SQL: one user matched, the update revoked zero rows, and the following
account count was **0 active, 6 revoked, 3 expired**. Therefore no unexpired, non-revoked
RepoPilot session remained for that account at the time; the update did not itself revoke the
remaining session, which had already become inactive. A subsequent new sign-in was used for
the evaluation. The procedure and its impact are in
`apps/api/evaluation/session-revocation.md`.
The regression suite now verifies a revoked fixture session cannot authenticate when replayed.

The real-provider budget-control proposal is in `apps/api/evaluation/paid-budget-design.md`.
It is a design only: the current adapter lacks durable hard-budget enforcement and paid
generation remains disabled. No paid API calls have been made.

## Sprint 3 Phase C1 — retrieval evaluation

**VERIFIED LOCALLY for the pinned-snapshot evaluation baseline.** The 20-question benchmark in `apps/api/evaluation/repopilot-6349190.json`
is anchored to real symbols at commit `63491908290e6874dbaaf2b15c2a96473aad1324` using Git
objects and Python AST line numbers. The pinned commit predates indexing, source chunking,
permalink generation and embedding cache modules, which therefore lack benchmark labels. Labels
are binary single-line definition anchors and do not exhaustively identify all relevant code.

Reconstructing all eligible Python files from the pinned Git object with the existing chunker
produced 40 files, 278 chunks, 109 whitespace-only gaps, 169 nonempty chunks and 168 distinct
nonempty content hashes. All reconstructed chunks matched their inclusive source line slices.
The user supplied read-only per-file PostgreSQL counts consistent with the reconstruction. The
per-file record is `apps/api/evaluation/chunk-audit.md`. Whitespace gaps contain no searchable
source and are excluded from embeddings; source chunking intentionally preserves all lines.

The evaluation harness uses only the existing authorized search API, checks the snapshot commit,
calculates macro Recall@1/3/5/10, MRR, binary nDCG@10, fallbacks, citation validity and sample
latencies, and writes no snippets or credentials to reports. Fake semantic/hybrid results are
mechanical only; real semantic quality is not measured. An authenticated browser run completed
against the pinned snapshot: all 20 natural-language keyword queries returned zero results,
so Recall@1/3/5/10, MRR and nDCG@10 were zero for this incomplete label set. The semantic and
hybrid requests all fell back to keyword because the status reported embeddings not ready; those
requests cannot establish vector or hybrid behavior. All modes returned zero citations, so the
zero invalid-citation count does not validate any citations. The exact per-query output and
wall-clock latency samples are in `apps/api/evaluation/results-local.md` and `.json`. PostgreSQL
simple-language `plainto_tsquery` requires query terms together, which is a likely explanation
for poor natural-language retrieval; no causal experiment was run. Latest local tests: **113 passed, 7 PostgreSQL-only skipped**;
Ruff passed. The user reported **119 passed**, Alembic revision 0006 with no drift, and Ruff
passing on a new disposable PostgreSQL database. A later focused local test added report,
commit-mismatch and browser-capture assertions, and all seven evaluation tests passed. No paid request was made. An experiment estimate
and its unenforced proposed spend ceiling are documented in `apps/api/evaluation/README.md`;
real-provider job support and enforceable budgets remain prerequisites to any paid experiment.

After the user enabled the fake provider and generated embeddings for the current published
snapshot, a second authenticated browser run completed all 60 searches without fallback.
`apps/api/evaluation/results-fake.md` and `.json` contain its measured results. Keyword had
zero returned results and Recall@1/3/5/10, MRR and nDCG@10 of zero on these 20 questions.
Fake semantic and hybrid each returned 200 results; 3 of 20 queries matched the incomplete
definition-anchor labels within ten results. Both had Recall@1/3/5/10 of .05/.05/.10/.15,
MRR .070 and nDCG@10 .088; these are **MECHANICAL TEST ONLY**, not real semantic quality.
The 400 returned citations passed structural checks against the pinned commit and line fragments.
Wall-clock p50/p95 in milliseconds were 1206.9/1774.4 keyword, 1223.0/1595.5 semantic,
and 1213.5/1796.1 hybrid. These include live GitHub authorization and proxy/network time,
without warmup or repeated sampling; they are not a production latency benchmark. Real semantic
quality has not been measured.

A later authenticated repeat capture produced the same per-query labeled ranks and aggregate
retrieval metrics in each mode, with zero fallbacks. Repeat p50/p95 latencies were 1213.2/1300.8
ms keyword, 1236.3/1848.9 ms fake semantic, and 1152.7/1295.8 ms fake hybrid. The repeat is
recorded in `apps/api/evaluation/results-repeat.md` and `.json`; equal labeled ranks do not
prove every returned ranking was identical.

## Sprint 3 Phase B1 — Checkpoint D

**VERIFIED LOCALLY with the deterministic fake provider.** Dashboard mode selection, snapshot-aware embedding readiness, fake-job
submission, bounded active-job polling, and explicit keyword fallback are implemented. The proxy
forwards the existing search mode and embedding routes with session and CSRF headers. Search
requests are fenced against stale responses; source remains escaped and citation URLs are checked.
The dashboard labels deterministic fake vectors as a test mechanism, not semantic quality.
The worker and dispatcher emit correlated embedding task receipt, finish and dispatch events;
task finish alone does not imply success, so persisted job state must also be checked.

Local frontend typecheck, ESLint, **20 tests**, and production build passed. These include
server-rendered and mocked-proxy checks, not browser interaction. Local backend full suite:
**106 passed, 7 PostgreSQL-only skipped**; Ruff passed. A full-suite fixture discovery error
was corrected by importing the shared authentication fixture directly. The user subsequently
built the API, worker, dispatcher and web images and ran the full suite against a fresh
disposable PostgreSQL database: **113 passed**, revision **0006**, no Alembic drift, and Ruff
passed. No paid call was made.

Migration 0005 installs pgvector if necessary, adds an ownership unique constraint and embedding
tables; 0006 adds embedding jobs. Previous disposable PostgreSQL upgrades reached 0006 with no
drift. Read-only host inspection reported the application database at **0006** with pgvector
**0.8.7** installed; no application migration is needed to reach the current head. Any future
application migration requires explicit approval and a protected backup. Migration
downgrade drops embedding data; it is not a lossless rollback. `make dev` / normal Compose startup
can run the migration service automatically and must not be used against the application database
before approval. Rebuilding images alone does not migrate data; API, dispatcher, worker and web
need updated images for the integrated flow.

The user restarted the rebuilt services with the fake provider and submitted a job through the
dashboard for the existing published `roshan-pandit1/RepoPilot` snapshot. Host logs show
dispatcher publication and Celery task receipt and return for job
`07919f84-3bfa-424e-976b-f1f2cb1abf74`. Read-only PostgreSQL queries show the job completed
in one attempt against commit `63491908290e6874dbaaf2b15c2a96473aad1324`, model
`fake/deterministic-hash` version 1, dimension 32: 169 embedded chunks and 168 distinct cache
entries. The snapshot contains 278 chunks, of which 109 are whitespace-only and excluded by the
worker; the 169 nonempty chunks match the job count. This verifies live fake-vector generation,
not semantic relevance. User-provided browser screenshots show `process_sync` searched on the
existing repository in keyword (7 results), semantic (10), and hybrid (10) modes, each displaying
its effective mode and retrieval method. Subsequent screenshots show the `process_sync` source
opened on GitHub at the expected commit and highlighted through line 147, with line 148 outside
the highlight. An unauthenticated hybrid search returned HTTP 401. A subsequent read-only query
showed two more completed jobs, `2c2a7f2c-5bec-4474-b3cd-49aa6a43e267` and
`11376cc5-c6f8-4e3f-94d5-13040061fdb9`, each reporting 169 of 169 chunks, while the current
published snapshot still had 169 embedding links and 168 cache entries. The dashboard also
showed a newer source indexing timestamp; this confirms repeated processing without increased
current-snapshot counts but does not prove that the source snapshot itself was unchanged.
The user subsequently supplied a dashboard screenshot for `roshan-pandit1/Mini-Css-Project`:
semantic search reported `embeddings_not_ready`, explicitly displayed keyword fallback, and
returned no matches for the snapshot with zero Python chunks. This is a functional integration
check, not a relevance benchmark or a production-readiness assessment.

Read-only application inspection (does not start the migration service):

```sh
docker compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
SELECT version_num FROM alembic_version;
SELECT name, default_version, installed_version FROM pg_available_extensions WHERE name = 'vector';
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
SQL
```

Before any approved application migration, create and securely retain a database backup, for
example `umask 077` followed by `docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > repopilot-before-b1.dump`.
Verify that backup according to the operator's restore procedure in a separate database.
After explicit approval, `docker compose run --rm --no-deps api alembic upgrade head` applies
the migrations using the built API image. Do not use downgrade as a lossless rollback: it drops
embedding tables and their contents. Restore testing and downtime coordination are operator
responsibilities; do not overwrite the application database during verification.

## Sprint 3 Phase B1 — Checkpoint A

**IN PROGRESS; NOT VERIFIED END TO END.** Added a deterministic fake provider, an explicitly
opt-in OpenAI provider adapter, additive migration `0005`, and tenant/repository-scoped vector
cache and chunk links. The fake is for mechanical testing only. No real embedding request or
paid API call has been made. The OpenAI adapter requires `allow_paid=True` in addition to a key;
it is not wired into background jobs or configuration yet.

The user built the API image and ran `alembic upgrade head`, `alembic current`, `alembic check`
and `pytest -q -ra tests/test_embeddings.py` on a new disposable PostgreSQL database: revision
`0005`, no drift, **3 passed**. A fourth provider retry/accounting test was added afterward and
passed locally using `httpx.MockTransport`; it made no network request. SQLite migration was
also tested; SQLite JSON storage is not evidence of pgvector similarity behavior. Worker,
semantic search, hybrid search and dashboard integration remain unfinished.

## Sprint 3 Phase B1 — Checkpoints B and C

**IN PROGRESS; NOT VERIFIED END TO END.** The fake-only durable embedding job, dispatcher,
batch persistence and exact pgvector query are implemented. A first host PostgreSQL run
exposed a scalar-distance decoding failure; the operator return type was corrected. The next
host run on a new disposable PostgreSQL database reported revision `0006`, no Alembic drift,
and **8 passed**, including exact cosine search with fake vectors. Additional revocation,
tenant and search-mode cases were added after that host build and subsequently passed in the
disposable PostgreSQL run described below.

The search API now accepts keyword, semantic and hybrid modes; reciprocal rank fusion combines
ranked lists, and missing compatible embeddings explicitly fall back to keyword search. Local
focused tests report **12 passed, 2 PostgreSQL-only skipped**. The later host PostgreSQL run
included the added hybrid and fallback tests and passed.
The dashboard is not yet integrated. No real-provider request or paid service was used;
paid background generation remains disabled pending explicit approval and budget controls.

### Checkpoint C PostgreSQL fixture failure

**PASS on a disposable PostgreSQL database.** The supplied `/tmp/repopilot-b1c-error.log` shows PostgreSQL
`UndefinedObject: type "vector" does not exist` during `CREATE TABLE embedding_cache`,
before the search test executes. The fixture calls ORM `create_all` directly, whereas
migration 0005 installs the `vector` extension; creating an empty disposable database
alone does not install it. The test fixture now installs the extension in its PostgreSQL
test database before creating tables. This does not modify application startup or migrations.
The database used in the failed run has not been inspected independently; its failure shows
the vector type was unavailable to that connection at setup time.

After the fixture change, local SQLite-backed embedding, ranking and code-workflow tests
reported **21 passed, 4 PostgreSQL-only skipped**; Ruff and `git diff --check` passed.
The user then ran the formerly failing test on a fresh disposable PostgreSQL database:
**1 passed**. Migration reached **0006 (head)** with no Alembic drift; inspection reported
pgvector **0.8.7** and the `embedding_cache`, `chunk_embeddings`, and `embedding_jobs` tables.
The related embedding, ranking and code-workflow suite reported **25 passed**, including
PostgreSQL vector, hybrid, keyword fallback, authorization and concurrency tests. These use
fake providers and do not demonstrate a live Celery embedding pipeline or semantic relevance.
The fixture's table creation and teardown were confined to the disposable test database.

## Sprint 3 Phase A4 — dashboard and lifecycle events

**VERIFIED LOCALLY with follow-up limitations.** The dashboard now renders repository indexing status and a
same-origin search interface, using the backend's published snapshot, counts, timestamp and
commit-pinned citations. Polling is limited to pending/running jobs and is stopped on cleanup.
Code is rendered as React text, with lightweight highlighting; citation links are restricted to
the expected GitHub repository, commit, path and line fragment. The user explicitly authorized
a live reindex for this verification.

| Check | Status | Evidence |
| --- | --- | --- |
| Frontend | PASS with limitation | `npm run typecheck`, `npm run lint`, `npm test` and `npm run build` passed locally; 17 tests include status rendering, error messaging, escaping and citation validation. Tests use server rendering or mocked fetches, not interactive browser transitions. |
| Backend | PASS with limitation | `pytest -q -ra`: 94 passed, five PostgreSQL-only skips; Ruff passed. Lifecycle tests verify job/snapshot correlation, JSON fields and severity, and check that a fixture token and source text do not appear in emitted events. |
| Host PostgreSQL | PASS with limitation | The user ran the backend suite against a disposable PostgreSQL database: **97 passed**. Two additional logging tests were added after that host build and passed locally; rerunning the latest image on PostgreSQL remains pending. |
| Browser and live logs for A4 | PASS with limitation | The user authorized a reindex, reported the new Code search UI displayed `process_sync` and its View source link opened the highlighted GitHub lines. Host logs show the RepoPilot job was queued, dispatched, claimed, collected, published and completed. A later host screenshot confirmed the corrected panel placement and readable search button, with RepoPilot shown as Indexed at 40 files, 278 chunks, the expected commit and a timestamp. Intermediate on-screen job states were not separately reported. The screenshot still showed the earlier five-second refresh setting; the later thirty-second setting needs a host rebuild. |

The status endpoint adds the published snapshot's `indexed_at` field. JSON lifecycle events
include correlation IDs but no source, tokens, or exception bodies. Existing historical jobs do
not gain retroactive logs. Host-provided logs showed two jobs being queued, dispatched, claimed,
collecting source and publishing snapshots; the RepoPilot job and UI search were confirmed as
described below. Those logs showed Celery wrapping INFO JSON events as WARNING;
worker stdout redirection was disabled afterward, but that adjustment has not been verified on
the host. Real-account dashboard refresh was reduced from five to thirty seconds after host logs
showed repeated GitHub reads; each backend read still revalidates access. Credential filtering
remains pattern-based and incomplete.

Host SQL correlated job `b97b9c35-0fcb-419d-ab01-664842d06830` with
`roshan-pandit1/RepoPilot`: status `completed`, commit
`63491908290e6874dbaaf2b15c2a96473aad1324`, 40 files, 278 chunks and zero skips. Its
job/task ID appears in API queued, dispatcher dispatched and worker claimed, collection,
publication and completion events; worker publication reported snapshot
`c9880616-13e2-40cf-8fd1-a720959091b6`. A separate completed job was for
`Mini-Css-Project` and contained zero indexed Python files. The user confirmed the new UI
search and View source link worked. The host did not separately report each intermediate
on-screen status; the worker lifecycle sequence establishes processing and completion.

## Sprint 3 Phase A3 closure checks

**Status: VERIFIED LOCALLY, with the observability limitations below.** The most recent local run of
`apps/api/.venv/bin/python -m pytest -q -ra` reported 91 passed and five PostgreSQL-only
skips; `.venv/bin/ruff check . --no-cache` and `git diff --check` passed. The earlier host
run reported 96 passing tests using disposable PostgreSQL, including full-text and
concurrency tests; those tests use injected GitHub clients and direct worker calls.

The live job and published snapshot both record commit
`63491908290e6874dbaaf2b15c2a96473aad1324`, 40 files and 278 chunks, with one dispatch
attempt. A live search returned `process_sync` at `apps/api/app/workers/tasks.py` lines
74–147; local `git show` confirms the source boundaries at that commit. The user printed the
actual API-generated URL:
`https://github.com/roshan-pandit1/RepoPilot/blob/63491908290e6874dbaaf2b15c2a96473aad1324/apps/api/app/workers/tasks.py#L74-L147`.
The owner, repository, commit, path, and line fragment match. The user confirmed that GitHub
opened the link and highlighted lines 74–147. Web retrieval in this sandbox returned a cache
miss, so the visual result is host-reported. The schema links snapshots to
repositories and commits, not directly to job IDs; correlation is based on repository,
commit and timestamps, not a job-to-snapshot foreign key.

The host ran `docker compose ps`, `docker compose logs --tail=300 worker dispatcher` and
read-only PostgreSQL queries. The worker and dispatcher were running; the worker startup log
listed the Redis broker and Celery queue. No error was visible in the supplied logs, but the
worker is configured at WARNING level, task events were off, and neither component emitted
per-task success messages. Thus the logs do not identify the indexing job. No reindex was
requested. PostgreSQL independently returned one completed job with one recorded dispatch
attempt, and exactly one published snapshot for the repository/commit with 40 actual files,
278 actual chunks, and the `process_sync` chunk at lines 74–147. The snapshot has no direct
job foreign key; the job/snapshot match is an inference from repository and commit. The
authenticated 202 request, one dispatch attempt, running Redis-connected Celery worker,
completed job, matching published snapshot and real search together support local processing;
they are not a per-task log trace and do not establish production readiness.

## Sprint 3 Phase A3 regression follow-up

| Check | Status | Evidence |
| --- | --- | --- |
| Production settings test | PASS | Reproduced failure with OAuth enabled and an HTTP localhost callback inherited from the environment. The positive test now supplies complete HTTPS OAuth settings; the existing negative test still rejects production HTTP. The four configuration tests passed with OAuth enabled in the environment. |
| Backend regression suite | PASS with limitation | `pytest -q -ra`: 90 passed and four PostgreSQL-only tests skipped, including the new concurrent indexing request test. Ruff passed. The configuration tests also passed with OAuth enabled in the environment. |
| Frontend checks | PASS with limitation | Typecheck, lint, 14 tests and production build passed both locally and on the host. Two proxy tests use a mocked upstream; no browser-based live indexing call has yet been run. The user's earlier npm commands failed because they were run from the repository root; rerunning from `apps/web` passed. |
| Live smoke | PASS with limitation | Host traceback confirmed demo authentication was disabled. A user-run isolated development demo stack built and reported `PASS: auth rejection, signature rejection, durable delivery, deduplication, real worker, DB, API, web data`. It used separate PostgreSQL and Redis volumes; the real-user stack remained separate. This validates the Sprint 1 path, not Sprint 3 indexing. |
| PostgreSQL migration and tests | PASS with limitation | Host rebuilt Compose, `alembic current` reported `0004 (head)`, and `alembic check` reported no new upgrade operations. A user-supplied dedicated disposable PostgreSQL test database ran `pytest -q -ra`: **96 passed**. This includes PostgreSQL row-lock, concurrent indexing-request and full-text citation tests, but uses injected GitHub clients and direct worker calls. |
| Real GitHub indexing and search | PASS | A signed-in host browser received HTTP 202 for job `6effc48a-e4ea-4608-a0c0-eef6da698900`; status reported completed. Host PostgreSQL showed one dispatch attempt, commit `63491908290e6874dbaaf2b15c2a96473aad1324`, 40 files, 278 chunks, zero skips, and a published snapshot with matching stored counts. An authenticated browser search for `process_sync` returned the function at `apps/api/app/workers/tasks.py` lines 74–147. `git show` confirmed the lines, the user printed the matching actual API URL, and confirmed GitHub highlighted those lines. |
| Real Celery evidence | PASS with observability limitation | The worker logs show a running Redis-connected Celery worker but no task receipt or completion for this job at WARNING level. A recorded dispatch attempt, completed database job, matching snapshot, and real search support the local chain; no per-task log trace was observed. The isolated Sprint 1 smoke independently exercised real Celery for webhook ingestion. |
| Live unauthenticated access | PASS | Host `curl` to `/v1/repositories/1/index-status` without credentials returned 401. This does not independently demonstrate cross-tenant isolation; PostgreSQL tests cover that with injected GitHub responses. |

Host read-only SQL confirmed both GIN indexes and both partial unique indexes exist in the
application database, which currently contains 6 issues, 3 repositories and 2 users. These
are current counts, not a complete before/after comparison of all stored data.

The web app now includes a narrow same-origin proxy for index, index status and search so a
signed-in browser can exercise the backend without copying session credentials into a terminal.
The proxy forwards the session and CSRF headers and leaves authorization to the existing API.

Host follow-up: the application database reached revision `0004`, but `alembic check`
failed because the two PostgreSQL FTS indexes created in migration `0003` were absent from
ORM metadata. They are now declared as PostgreSQL-only expression indexes. A local SQLite
upgrade/check reaches `0004` with no detected drift; SQLite emits two warnings because it
cannot reflect expression indexes. The corrected PostgreSQL check and suite await a host run.
The first corrected host check still reported a mismatch for the chunk index: PostgreSQL
reflects extra grouping around concatenation. The metadata now matches that grouping, and a
local regression test compares it with the actual PostgreSQL-reflected expression. A live
PostgreSQL recheck still reported a remove/add operation for that index; the test did not
reproduce SQLAlchemy's full reflection/compilation behavior. Read-only diagnostics of the
reflected and metadata expressions showed that SQLAlchemy's reflected form had one fewer
pair of grouping parentheses than `pg_indexes` displayed. Metadata now matches the reflected
form, with a normalization regression test. The subsequent host check passed without a new
migration, confirming the existing indexes were retained.

Indexing now claims a fenced lease, fetches GitHub content outside database transactions, and
revalidates session, tenant, repository, installation, lease and branch commit before atomic
publication. SQLite tests cover stale leases, revocation during fetch, changed commits and expired
lease recovery. Real PostgreSQL concurrency, broker recovery and provider authorization changes
remain unverified. A separate additive `0004` migration introduces nullable lease fields.

Host PostgreSQL testing reached the full suite after the FTS metadata correction, but reported
24 failures in authentication and indexing. A focused test confirmed PostgreSQL's demo seed
used explicit IDs without advancing the tenant sequence, causing a duplicate primary key on
the next generated tenant. The seed now serializes PostgreSQL inserts while advancing the user
and tenant sequences without rewinding them. The full host PostgreSQL rerun passed all 96
tests. Local SQLite results after this fix: 91 passed, five PostgreSQL-only tests skipped.

## Sprint 3 Phase A3 — backend integration

**NOT YET VERIFIED.** Added migration `0003`, indexing jobs, tenant-linked snapshots/files/chunks,
dispatcher publication, a Celery indexing task, and authenticated index/status/keyword-search
routes. The worker builds and publishes in a single transaction after GitHub access checks.
Its pending status remains visible during work; live progress and lock-duration hardening remain.

| Check | Status | Evidence |
| --- | --- | --- |
| Backend suite | PASS with limitation | `apps/api/.venv/bin/python -m pytest -q -ra`: 85 passed; three PostgreSQL-only tests skipped (two locking tests and FTS search). |
| Index workflow test | PASS with limitation | Injected GitHub/source clients and direct worker invocation demonstrated persisted job, dispatcher callback, snapshot/chunk storage, retry rollback, and tenant/revocation denial using SQLite. This is not live Celery or GitHub. |
| Ruff / frontend | PASS | Backend Ruff and frontend typecheck and ESLint passed. |
| SQLite migration | PASS with limitation | Disposable SQLite database upgraded to 0002, seeded, upgraded to 0003; `alembic check` found no drift, `alembic current` returned 0003 and the demo repository remained. PostgreSQL migration and FTS indexes have not been verified. |
| PostgreSQL / Celery / GitHub / search | BLOCKED | Docker daemon inaccessible in this session; PostgreSQL FTS, real broker processing and real GitHub indexing have not been exercised. No live citation result is claimed. |

Current source filtering is pattern-based, not comprehensive. Real GitHub source indexing requires
Contents read permission; existing permission changes may revoke the current installation, and
reauthorization is unavailable. Use a separate development app/installation for real testing.

## Sprint 3 Phase A2 — source client increment

**NOT YET VERIFIED.** Added an isolated GitHub source client with HTTPS-only fixed origin,
request and response limits, rate-limit classification, resolved commit/tree mapping, and
content-addressed blob integrity validation. Added a high-confidence source pattern detector;
this is not comprehensive secret scanning. Neither is wired into authorization, persistence,
Celery, or an API and no real repository was downloaded or indexed.

| Check | Status | Evidence |
| --- | --- | --- |
| Backend tests | PASS with limitation | `apps/api/.venv/bin/python -m pytest -q`: 80 passed, two PostgreSQL-only tests skipped; source client uses `httpx.MockTransport`. |
| Ruff | PASS | `apps/api/.venv/bin/ruff check . --no-cache` passed. |
| Migration, worker, keyword search, frontend | BLOCKED | No Sprint 3 schema or indexing pipeline has been implemented; no live PostgreSQL/Celery or GitHub indexing test has been performed. |

An isolated collector enforces byte and chunk budgets and rejects files containing recognized
credential patterns before returning chunks. It is not connected to storage and is not a
comprehensive secret scanner. Publishing requires fresh authorization checks and atomicity.

## Sprint 3 initial primitives — 2026-10-28

**NOT VERIFIED / Phase A incomplete.** The isolated source-selection, snapshot-planning,
and Python chunking primitives have been added, but are not wired to an API, GitHub, database,
or worker. No repository source has been indexed. Candidate selection is not secret detection.
Snapshot planning rejects truncated trees instead of treating them as complete.

| Check | Status | Evidence |
| --- | --- | --- |
| Backend tests | PASS with limitation | `apps/api/.venv/bin/python -m pytest -q`: 74 passed, two PostgreSQL-only tests skipped. Snapshot tests use a fake client; no GitHub call. |
| Backend Ruff | PASS | `apps/api/.venv/bin/ruff check . --no-cache` passed. |
| Frontend typecheck and lint | PASS | `npm run typecheck && npm run lint` passed using installed dependencies. |
| Migration | BLOCKED / not applicable | No Sprint 3 migration exists yet; real PostgreSQL is unavailable in this sandbox. |
| Indexing, retrieval, benchmarks and browser | BLOCKED | No indexing worker, persisted snapshot, embeddings, search endpoint, evaluation or search UI exists yet. No benchmark results are claimed. |

## Sprint 2A real-service verification follow-up — 2026-10-28

Subsequent user screenshots show a real GitHub sign-in as `roshan-pandit1`, an eligible
personal installation listing public repositories, two connected repositories, and the UI
message “Initial issue synchronization completed.” The selected repository showed an empty
issue list. **PASS with limitation:** provider sign-in and onboarding were observed through the
UI; database job records, actual synchronized issues, and a real GitHub webhook remain to be
verified. No credentials or webhook payloads were supplied.

**PASS with limitation — real sync jobs:** The user queried PostgreSQL after sign-in. The
`Mini-Css-Project` and `To_Do_list` jobs were `processed`, each with one dispatch attempt and
a processing timestamp. Both repositories had zero stored issues; the demo repository retained
five. The UI and database evidence show job completion, but do not establish that a real issue
was imported, that an issue webhook was received, or that a browser rendered a real issue.

**PASS with limitation — real issue rendered:** The user created `To_Do_list` issue #1,
enabled the Issues event, and edited its title. GitHub showed an `issues.edited` delivery.
The relay initially reported HTTP 401 and PostgreSQL had no corresponding delivery or issue.
A later dashboard screenshot showed the edited issue as processed. The intervening fix and
the corresponding PostgreSQL delivery/outbox record have not yet been confirmed, so the
precise ingestion path and end-to-end webhook processing are still unverified.

| Check | Status | Evidence and limitations |
| --- | --- | --- |
| Commit and push | PASS, host-reported | The user ran `git commit` and `git push origin main`; commit `337967b` was pushed to `roshan-pandit1/RepoPilot`. This supersedes the earlier sandbox publication failure below. |
| Stack | PASS with limitation, host-reported | `docker compose ps` showed PostgreSQL, Redis, API and web healthy; worker and dispatcher were running without reported health checks. |
| Backend tests | PASS with limitation, host-reported | `docker compose exec api pytest -q -ra`: 58 passed, 2 skipped. Both skipped tests require PostgreSQL row locks; without `TEST_DATABASE_URL` the fixture uses SQLite. These tests use injected GitHub clients, not real GitHub. |
| PostgreSQL migration | BLOCKED | The user ran `docker compose run --rm migrate`; no error was shown, but the supplied output does not show the migration revision or a before/after data check. Confirm the live revision and preservation separately. |
| PostgreSQL concurrency tests | BLOCKED | Sprint 2A's two PostgreSQL-specific tests have not yet been reported against a disposable PostgreSQL database. Fixtures drop tables: never use the application database as `TEST_DATABASE_URL`. |
| Real GitHub onboarding and live lifecycle | BLOCKED | No real GitHub App sign-in, verified enrollment, synchronization or lifecycle event has been reported. Existing mock tests are not evidence of real provider integration. |
| GitHub Actions | BLOCKED | No actual workflow result has been provided. |

The app uses a user OAuth token, not an installation private key; GitHub App private key
configuration is not implemented or required by the current flow. A public webhook relay receives
event payloads: use a dedicated public test repository and a trusted relay, never expose the demo
dashboard or include webhook secrets, credentials, callback codes or payloads in shared logs.

## Repository publication attempt — 2026-10-28

The user authorized committing and pushing to `https://github.com/roshan-pandit1/RepoPilot`.
The existing `origin` points to that repository and the current branch is `main`.

- `uv lock --check --offline` passed, resolving 61 packages; the lock includes `cryptography`.
- Backend pytest: 58 passed, two PostgreSQL-only tests skipped; Ruff passed.
- Frontend type check, lint, 12 tests, and production build passed using installed dependencies.
- `git diff --check` passed. `.env`, environment variants, build output, node modules and local
  SQLite files are ignored. A targeted source scan did not find common token/private-key patterns.
- `git ls-remote origin refs/heads/main` failed because the sandbox could not resolve github.com.
- `git add -A -- .env.example .github/workflows/ci.yml .gitignore AGENTS.md Makefile README.md
  apps/api apps/web compose.yaml docs` failed: the sandbox denied creation of `.git/index.lock`.
  No files were staged; no commit or push was created.

The user can run the corresponding Git commands from their host Terminal. Do not force-push if
remote history differs; inspect the failure first. These checks do not prove real GitHub OAuth,
the new PostgreSQL migration, or a passing GitHub Actions workflow.

## Sprint 2A implementation — 2026-10-28

**Status: NOT RELEASE VERIFIED.** The new sign-in, personal installation verification,
repository selection, and first-page synchronization have not been exercised against real
GitHub or the real PostgreSQL/Redis/Celery stack. Sprint 1's earlier host results remain
historical evidence for the previous code, not evidence for these new changes.

| Check | Status | Evidence |
| --- | --- | --- |
| Backend `pytest -q` | PASS with limitation | 58 passed, two PostgreSQL-only concurrency tests skipped on SQLite. GitHub client interactions were injected or `httpx.MockTransport`; no real credentials or outbound GitHub calls. |
| Backend `ruff check . --no-cache` | PASS | No lint errors. |
| SQLite migration preservation | PASS with limitation | Fresh SQLite database upgraded to 0001, seeded, upgraded to 0002, and checked for model drift; existing demo repository and membership remained. PostgreSQL migration and downgrade were not run. |
| Frontend type check, lint, `npm test`, and build | PASS with limitation | Installed dependencies, Node 24 and Next 16.4.3. Twelve tests passed, including server-only forwarding of a real-session cookie and OAuth proxy redirect/error handling. Not a clean install, browser OAuth test, or a Docker build. |
| Python lockfile | PASS with limitation | The updated lock includes `cryptography` and its dependencies; `uv lock --check --offline` resolved 61 packages on October 28. A clean locked install and Docker build after this update have not been run in this session. |
| Real GitHub / host integration | BLOCKED | No registered App/test credentials or host Docker access were used. PKCE callback, cookie forwarding, real installation API, synchronization, Redis delivery, and PostgreSQL concurrency remain unverified end-to-end. |
| CI | BLOCKED | No remote workflow run; existing lockfiles remain uncommitted. |

Tests cover state mismatch/replay/expiry, encrypted token storage, session expiry and logout,
CSRF, production cookie attributes/demo rejection, personal account/app verification, private
repository rejection, tenant isolation, stale selection/removal tombstones, permission-change
revocation, a durable initial-sync job, idempotent processing, logout/revocation during queued
work, sanitized upstream errors, rollback on transient sync failure, access changes during fetch, and the first-page limit.
They do not prove concurrent PostgreSQL locking or real GitHub provider behavior.

Known restrictions before external use: personal accounts and public repositories only;
organizations and explicit reauthorization after revocation are unavailable; synchronization
covers the first 100 GitHub issue/PR entries only and may return `partial`; refresh tokens,
complete pagination, close/delete reconciliation, session/token retention cleanup, OAuth endpoint
rate limits, operational metrics, independent security review, and real-provider integration are
not implemented. Rotate encryption keys only with a planned session invalidation procedure.
No existing data was removed and no commit, push or deployment was performed.

On the authorized host, review the updated `apps/api/uv.lock` and use a disposable PostgreSQL
database to test migration preservation and concurrency. Rebuild the
stack and run the Sprint 1 smoke and full checks before testing a real GitHub App. Configure
secrets only locally, never include them in terminal output or screenshots, and use a public test
repository you control. Do not point `TEST_DATABASE_URL` at existing application data.

## Sprint 1 hardening / Sprint 2 planning — 2026-10-28

| Check | Status | Evidence and limits |
| --- | --- | --- |
| Frontend rendering and API-route tests | PASS with limitation | `npm test`: **9 passed**. Tests render actual issue-list states for loading, retry, errors including unauthorized, empty results, and escaped issue text. Separate route tests mock the upstream. They do not exercise browser networking, effect timing, or real backend authorization. |
| Retry behavior | FIXED, browser verification pending | A regression test first failed because loading plus an old error displayed the stale error. The retry handler now sets loading, and the issue list prioritizes the loading state. The focused test and full frontend suite passed afterward. |
| `npm run typecheck`, `npm run lint`, `npm run build` | PASS | Passed with installed dependencies and Node 24.22.0; Next.js 16.4.3 production build completed. |
| Backend pytest / Ruff | PASS with limitation | `pytest -q`: 38 passed, 1 PostgreSQL-only test skipped using SQLite. `ruff check . --no-cache` passed. Earlier host PostgreSQL run: 39 passed without warnings. |
| `uv lock --check` | PASS | uv 0.13.6 resolved 58 locked packages; manifest matches the lock. |
| Clean Python install in isolated temporary environment | BLOCKED locally | `uv sync --locked --offline` could not find the locked Ruff wheel in the isolated cache. Prior host Docker image build completed `uv sync --locked`. |
| npm lock and clean install | PASS with limitation | Root dependency specifications match. Prior host `npm ci` passed; current isolated offline `npm ci` could not find `zod-validation-error` in its cache. No dependency manifest or lock was changed in this task. |
| CI configuration | PASS static / BLOCKED actual | YAML parsed; push/PR triggers, PostgreSQL service, uv 0.13.6, Node 22, locked installs, lint/tests/build and smoke commands were checked. `actionlint` was unavailable and no GitHub Actions run was executed. |
| Git / secrets | PASS with limitation | `.env`, `.env.production`, node_modules, `.next` and a local SQLite file are ignored. Both lockfiles remain untracked. No file was staged, committed, or pushed. |
| Browser loading/error transitions | BLOCKED | No browser automation is available; server-rendering tests do not establish interactive fetch or retry timing. |

The current code is a local demo, not production-ready for external users. Before committing,
review the pre-existing and new working-tree changes and include the lockfiles only with the
user's authorization. A real GitHub Actions run is required before calling CI passed.

## Browser and database follow-up — 2026-10-28

| Check | Status | Evidence |
| --- | --- | --- |
| Browser Console | PASS with limitation | User screenshot shows no visible console error or hydration message at the captured moment. DevTools identified one form field without an id or name. The dashboard repository selector is the only form field in project source; an id and name have been added, but verification in the running Docker browser is pending. A fresh reload with preserved logs has not been confirmed. |
| Browser Network | PASS with limitation | User screenshot shows repeated `200` responses for health, repository and issue dashboard requests, and one canceled issue request. The canceled request is consistent with effect cleanup aborting an earlier fetch when the initial repository selection changes; its exact cause is inferred, not proven. No other failures are visible in the captured portion. |
| API-backed issue rendering | PASS with limitation | Dashboard source fetches `/api/dashboard` and renders `page.items`; screenshots show processed smoke rows, and host-reported live smoke previously verified the data route. The screenshot does not show response bodies. |
| PostgreSQL issue count | PASS, host-reported | User ran `SELECT count(*) FROM issues;` against the application database; PostgreSQL returned **4**, matching the screenshot’s four issue rows. |
| PostgreSQL delivery correlation | PASS, host screenshot | Read-only join returned four distinct issue IDs and four distinct delivery UUIDs. Every joined event was `issues`, each outbox status was `processed`, and each showed one dispatch attempt. Prior live smoke replayed its delivery and verified a single issue record. |
| Celery and dispatcher logs | PASS with limitation | User ran `docker compose logs --tail=80 worker dispatcher`; it returned no output. Worker log level is WARNING and successful completion is not explicitly logged, so empty logs do not independently prove processing. |
| GitHub Actions | BLOCKED | No workflow result reported; both lockfiles remain untracked. |

The read-only database join confirmed distinct issue IDs and distinct processed delivery UUIDs for
the four smoke issues, consistent with separate smoke runs. No data was deleted.

## Browser form-field fix — 2026-10-28

The user supplied DevTools evidence of a form field lacking an id or name. The repository
selector is the only form field in the dashboard source; `id="repository-selector"` and
`name="repository"` were added. Local frontend type checking, lint, all four API-route tests,
and the production build passed. A subsequent user screenshot showed the dashboard without the previous DevTools issue badge.
The user then confirmed `document.querySelector('#repository-selector') !== null` returned
`true` in the browser, verifying that the updated selector is served. GitHub Actions remains
unverified.

## Closure audit — 2026-10-28

**Verdict: SPRINT 1 VERIFIED LOCALLY for the demo ingestion slice.** User-supplied host evidence
shows a successful real-service smoke, 39 passing PostgreSQL-backed tests, the rendered issue
table, and four distinct processed issue/delivery pairs. The user confirmed the browser serves the
updated form selector. Loading/error states and a real GitHub Actions run remain unverified; the
worker logs contained no success records at the configured warning level.

| Check | Status | Evidence |
| --- | --- | --- |
| Backend tests and Ruff | PASS with limitation | This session: 38 passed, one PostgreSQL-only skip with SQLite; Ruff passed. Previous host run: 39 passed with PostgreSQL and no warnings. |
| Frontend checks | PASS with limitation | This session: type check, lint, four tests, and production build passed using installed packages. Previous host clean `npm ci` and checks passed with npm warnings. |
| Live smoke | PASS, host-reported | Earlier `make smoke` checked signature rejection, authentication, duplicate delivery, durable outbox, worker processing, persisted issue, API, and web data route. This session did not access Docker. |
| Browser rendering | PASS with limitation | User screenshots show four processed issue rows. Console, network failures, hydration, and loading/error states were not inspected. Browser automation is unavailable in this session. |
| Four smoke issues | PASS, host-reported | User-supplied SQL output showed four distinct issue IDs and four distinct processed delivery IDs, each with one dispatch attempt. The live smoke separately confirmed duplicate replay has a single issue effect. No data was removed. |
| Lockfiles / CI | BLOCKED for remote verification | `uv lock --check` passed. Workflow pins uv 0.13.6 and Node 22 and uses `uv sync --locked` and `npm ci`, but both lockfiles are untracked and no actual GitHub Actions run has been observed. |

Manual browser verification: open `http://localhost:3000`, press **⌘ Option J** in Chrome,
clear the Console, enable Preserve log in the Network panel, and reload. Confirm the issue table,
`/api/dashboard` and `/api/health` responses, absence of unexpected red console/hydration errors,
and no unexpected failed network requests. In DevTools Network throttling, briefly select Offline
and refresh to check the error state, then restore Online and refresh. Loading can be checked using
network throttling. Report observations rather than assuming these states passed.

## Host-assisted verification — 2026-10-27

The following result was supplied by the user from their macOS Terminal. The assistant did
not independently access Docker. Existing volumes were preserved.

| Command | Status | Host-reported evidence |
| --- | --- | --- |
| `make dev` | PASS | Compose built the API, migration, worker, dispatcher, and web images using cached build steps. PostgreSQL, Redis, API, worker, dispatcher, and web reported healthy; the migration container exited and dependent services started. |
| `make seed && make smoke` | PASS | User reported `PASS: auth rejection, signature rejection, durable delivery, deduplication, real worker, DB, API, web data`. The script checks a signed webhook, duplicate replay, processed outbox row, unique persisted issue, authorized API access, and the Next.js data route. |
| `make test && make lint` | PASS with limitations | User reported 38 passed, one PostgreSQL concurrency test skipped, two warnings; container Ruff with `--no-cache`, frontend type checking, and frontend ESLint passed. Pytest warned that `/app/.pytest_cache` was not writable and Starlette warned that its TestClient prefers `httpx2`. |
| `make dev && make test` after pytest cache fix | PASS with limitation | User reported successful locked API image rebuild and healthy services; pytest reported 38 passed, one PostgreSQL test skipped, and only the Starlette `httpx2` deprecation warning. The pytest cache permission warning no longer appeared. |
| PostgreSQL suite using a newly created disposable database | PASS | User reported **39 passed, one Starlette TestClient deprecation warning**. The formerly skipped row-locking test ran; test database remains in place. |
| `(cd apps/api && uv lock) && make dev && make test` | PASS with limitation | User reported lock generation with 58 packages, a successful `uv sync --locked` image rebuild, healthy services, and **38 passed, one PostgreSQL-only skip, no warnings**. The PostgreSQL suite needs a rerun with the updated test client. |
| PostgreSQL suite after locked test-client update | PASS | User reran the suite against the separate disposable database: **39 passed, no warnings**. |
| `make smoke` after locked dependency rebuild | PASS | User reported `PASS: auth rejection, signature rejection, durable delivery, deduplication, real worker, DB, API, web data`. |
| Browser issue rendering | PASS with limitation | User supplied a screenshot showing the `demo/repopilot-sandbox` issue table with multiple processed signed smoke issues. Browser console, loading and error states were not shown. |
| `(cd apps/web && npm ci && npm run typecheck && npm run lint && npm test && npm run build)` | PASS with warnings | User reported clean installation, zero npm audit vulnerabilities, type check, lint, four tests, and Next.js 16.4.3 production build passed. npm warned that ESLint 9.39.5 is unsupported and blocked the `unrs-resolver` postinstall script; all requested checks still passed. |
| Browser console, loading/error states, and CI | PENDING | Not yet verified from host output. |

## Current verification attempt — 2026-10-27

**Verdict: NOT YET VERIFIED.** Both lockfiles are present but untracked. No commit or push
was made. The running services and database state cannot be inspected from this sandbox.

| Check | Status | Actual result |
| --- | --- | --- |
| `docker compose config -q` | PASS | Compose configuration parsed successfully. |
| `docker compose exec api ruff check . --no-cache` | BLOCKED | Docker daemon socket permission denied; the reported cache failure could not be reproduced in this session. The Makefile now invokes this command once, before frontend checks. |
| Escalated Docker access | BLOCKED | Automatic approval policy rejected the request because sandbox approvals are disabled. No service commands were run with elevated access. |
| `make lint` | BLOCKED | The corrected first command could not connect to the Docker socket; full Makefile lint was not verified. |
| Host `ruff check . --no-cache` | PASS | Ruff found no backend lint errors. Host success does not verify container permissions. |
| Host `pytest -q -W default` | PASS with limitation | 38 passed, 1 skipped; SQLite-backed, with one Starlette TestClient deprecation warning. PostgreSQL row-locking test remains skipped. The user's second reported Docker warning could not be examined. |
| `uv lock --check` with uv 0.13.6 | PASS | 54 packages resolved; the backend lock matches its manifest. |
| `uv sync --locked --offline` into a temporary environment | BLOCKED | A locked psycopg wheel was absent from the local cache. A clean Python install was not verified. |
| npm manifest/lock consistency | PASS with limitation | Root dependency specifications match. Both lockfiles remain untracked; CI uses locked installation but has not run. |
| `npm ci` in a temporary directory | BLOCKED | Corrected invocation reached package download but failed with `ENOTFOUND` for the npm registry. This did not remove the existing installation. |
| Frontend `npm run typecheck`, `npm run lint`, `npm test`, `npm run build` | PASS with limitation | Existing installed dependencies, Node 24.22.0 and Next 16.4.3; four frontend API-route mock tests passed. ESLint initially scanned `node_modules.preverification`; global ignore now excludes dependency backups. `npm ls --depth=0` reported two extraneous optional packages. |
| Docker image build, `up -d --wait`, `ps`, logs, `make migrate`, `make seed`, `make test`, `make smoke` | BLOCKED | Daemon socket is unavailable; commands were not repeatedly retried after the denial. No assertion is made about Docker health, PostgreSQL, Redis, or Celery. |
| Browser / GitHub Actions | BLOCKED | No live app reachable for browser validation. No real workflow run was observed. |

The currently locked ESLint 9.39.5 is end-of-life. Some locked ESLint plugins declare peer
compatibility through ESLint 9 only, so moving to ESLint 10 requires a separately tested plugin
upgrade; no peer-dependency checks or npm install-script restrictions were bypassed. The blocked
`unrs-resolver` postinstall did not prevent the host lint or build from passing. Browser-console
errors have not been inspected. GitHub Actions has not been reported as passing.

The known warning comes from Starlette 1.10.0's `TestClient` fallback to `httpx`; it recommends
`httpx2`. It has not been suppressed. Adding or changing a dependency would require refreshing
and testing the lockfile; that is not possible with the current clean-install restrictions.
The second warning reported from Docker remains unknown because container logs are inaccessible.
The SQLite-only migration checks and historical verification results below do not validate
PostgreSQL. No live signed webhook, queued Celery event, or persisted dashboard issue was observed.

On a Docker-capable host with package registry access, run from the project root:

```bash
docker compose config -q
docker compose build
docker compose up -d --wait
docker compose ps
docker compose logs --tail 100
make migrate
make seed
make smoke
make test
make lint
(cd apps/web && npm ci && npx tsc --noEmit && npm run lint && npm test && npm run build)
```

Run the PostgreSQL test suite only against a **disposable** database because its fixtures drop
and recreate tables; never point `TEST_DATABASE_URL` at the running application database. Check
migration state and indexes without modifying application data. Then open
`http://localhost:3000`, select the demo repository, confirm the smoke-created issue appears,
check loading and error states, and inspect the browser console. Finally inspect a real GitHub
Actions run. Do not mark these checks passed from HTTP status or mocked tests alone.

## Final verification and environment recovery — 2026-10-27

**Overall: BLOCKED. Sprint 1 is not ready to close.** The existing Git checkout on `main`
was preserved. No commits or pushes were made. `.env` exists locally and remains ignored;
`.gitignore` was expanded for environment variants, local databases, and the preserved
preverification dependency directory. The previously copied frontend `node_modules` was
moved aside, so this session does not use it for clean installation.

| Check | Status | Evidence |
| --- | --- | --- |
| `git --version`, `git rev-parse --show-toplevel`, `git status --short --branch` | PASS | Git 2.54.0; existing checkout on `main`, with pre-existing uncommitted changes. No `git init` needed. |
| `docker compose version` | PASS | Compose v5.6.0. |
| `docker info` | BLOCKED | Docker client 29.8.2; server socket returned permission denied. Server version and service status are unknown. |
| `python3 --version`, `node --version`, `npm --version` | PASS | Python 3.15.0 (Python 3.14.8 also available); Node 24.22.0; npm 12.2.0. |
| `.venv/bin/python -m pip install uv==0.9.5`; `.venv/bin/uv --version` | PASS | uv 0.9.5 installed locally from PyPI. |
| Registry checks | PARTIAL | Approved `curl` received HTTP 200 from PyPI and npm; npm itself returned `ENOTFOUND` when resolving packages. PyPI simple-index download exceeded a 10-second timeout. |
| `PATH="$PWD/.venv/bin:$PATH" UV_CACHE_DIR=/tmp/repopilot-uv-cache UV_HTTP_TIMEOUT=5 UV_HTTP_RETRIES=0 UV_PYTHON_DOWNLOADS=never make lock` | BLOCKED | uv 0.9.5 panicked inside macOS SystemConfiguration. `uv lock --offline` also panicked. No uv.lock was created. Without `UV_CACHE_DIR`, its default cache path was denied. |
| `npm install --package-lock-only --ignore-scripts --cache /tmp/repopilot-clean-npm-cache --no-audit --no-fund --fetch-retries=0` | BLOCKED | `ENOTFOUND` from npm registry resolution. No package-lock.json was created. |
| `npm ci ... --fetch-retries=0`; `npm run build` | BLOCKED | Clean install requires the missing lockfile; build could not find Next.js after the old copied dependency tree was moved aside. Prior non-clean build evidence is listed below. |
| `../../.venv/bin/python -m pytest -q` (apps/api) | PASS with limitation | **38 passed, 1 skipped** using SQLite and directly installed dependencies; the skipped test requires PostgreSQL row locking. One Starlette TestClient deprecation warning was emitted. |
| `../../.venv/bin/python -m ruff check .` (apps/api) | PASS | All checks passed with Ruff 0.17.3. |
| `../../.venv/bin/alembic upgrade head`, `check`, `downgrade base`, `upgrade head` with a new temporary SQLite database | PASS with limitation | All four commands passed; no model drift detected on SQLite. PostgreSQL migration remains unverified. |
| `.venv/bin/python -m pip check` | PASS with limitation | No broken requirements in the local environment; dependencies were resolved by pip, not installed from a lockfile. |
| `test -f .env`; `docker compose config --quiet` | PASS | Existing `.env` preserved; configuration syntax validated. |
| `make dev`, `make migrate`, `make seed`, `make smoke`, `make test`, `make lint`; `docker compose ps` | BLOCKED | Docker daemon socket permission denied. No migration, startup, service health, worker, or live ingestion result was obtained. |
| Local TCP bind to `127.0.0.1` | BLOCKED | `PermissionError: [Errno 1] Operation not permitted`. No local HTTP service could be started. |
| Browser verification | BLOCKED | Chrome and Brave are installed, but no application can be started locally; no rendered issue or console check performed. |
| `gh run list --limit 3` | BLOCKED | Could not connect to api.github.com; no workflow success is claimed. The workflow statically specifies locked installs, backend tests/Ruff, frontend checks, and a Compose smoke job. |

The backend tests use a disposable SQLite database when run without `TEST_DATABASE_URL`.
Their results cannot prove PostgreSQL locking, Redis delivery, or live Celery operation.
The smoke script checks the dashboard data route but does not verify browser rendering.
No signed webhook has been demonstrated against a live stack in this session.

## Earlier Sprint 1.5 session

Date: 2026-10-27. At that time the workspace was not a Git checkout. The sandbox cannot resolve
PyPI/npm DNS, access the Docker daemon socket, or bind a local TCP listener. These are
independent blockers to dependency resolution, Compose, and live HTTP tests.

## Executed checks

| Command or check | Actual outcome |
| --- | --- |
| `test -f .env` | Passed; existing local development file was preserved. |
| `make lock` | Failed: `uv: command not found`. Neither lockfile exists. |
| `curl --fail --location --max-time 5 https://pypi.org/simple/uv/ -o /dev/null` | Failed: DNS could not resolve `pypi.org`. |
| `npm install --package-lock-only --ignore-scripts --cache /tmp/repopilot-npm-cache --fetch-retries=0 --fetch-timeout=5000 --no-audit --no-fund` (apps/web) | Failed: DNS could not resolve the npm registry. |
| Offline npm resolution | Failed: cached registry metadata / optional package archives incomplete. No incomplete lock was retained. |
| `npm ci --offline --cache /tmp/repopilot-npm-cache --no-audit --no-fund` | Failed: no package-lock.json. |
| `docker compose config --quiet` | Passed; validates the Compose configuration only. |
| `make dev`, `make migrate`, `make seed`, `make smoke`, `make test`, `make lint` | All failed: permission denied opening the Docker daemon socket. No services were started. |
| `../../.venv/bin/python -m pytest -q` (apps/api) | Collection failed: FastAPI missing. |
| `../../.venv/bin/python -m ruff check .` (apps/api) | Failed: Ruff missing. |
| `PYTHONPATH=apps/api .venv/bin/python -m pytest --confcutdir=apps/api/tests/unit apps/api/tests/unit -q` | **7 passed**: raw-body HMAC test vector and invalid/tampered signatures. |
| `python3.14 -m compileall -q apps/api infra` | Passed. Compilation does not exercise runtime imports. |
| `npm run typecheck` (apps/web) | Passed with copied local dependencies and Node 24.22.0. This was actual `tsc --noEmit`. |
| `npm run lint` (apps/web) | Initially failed on a Next.js link rule and a PostCSS export warning; both fixed. Rerun passed. |
| `npm test` (apps/web) | **4 passed** with a mocked upstream. Exercises the dashboard route and server API client, not a live backend. |
| `npm run build` (apps/web) | Passed with copied local dependencies and Node 24.22.0; Next.js 16.3.1 compiled and produced the App Router routes. |
| Python mock HTTP server on `127.0.0.1:18080` | Failed: `PermissionError: [Errno 1] Operation not permitted` while binding. No browser or live frontend/API integration check was possible. |
| GitHub Actions | Not run; no Git repository or remote is present. |

The successful frontend checks used a copy of `/Volumes/Samsung SSD/Project/DeepVerify/frontend/node_modules`
placed under the ignored `apps/web/node_modules`, including Next.js 16.3.1 and TypeScript 5.9.3.
The other project was not modified. These checks are useful but do **not** verify `npm ci`,
the missing frontend lock, the Docker image, or a clean checkout.

The frontend mock tests exercise the production route implementation, including token forwarding,
rejection when demo access is disabled, input validation, and safe upstream error handling. They
do not test React rendering, PostgreSQL, Redis, or a Celery worker. The new backend malformed-body
and non-ASCII bearer-token regression tests were written but could not be run without dependencies.

## Reproduce on an unrestricted host

Install Docker with Compose, Python 3.12+, Node 22 or 24, and uv **0.13.6**. Restore registry
access and use a disposable local database. Then, from the repository root:

```bash
test -f .env || python3 infra/init_env.py
make lock
make dev
make migrate
make seed
make smoke
make test
(cd apps/web && npm ci && npm run typecheck && npm run lint && npm test && npm run build)
make lint
```

The current lockfiles are untracked. Commit `apps/api/uv.lock` and
`apps/web/package-lock.json` only after verification and with the user’s authorization. Run the PostgreSQL test and migration checks in CI on a disposable database:

```bash
cd apps/api
uv sync --locked
# Set DATABASE_URL and TEST_DATABASE_URL to a disposable PostgreSQL database and
# GITHUB_WEBHOOK_SECRET to a local secret of at least 32 characters first.
uv run --locked alembic upgrade head
uv run --locked alembic check
uv run --locked alembic downgrade base
uv run --locked alembic upgrade head
uv run --locked pytest -q
uv run --locked ruff check .
```

After the smoke test, open `http://localhost:3000` and verify the signed demo issue is
rendered. The smoke checks the Next.js data route but does not operate a browser. Investigate
and fix any failed check before closing the sprint. A green remote GitHub Actions run is still
required; authoring the workflow is not evidence of a passing run.

## Open release blockers and security limitations

- Both lockfiles are present but uncommitted; clean installations were not verified because package archives are unavailable in this sandbox.
- Docker builds/startup, migrations, PostgreSQL concurrency, Redis/Celery, and live signed
  ingestion have not been run. There is no evidence of an issue persisted in this session.
- Backend tests and Ruff passed locally with SQLite and pip-installed dependencies; the PostgreSQL concurrency test was skipped and reproducibility remains unverified.
- Production OAuth, sessions and verified GitHub installation enrollment do not exist. Demo auth
  is deliberately shared and must remain local; production startup rejects demo authentication.
- Tenant isolation is enforced in application queries and composite keys, not PostgreSQL RLS.
  Retention/deletion automation and repository visibility/transfer reconciliation are absent.
- Readiness does not establish worker health. The outbox has bounded retries and requires operator
  review after exhaustion. Issue close/reopen synchronization and timestamp reconciliation remain
  out of scope.
- Sprint 1 / 1.5 is **not ready to close** until the definition-of-done checks pass.

### C3 v2 disposable evaluation (2026-10-29)

The matched host log and saved v2 report record source commit
`956a4f92983b222ce179891bbde39cb49a2022b2`, dataset SHA-256
`813414c2eece2fa42f57d75d9cc12b6dd77eb5d75d63999ad8cae14b65bdd2ba`, database
`repopilot_c3_disposable_a47f7b87227215f9` and published snapshot
`2207c4a6-2717-4c81-ab3c-eb777e97d557`. The script created a separate container and checked
the database name and empty schema before tests. It used no Compose services. The log shows
128 PostgreSQL tests passed, Ruff passed, migration 0006 head without drift, 30 verified labels,
published snapshot, and runner completion. The user reports the host command exited 0.
The application database was not independently inspected or compared before and after.

Sixteen positive/ambiguous questions and 30 labels were evaluated. Keyword macro recall
@1/@3/@5/@10 was **0.125 / 0.318 / 0.443 / 0.510**, MRR **0.404**, nDCG@10 **0.367**.
Twelve questions had at least one labeled top-10 result; `access`, `snapshot`, `chunking`,
and `citations` had none. The report records zero invalid citations among 160 results and zero
fallbacks. Latency p50/p95 was **26.968 / 61.661 ms** for 16 in-process test-client requests;
nearest-rank p95 is the slowest observation and does not establish load performance. An
independent evaluator invocation reconstructed metrics from stored relevant ranks and label
counts and matched the JSON and Markdown output. This checks arithmetic, not independent
retrieval: the report does not preserve all returned identities. Two negative candidates remain
unscored, and incomplete labels mean unlabeled results are not necessarily irrelevant.

The runner checks file hashes, chunk slices, commit, path and line ranges against local Git
blobs, and checks the citation URL structure; the matching successful host log and report
record the checks passing. The log also records the fixture's unauthenticated 401, unpublished
snapshot 409, revoked access and other-tenant 404 responses. Remote GitHub links are not
verified for this local-only commit. No embeddings were generated in this v2 run and real
semantic quality remains unmeasured.

The original 20-question v1 dataset remains separately pinned to
`63491908290e6874dbaaf2b15c2a96473aad1324`; its C3 keyword Recall@10 remained 0.80 and its
fake semantic/hybrid results are mechanical only. The separate v1 and v2 commits, questions,
labels and execution environments make their scores unsuitable for direct comparison.
The synthetic 1K/10K/50K scale and query-plan results remain in `c3-scale.md` and `.json`;
no additional index was justified. Paid-provider hard budget controls remain unimplemented,
and paid background generation remains disabled.

This final review also revalidated the 30 labels, passed 10 evaluation/adapter tests, Ruff,
and `git diff --check`. The seven previously observed frontend status entries remain present;
byte-for-byte preservation was not independently established. No source labels were changed.

## Sprint 4 checkpoint 4A — issue context

**NOT YET VERIFIED.** Added `GET /v1/repositories/{repository_id}/issues/{issue_number}/context`
for bounded fresh issue metadata and comments, without migrations or AI calls. A GitHub user
session, tenant membership, active enrolled installation and enabled repository are required;
current personal-installation/public-repository visibility and session/repository state are
rechecked after the bounded fetch. PRs and missing/inaccessible repositories are rejected.
GitHub errors are sanitized; timeout and rate-limit handling are covered with mocked transport.
Content is inert, untrusted data and links/attachments are not fetched. See README for limits,
truncation semantics and configuration. The per-operation request cap includes authorization
pagination as well as issue/comment calls. Stored issues are not used as a freshness authority.

Local backend test suite: **129 passed, 9 PostgreSQL-only skipped**, including 10 mocked issue
context tests; Ruff and `git diff --check` passed. No live GitHub context request was made.
Docker access is unavailable in the agent sandbox; PostgreSQL integration tests and migration
drift checks for this checkpoint remain pending. The host script
`apps/api/evaluation/run-4a-disposable.sh` creates a new isolated container/database, verifies
its name and empty schema before destructive fixtures, runs tests, and checks migrations. It
retains the new container and volume. The normal application database is not targeted.

The user subsequently provided a host screenshot of the dedicated disposable run: database
`repopilot_4a_disposable_2ad3cb51bc38243f` was confirmed empty before fixtures; **138
PostgreSQL tests passed**, Ruff passed, and Alembic reported **0006 (head)** with no pending
upgrade operations. The screenshot reports that the new container and volume were retained.
This is host-reported screenshot evidence; no live GitHub issue-context request has been
verified. **Checkpoint 4A remains NOT YET VERIFIED** pending live integration verification.

### Checkpoint 4A live verification preparation

The actual endpoint is `GET /v1/repositories/{repository_id}/issues/{issue_number}/context`;
there are no query parameters. Existing Next.js `/api/code/...` routes do not proxy this path.
The backend requires a real signed-in GitHub session and rechecks current personal-installation
and public-repository access before returning content. GitHub documents repository Issues: read
for GitHub App user tokens (public resources may be accessible without that permission); the
actual app installation's permission state has not been inspected. Changing installation
permissions can revoke RepoPilot enrollment and requires separate approval. No permission or
installation changes were made.

Localhost was unreachable in the agent sandbox and the GitHub repository/issues page could not
be retrieved by the web tool, so no actual issue number, GitHub result, or HTTP status has been
verified. In this review the focused mocked issue-context tests passed 10 tests and Ruff passed.
The previous host screenshot records 138 PostgreSQL tests and Alembic 0006 without drift.
Authentication, other-tenant denial, revocation, PR exclusion and malicious content are covered
by those mocked/integration tests, not a live revocation. Live field comparison and an
unauthenticated live request remain pending; Checkpoint 4A remains NOT YET VERIFIED.

### Checkpoint 4A same-origin issue-context proxy

A narrowly scoped Next.js GET route now forwards browser session cookies server-side to
`/v1/repositories/{repository_id}/issues/{issue_number}/context`, with bounded numeric IDs,
no-store headers, no redirect following, and sanitized error responses. Backend authentication,
repository and tenant authorization remain authoritative. The existing application container
must be rebuilt/restarted locally to serve this new route; no deployment was performed here.
Frontend verification: **24 tests passed**, typecheck and ESLint passed; focused backend
issue-context tests: **10 passed**. `git diff --check` passed. Live GitHub issue verification
remains pending, so checkpoint 4A remains NOT YET VERIFIED.

### Checkpoint 4A live GitHub verification — 2026-10-29

**SPRINT 4 CHECKPOINT 4A VERIFIED LOCALLY.** The user provided screenshots of a public
non-PR test issue #1 in `roshan-pandit1/RepoPilot` and the signed-in same-origin proxy response.
The response displayed repository ID `1435878031`, issue number 1, stable issue ID, title,
body, state `open`, empty labels and comments, creation/update/retrieval timestamps, GitHub
issue URL and all truncation flags `false`. The issue number, title, body and state match the
GitHub issue screenshot; the URL identifies the same issue. The success status is inferred as
200 from the proxy implementation's success-only response branch; the screenshot did not show
the Network status. Timestamps were present but not independently compared to exact GitHub
timestamps. There were no comments to compare, and the live issue did not exercise truncation.

A separate incognito screenshot showed `Authentication required`; the proxy maps that response
to 401, although the screenshot did not show the HTTP status. Other-tenant isolation, revoked
installation/repository access, pull-request rejection, malicious issue text, oversized input,
and truncation are covered by the mocked/integration tests; no live access was revoked.
The user previously supplied host evidence of 138 passing PostgreSQL tests, Ruff and migration
0006 without drift. The same-origin proxy passed 24 frontend tests, typecheck and lint; the
issue-context suite passed 10 focused tests. No GitHub App permission change, live reindex,
paid API call or additional commit was performed. Live testing covers one short public issue
with no comments, not all GitHub states or provider failure conditions.

## Sprint 4 checkpoint 4B — durable mock investigation jobs

**NOT YET VERIFIED.** Added tenant/user/repository-scoped investigation jobs and a dedicated
transactional outbox (migration 0007), authenticated CSRF-protected submission and authorized
status endpoints, dispatcher publication, and fenced lease-based Celery mock execution. Active
same-user/repository/issue submissions reuse a job; terminal requests may create a fresh job.
The job records issue identity and timestamps, not raw issue text or token material. GitHub
checks occur outside locked transactions; the worker rechecks session, membership, installation,
repository and current visibility before completion. Completed indicates mock orchestration only;
no source snapshot or AI inference is performed. Publication retries continue with capped delay;
worker claims are capped at five, and expired leases can be reclaimed. API, worker and outbox
status semantics and limitations are summarized in README.

Local backend verification: **135 passed, 10 PostgreSQL-only skipped**, Ruff passed. A fresh
SQLite database upgraded to Alembic 0007 and `alembic check` found no operations, with SQLite
warnings that expression indexes cannot be reflected; this is not PostgreSQL migration evidence.
Frontend: **26 tests passed**, typecheck and lint passed. PostgreSQL concurrency and schema
checks, actual Redis/dispatcher/Celery processing and the live issue #1 job remain pending.
Docker is inaccessible from the agent sandbox. `apps/api/evaluation/run-4b-disposable.sh`
creates a new isolated PostgreSQL container and database, confirms an empty schema before
fixtures, runs tests and migrations, and retains its new volume. The normal database has not
been changed. A live run against it requires explicit user approval for migration 0007, and
local app/worker/dispatcher restart after code review; it cannot be claimed from direct worker
unit tests. `apps/api/evaluation/investigation-live-check.js` is a prepared browser-side test,
not an execution record. No paid calls, commit, push or deployment were performed.

The user subsequently supplied a host screenshot showing a new empty dedicated database
`repopilot_4b_disposable_28472d8e081d0d12`: **145 PostgreSQL tests passed**, Ruff passed,
Alembic reported **0007 (head)** and no pending upgrade operations, and the disposable
container and volume were retained. This is host screenshot evidence, not a real
Redis/dispatcher/Celery execution. Live orchestration remains pending; the normal application
database has not been migrated by this work. **Checkpoint 4B remains NOT YET VERIFIED.**

### Checkpoint 4B local integration approval and preparation

The user approved an application database backup, additive migration 0007 and exactly one
mock job for RepoPilot issue #1. Sandbox Docker access is unavailable, so these actions have
not yet run. The reviewed migration adds the two investigation tables, indexes and constraints;
it does not alter or delete existing tables. The prepared host procedure
`apps/api/evaluation/run-4b-local-migration.sh` verifies the Compose project, local PostgreSQL
container address, development API/migration targets and existing revision, writes a private
custom-format database backup, validates that the full archive can be read, applies 0007 and
restarts only local services. Failure stops execution. It does not create a job.
`investigation-live-check.js` submits one job; the read-only `investigation-evidence.sh` and
`investigation-replay.sh` capture correlated status/log evidence and republish the existing task
without creating a new job. These are prepared procedures, not evidence of execution. Backup,
migration, authorization and real Celery results remain pending host output.

The user supplied a host screenshot of the migration procedure showing the migration-container
target/revision confirmation, Alembic `0007 (head)`, no new upgrade operations, the local
API healthy and worker/dispatcher/web started, and a retained backup at
`~/Library/Application Support/RepoPilot/backups/4b-p1KB07/repopilot-before-0007.dump`.
The visible screenshot does not show the earlier dump-validation output; the prepared script
is designed to stop on backup failure or unreadable archive. This is user-provided host evidence,
not an independently inspected backup or test restore. Exactly one live mock job remains to be
submitted and verified; checkpoint 4B remains NOT YET VERIFIED.

The user provided a browser screenshot showing one authorized mock investigation submitted as
`d0614fdf-6931-4f7f-ab52-37bcb9955208`, initially `queued`, then `completed` with one
attempt, no error code and operation `mock_orchestration`. This is a reported status API
observation; correlated database/outbox/dispatcher/worker and unauthenticated status evidence
are still pending. No second job has been authorized. Checkpoint 4B remains NOT YET VERIFIED.

The first correlation lookup and replay were given an incorrectly transcribed job UUID
(`47f7` instead of `4f7f` in the third group). The lookup returned zero rows and the replay
script reported that no task was sent. The incognito request also used the incorrect UUID and
returned an authentication-required message, without showing an HTTP status. Correct-ID
correlation and replay evidence remain pending.

### Checkpoint 4B local integration verification — 2026-10-29

**SPRINT 4 CHECKPOINT 4B VERIFIED LOCALLY**, within the limits below. The user-provided host
screenshots show the authorized issue #1 job `d0614fdf-6931-4f7f-ab52-37bcb9955208`
transitioned from queued to completed through the signed-in status API. The correlated
PostgreSQL row shows repository `1435878031`, issue 1, completed, one worker attempt, no error,
and an outbox status of processed with two dispatch attempts. Dispatcher and worker lifecycle
logs show dispatch, task receipt, claim and finalization. The user republished the existing
Celery task with a different task ID; the worker received it and the stored status and worker
attempt count remained completed and one. The repeat dispatch/receipt did not create a second
completed worker claim in the shown evidence. This exercises Redis/Celery at least once and
idempotent handling of a duplicate after completion; it does not prove behavior under every
failure or timing condition.

An incognito request for the correct job showed `Authentication required`. The screenshot
did not include the Network status code; 401 is inferred from the proxy's handling of the
backend response. Tenant isolation, revocation, concurrent claims, retry and lease recovery
were exercised in the previously reported disposable PostgreSQL suite of 145 passing tests.
The prior host screenshot reported migration 0007 at head with no drift and a retained backup;
the backup has not been independently restored. No AI inference, source retrieval, hypothesis
or report was performed. No push, commit or paid call is reported. This verification is local
and is not a production-readiness claim.

## Sprint 4 checkpoint 4C — snapshot-fenced evidence preparation

**SPRINT 4 CHECKPOINT 4C NOT YET VERIFIED.** New investigation jobs bind to an existing
published tenant/repository snapshot at submission. The worker fetches fresh authorized issue
metadata, checks issue identity/update time, rechecks repository access before searching and
before publication, uses the shared PostgreSQL keyword statement, and validates the same
snapshot and chunk fingerprints in the fenced publication transaction. Evidence references,
query IDs/hashes, pinned query-builder version/limits and job completion are committed atomically. After revocation, unpublication,
or a changed/missing chunk, the evidence API fails closed. Empty query/match outcomes and
partial snapshots are explicitly identified. The application does not enforce source-row
immutability at the database level; fingerprints detect subsequent changes at read time.

Migration 0008 adds job snapshot/operation fields and an evidence table with ownership foreign
keys and uniqueness constraints. Existing 4B jobs receive the legacy operation default, retaining
snapshot-null semantics; a disposable SQLite upgrade test verified a populated completed 0007
job and outbox survive. SQLite `alembic check` found no pending operations, but cannot reflect
existing expression indexes and is not PostgreSQL evidence. The six-case synthetic dataset
`apps/api/evaluation/investigation-evidence-v1.json` uses actual local Git commit
`956a4f92983b222ce179891bbde39cb49a2022b2`; four positive evidence labels were matched to
eligible source chunks. Its PostgreSQL evaluation test measures labeled top-10 hits, no-answer
behavior, local Git citation/chunk consistency and direct-worker latency, but was skipped here.
No evidence quality or latency scores have been measured in this environment. Query-builder
version and query/result budgets are pinned at submission; the API flags truncated query input.

Local backend suite: **159 passed, 12 PostgreSQL-only skipped**; Ruff passed. Frontend:
**27 tests passed**, typecheck and lint passed. `git diff --check` passed. Docker access to the
sandbox was denied. `apps/api/evaluation/run-4c-disposable.sh` prepares a new isolated
PostgreSQL container/database, verifies its target and empty schema, runs tests and migration
drift checks, and writes separate evaluation reports. The normal database was not migrated,
no live 4C job was created, and no real Redis/Celery 4C result is claimed. A reviewed local
migration helper and a one-job browser procedure are prepared but require separate approval.
Existing issue #1 is a generic issue-context test; it may exercise the pipeline but is not a
relevance benchmark. No paid models, embeddings, source reindex or AI conclusions were used.

### Checkpoint 4C disposable PostgreSQL and synthetic evaluation — 2026-10-29

The user supplied a host screenshot reporting the newly created, confirmed-empty database
`repopilot_4c_disposable_9c07073a6ea041d4`, **171 PostgreSQL tests passed**, Ruff passed,
Alembic **0008 (head)** and no pending operations. The separate saved
`apps/api/evaluation/4c-evaluation-local.json` and `.md` record a six-case direct-worker
PostgreSQL evaluation with mocked GitHub, dataset SHA-256
`4a082e5bb5133f945693ed8f44be940e9f072d4cbc8532e422ee9f8ecd0aa202`, and local commit
`956a4f92983b222ce179891bbde39cb49a2022b2`. Its disposable snapshot ID is
`599acb53-e760-4e9a-ad43-ef27ee099003`, with 77 collected files and 349 nonempty chunks.

Two of three positive cases had a labeled hit in the top 10: the exact identifier case at rank
1 and the ambiguous case at rank 4. The natural-language webhook-signature case had no
labeled hit in the top 10 despite 19 evidence candidates; the report does not establish whether
a labeled item occurred later. The two synthetic no-match cases returned no candidates and
`no_matches`; the malicious-text case returned `no_usable_queries`. Across 48 evidence items,
the test recorded zero citation/chunk mismatches against local Git objects. The direct-worker
latency p50/p95 was 28.239/68.736 ms over only six samples; the nearest-rank p95 is the maximum,
not a load-test estimate. Labels are incomplete, so unlabeled results are not necessarily
irrelevant. No real GitHub URL resolution, real Celery execution, semantic quality or AI
reasoning was evaluated by this fixture. The original 4C preparation record above describes the
previous sandbox state and is superseded by this host run for PostgreSQL tests and evaluation.

The existing local application database has not been migrated to 0008 and no live 4C job has
been created. A separate approval is required for each. **Checkpoint 4C remains NOT YET
VERIFIED** until an approved real PostgreSQL/Redis/Celery job and citation evidence are observed.

### Checkpoint 4C live verification approval and preflight preparation

The user approved a fresh backup, additive migration 0008 and exactly one new local issue #1
job. Docker is inaccessible from the agent sandbox, so no host operation has yet been executed
by the agent. The reviewed 0008 upgrade adds investigation job columns, constraints and the
new evidence table; its conventional downgrade removes them and is not authorized or used.
The host helper checks the local Compose database and 0007 revision, the prior completed 4B
job, an active published repository snapshot and absence of active issue #1 jobs; it creates
and reads back a private dump before applying the upgrade. The prepared browser helper checks
snapshot access via the authenticated API before submitting once. The evidence helper checks
persisted snapshot/chunk ownership and fingerprints, and a separate local Git verifier compares
file and chunk hashes, symbols and line ranges without printing source. A focused local Git
verifier test passed, Ruff passed, and shell/JavaScript syntax checks passed. Remote GitHub
citation resolution and live database, dispatcher, broker and worker results remain pending.

The user subsequently supplied a host screenshot of the approved local migration procedure:
local images built, the migration-container target/revision confirmed, Alembic `0008 (head)`
with no pending upgrade operations, the post-migration target/revision and prior 4B job verified,
and the API healthy with worker/dispatcher/web started. The output reported a fresh backup
retained under `~/Library/Application Support/RepoPilot/backups/4c-*`. The screenshot starts
partway through the procedure and does not itself show the initial snapshot/database preflight
or archive-read output; the script is designed to stop if those checks fail. No independent
test restore was performed. The approved single live 4C job and evidence remain pending.

The user provided a browser screenshot of the authorized 4C check: published commit
`63491908290e6874dbaaf2b15c2a96473aad1324`, newly submitted job
`457d40bf-7e15-4e10-9a27-b8a0de9e513b`, snapshot
`24e51533-c612-4833-921d-447cfed7df99`, and terminal `completed` status with one attempt,
`code_evidence` operation and 20 candidate references with `ready` retrieval status. The issue
is generic, so this is not evidence of meaningful relevance. The screenshot is authenticated
API evidence; database/outbox, correlated Celery logs, duplicate replay, unauthorized status,
local Git and remote citation checks remain pending. **Checkpoint 4C remains NOT YET VERIFIED.**

The user then supplied host terminal output for job `457d40bf-7e15-4e10-9a27-b8a0de9e513b`:
the application database reports `completed`, one worker attempt, no error, snapshot
`24e51533-c612-4833-921d-447cfed7df99`, commit
`63491908290e6874dbaaf2b15c2a96473aad1324`, and a processed outbox with three dispatch
attempts. The correlated dispatcher and Celery logs show dispatch, task receipt, claim,
evidence publication and finalization. Twenty distinct ranked evidence rows were present;
a separately dispatched duplicate task was received and finished, with the same 20 chunk IDs,
ranks and one worker attempt afterward. The local Git verifier confirmed that all 20 persisted
chunk references match file hashes, symbols and inclusive ranges in the specified local Git
commit. The user also reported an unauthenticated evidence request returning HTTP 401. The
signed-in browser had already returned job status and evidence references.

This is real local PostgreSQL/Redis/Celery orchestration and persisted evidence, not a relevance
assessment: issue #1 is a generic test issue. The remote GitHub permalink was not checked by the
local verifier, and an attempt to open the cited source through the agent's web tool failed to
fetch it. User confirmation of a GitHub-hosted citation opening to the expected commit, file
and lines remains outstanding. Until that citation check, **checkpoint 4C remains NOT YET
VERIFIED**. The disposable suite previously reported 171 PostgreSQL tests passed and Alembic
0008 without drift; backup retention was reported without a test restore.

### Checkpoint 4C final local verification — 2026-10-29

**SPRINT 4 CHECKPOINT 4C VERIFIED LOCALLY.** The user supplied GitHub screenshots of the
returned `process_sync` citation: `apps/api/app/workers/tasks.py` at displayed commit
`6349190`, with lines 74–147 highlighted. This verifies one GitHub-hosted citation; all 20
persisted evidence chunks were separately checked against local Git objects, not individually
opened on GitHub. The prior pending-citation verdict above is superseded by this evidence.

The single authorized live 4C job was `457d40bf-7e15-4e10-9a27-b8a0de9e513b` for repository
`1435878031`, issue 1, snapshot `24e51533-c612-4833-921d-447cfed7df99` and commit
`63491908290e6874dbaaf2b15c2a96473aad1324`. The user-reported database and correlated
logs show a completed job with one worker attempt, a processed outbox with three dispatch
attempts, real dispatcher and Celery receipt/claim/publication, and 20 persisted chunk
references. A duplicate task replay left the same evidence rows and attempt count. Authorized
status/evidence reads succeeded and an unauthenticated evidence request returned HTTP 401.
The user-reported disposable PostgreSQL suite passed 171 tests; Ruff passed, and migration
0008 was at head without drift. The host procedure reported a retained backup; it was not
independently test-restored.

The live issue is generic and the returned candidates are not judged relevant. In the separate
six-case synthetic evaluation, two of three positive cases had a labeled top-10 hit, with no
labeled top-10 hit for the natural-language case; labels are incomplete. No semantic quality,
AI inference, hypotheses or reports were evaluated. Local verification is not a claim of
production readiness or that every remote citation was individually opened.

### Checkpoint 4D mock reports — 2026-10-29

**SPRINT 4 CHECKPOINT 4D NOT YET VERIFIED.** The working tree now contains an explicit,
separately requested report task for an authorized completed 4C investigation. Submission
checks session, CSRF, current tenant/repository/installation access and the still-published
snapshot, and atomically inserts the task and its outbox row. A unique investigation-to-task
constraint makes repeated requests reuse the same task; failed or cancelled tasks do not have
an automatic restart endpoint. Existing 4B/4C jobs are not reprocessed. The worker claims a
lease, fetches bounded fresh issue context, checks issue identity/update time and current
authorization, projects the existing evidence into bounded mock input, and rechecks access,
snapshot, chunk fingerprints and the lease before publishing one report and terminal state
in a single transaction. No database transaction is held during model execution. The report
read API checks current authorization and verified evidence again, with local session,
revocation and snapshot locks acquired after the remote check; no report is returned for an
unsuccessful or partial task.

Only the deterministic `mock` / `deterministic-v1` in-process model is selectable; it does
not perform diagnostic reasoning. The API labels its output accordingly. Reports identify the
job, repository, issue, snapshot, commit and provider and include a summary, ordered possible
causes, supporting and contradictory evidence, missing information, high uncertainty,
diagnostic next steps, warnings, usage metadata and creation time. Model output may reference
only verified chunks belonging to the parent job, using their exact snapshot, commit and
inclusive line boundaries; duplicate, foreign, malformed and fabricated references are
rejected. URLs, paths and symbols come from verified server-side evidence, not the model.
Evidence-backed claims remain speculative, and a claim with no support is unsupported.
An empty evidence set can produce a valid report with no hypotheses.

The package is limited to eight evidence items, 800 UTF-8 bytes per sanitized source excerpt,
10,000 bytes of sanitized text, 32,000 bytes of serialized input, three hypotheses and 16,000
bytes of model output; rendered reports are capped at 60,000 bytes. No source excerpts or raw
model inputs are persisted in reports or returned by their API. Common sensitive patterns,
source literals and comments are redacted; the active GitHub token, session hash, configured
secret values and database/Redis passwords are checked against the projected package and
validated report output.
This is best-effort redaction, not proof that arbitrary secrets cannot occur in source or
metadata. Untrusted issue/source text has no tools, shell or
GitHub write capability in the mock. These safeguards and mock tests do not establish that a
future real model would resist prompt injection or be safe to send repository data to.

Actual local checks in this workspace: backend pytest **203 passed, 14 skipped** because
PostgreSQL-specific locks, full-text, vector, migration and sequence checks require a real
PostgreSQL database. The populated 0007 → 0008 → 0009 preservation and `alembic check`
passed on a disposable SQLite database; SQLite cannot establish PostgreSQL migration drift or
locking correctness. Ruff passed. Frontend proxy tests: **28 passed**; TypeScript typecheck
and ESLint passed. Shell syntax checks passed, and the prepared normal-database migration
helper failed closed when its explicit approval acknowledgement was absent. The full
PostgreSQL suite and PostgreSQL Alembic drift check have **not** run for 0009 in this sandbox.

The separate `mock-report-v1` evaluation produced seven valid structured outputs out of nine
model cases, rejected both intentionally invalid outputs, validated six synthetic references,
and observed one persisted report/one worker attempt after a duplicate direct delivery. A
mocked revoked-access read returned 404. The measured in-process model/validation latency
p50/p95 was **0.137/0.346 ms** over nine synthetic cases; this is not a service or load test.
The exact case outcomes and dataset hash are in `apps/api/evaluation/4d-evaluation-local.md`
and `.json`. It does not assess cause accuracy, remote citation resolution or real Celery.
The earlier 4C retrieval evaluation remains separate and its natural-language miss remains.

Migration `0009` adds report jobs, report outbox and reports, with composite ownership and
uniqueness constraints; its upgrade contains no table drops or data updates. Its downgrade
would remove the new tables and was not executed. The normal application database was not
migrated for 4D and no 4D report task or live investigation job was submitted. Docker access
is restricted in the agent sandbox. On the Mac host, the following runs tests and migrations
only against a **new**, checked-empty disposable PostgreSQL container/database and retains
its volume; it does not create a live task:

```sh
cd "/Volumes/Samsung SSD/Project/RepoPilot"
bash apps/api/evaluation/run-4d-disposable.sh
```

After those checks pass, a separate approval is required to back up and migrate the normal
local database to 0009, rebuild/restart local services, and create one mock report task for
completed 4C job `457d40bf-7e15-4e10-9a27-b8a0de9e513b`. The prepared
`run-4d-local-migration.sh` verifies the target, prior job/snapshot/evidence and reviewed
migration hash, creates and reads a private backup, then migrates; the backup would still need
an independent test restore to establish recoverability. Its acknowledgement flag is an
additional guard, not user authorization. `investigation-4d-live-check.js` is a prepared
one-submission browser procedure and `investigation-4d-evidence.sh` reads correlated task,
outbox and allowlisted lifecycle logs. Neither has been executed. Actual PostgreSQL
locking/drift, dispatcher/Redis/Celery execution, authorized report read and unauthenticated
rejection remain required before closing 4D.

### Checkpoint 4D approved local verification preparation — 2026-10-29

The user has now approved a fresh backup, local application migration 0009, local service
restart and exactly one mock report task for completed 4C investigation
`457d40bf-7e15-4e10-9a27-b8a0de9e513b`. This supersedes the approval requirement in the
preceding historical entry; it does not authorize another investigation job, a reindex or a
real provider. Docker remains inaccessible from the agent sandbox, so no backup, migration,
service restart or live report task has been performed by the agent in this step.

Code review confirms that 0009's **upgrade** creates three new report tables, their constraints
and an outbox index; it does not change existing investigation rows. The report submission
creates a separate report job and outbox event, while the report worker reads the completed
4C job and its evidence and does not reopen or mutate them. A focused regression test checks
that the parent status, attempts, timestamps, snapshot and evidence remain unchanged after
report processing. The host migration helper now also checks the expected local database,
0008 revision, all three report tables being absent, published snapshot and 20 existing
evidence rows, processed 4C outbox and existing non-revoked guards before making a backup.
It validates the backup archive before migration and checks that both prior jobs and evidence
remain present afterward. The archive-read check is not an independent test restore.

The disposable host runner now fails if any tests are skipped and runs the browser-helper
tests before any normal-database migration. Three local browser-helper tests passed: one POST
with valid evidence, no POST if the parent changed or a report exists, and failure on a bad
citation without resubmission. Focused report/migration tests passed **27**, with **3**
PostgreSQL-only skips in this sandbox; Ruff and shell/JavaScript syntax checks passed. A
separate probe confirmed that the disposable runner's test gate rejects skipped tests. The
host browser helper checks the original job before and after the report and compares each
returned citation to authorized evidence. The read-only evidence helper validates the
persisted report, snapshot, evidence fingerprints and reference ranges and prints only
identifiers, counts and allowlisted lifecycle log fields. None of these host procedures has
been executed here. The PostgreSQL results, fresh backup, 0009 migration and real report
execution remain pending; **checkpoint 4D remains NOT YET VERIFIED**.

### Checkpoint 4D authenticated browser result — 2026-10-29

The user supplied a screenshot of the approved browser helper submitting mock report task
`0bc440d3-0a4e-41fc-94f4-c0f3763deac6` for the existing 4C investigation. The authenticated
report API returned `completed` with one attempt. The helper reported that one report citation
matched the authorized evidence response and that the original 4C job's checked state was
unchanged. The displayed 404 occurred during the helper's expected pre-submission check that
no report existed; it preceded the successful submission.

The user subsequently reported an unauthenticated report request returning HTTP 401. The
evidence script printed its UUID usage message and did not return database or log evidence;
the actual report task UUID above must be supplied to run it. The screenshot and 401 do not
show the backup or disposable PostgreSQL test output, the persisted report ID and outbox row,
or correlated dispatcher/worker logs. Those host results are still needed to verify real
orchestration and close checkpoint 4D. **SPRINT 4 CHECKPOINT 4D NOT YET VERIFIED.**

### Checkpoint 4D real report orchestration evidence — 2026-10-29

The user supplied the read-only host evidence output for report task
`0bc440d3-0a4e-41fc-94f4-c0f3763deac6` and parent investigation
`457d40bf-7e15-4e10-9a27-b8a0de9e513b`. The application database reported one completed
report, ID `dbcbaa32-6330-475a-9da9-7bbb0f8e3305`, using `mock` / `deterministic-v1`.
The task had one worker attempt and a processed outbox with three dispatch attempts.
Correlated logs show dispatch, worker receipt and claim, and completion. Multiple deliveries
were observed, while the database retained one report and one worker attempt.

The host verification checked that the completed parent still had one attempt and 20 evidence
items, and that the report's one reference matched the persisted evidence and its fingerprint
for published snapshot `24e51533-c612-4833-921d-447cfed7df99`, commit
`63491908290e6874dbaaf2b15c2a96473aad1324`. The signed-in browser also reported its comparison
of the citation to authorized evidence and unchanged parent state; an unauthenticated report
request returned 401. These checks demonstrate local mock-report orchestration, not real AI
reasoning or root-cause quality.

A backup file was observed at `~/Library/Application Support/RepoPilot/backups/4d-GuxVsW/`
with size 241,480 bytes. File existence alone does not verify the archive or a restore. The
saved synthetic evaluation output was updated on the host; its current p50/p95 values are
0.390/0.749 ms for nine in-process mock cases, not a service benchmark. The earlier recorded
0.137/0.346 ms values refer to a different sandbox run. The saved evaluation file does not
establish the full disposable PostgreSQL test result. The disposable test output, archive-read
confirmation and application Alembic current/drift output remain to be reviewed. Until that
evidence is available, **SPRINT 4 CHECKPOINT 4D NOT YET VERIFIED.**

### Checkpoint 4D final local verification — 2026-10-29

**SPRINT 4 CHECKPOINT 4D VERIFIED LOCALLY.** The user supplied a screenshot of the host
verification command completing. It shows the disposable runner's final retained-container
message for `repopilot-4d-disposable-af47e657cfdf3b87`, followed by application Alembic
`0009 (head)`, no pending upgrade operations, and successful backup-archive reading. The
test-count line is not visible in the screenshot. From the reviewed runner's fail-closed
control flow, reaching that final message implies that its checked-empty disposable
PostgreSQL preflight, full pytest suite without skips, browser-helper tests, Ruff, disposable
Alembic upgrade/check and `git diff --check` succeeded. This is an inference from the shown
completion marker and script, not an independently observed test count. The container and
volume were retained. The backup was read as an archive; it was not independently restored.

The matching saved synthetic `mock-report-v1` evaluation contains seven valid reports, two
rejected invalid outputs and six validated synthetic references. It reports one persisted
report and one worker attempt after a duplicate direct delivery, plus a mocked revoked-access
HTTP 404. Its nine in-process samples had p50/p95 validation latency of 0.585/1.197 ms;
this is neither a service load measurement nor an assessment of diagnostic accuracy.

The separate real local PostgreSQL/outbox/Redis/Celery evidence immediately above shows report
`dbcbaa32-6330-475a-9da9-7bbb0f8e3305` completed through the approved report task, with one
worker attempt, three outbox dispatch attempts and one persisted report. Its one cited chunk
matched the authorized parent investigation's published snapshot and fingerprint. The parent
job remained completed and unchanged in the browser check, the signed-in report API returned
the report, and an unauthenticated request returned HTTP 401. The earlier pending verdicts
are superseded by this evidence.

This verifies mock orchestration and evidence grounding locally. The generic issue does not
establish issue-to-code relevance, the mock performs no real reasoning, and the report's
individual GitHub citation was not independently opened remotely in this 4D run. Secret
redaction is best effort. No paid model was enabled or called, and no test restore was made.

### Checkpoint 4E security preparation — 2026-10-29

**SPRINT 4 CHECKPOINT 4E NOT YET VERIFIED.** The model boundary now constructs an immutable,
application-owned `mock-report-policy-v1` instruction object separately from the bounded
untrusted issue, labels, comments, paths, symbols and source excerpts. The mock has no tools
or model-provider network interface. The server rejects invalid evidence allowlists before
model invocation and again during output validation, as well as tested explicit
forged-role/tool patterns, URLs, unsafe control characters and malformed or fabricated
model responses. Existing tenant/snapshot checks and lease-fenced, atomic publication remain
in force. Unknown model errors are reduced to safe error codes; prompts and source excerpts
are not persisted in reports or included in lifecycle logs. Invalid Unicode in a GitHub
issue is rejected by the issue schema without publishing a report.

The separate synthetic dataset `apps/api/evaluation/adversarial-report-v1.json` has SHA-256
`b7ba2f58a21d3c349198ccdaf2dfbfed968a7e384618cef7530c86fc44c020e6`. The local evaluator
reported **33/33** boundary checks passed: 14 untrusted input cases and 19 malicious-output
cases. Its per-case report is `apps/api/evaluation/4e-security-evaluation.md` and `.json`.
Separate workflow tests cover a foreign-tenant chunk, a same-tenant foreign-snapshot chunk,
access revoked during a mock call, timeout followed by malicious output, duplicate delivery,
external-operation guards and safe error/log handling. These tests use fake GitHub responses
and the deterministic mock; they are not evidence of a real model's prompt-injection resistance.

The local backend suite passed **255 tests**, with **14 PostgreSQL-specific tests skipped**;
Ruff, the existing three browser-helper tests, shell syntax and `git diff --check` passed.
The SQLite migration-preservation test includes an Alembic check, but SQLite does not verify
PostgreSQL locking or drift. Docker's API socket was unavailable in this environment, so no
4E PostgreSQL test or live 4E worker run was performed. No normal application database or
live job was changed. The prepared `apps/api/evaluation/run-4e-disposable.sh` creates a new,
checked-empty PostgreSQL container/database, runs all backend tests without skips, the security
evaluation, Ruff and Alembic checks, and retains its volume.

The output filters and secret redaction are best effort: they can miss obfuscated instructions
or unknown secrets and can reject benign text. A future real provider would require separate
review of role boundaries, tool permissions, disclosure, budgets and adversarial behavior;
the current tests do not establish real AI reasoning or production readiness. The report
schema does not persist the instruction-policy version for historical reports.

### Checkpoint 4E disposable PostgreSQL verification — 2026-10-29

**SPRINT 4 CHECKPOINT 4E PASS LOCALLY**, within the mock-only security scope. The user supplied
the completed host output for new container `repopilot-4e-disposable-f1c81fccddeca9be` and
database `repopilot_4e_disposable_f1c81fccddeca9be`. The runner confirmed the database was
empty and dedicated before testing. It reported **269 PostgreSQL tests passed, zero skipped**,
three browser-helper tests passed, Ruff passed, Alembic **0009 (head)** with no pending upgrade
operations, and all **33/33** adversarial fixture checks passed. The container and its new
volume were retained. This host output supersedes the pending PostgreSQL status above.

The reported dataset SHA-256 `b7ba2f58a21d3c349198ccdaf2dfbfed968a7e384618cef7530c86fc44c020e6`
matches both the current dataset file and the saved `4e-security-evaluation.json`. The 33
cases cover 14 untrusted input surfaces and 19 malicious model-output cases; the separate
workflow tests exercise tenant/snapshot checks, revocation, retries and publication safety.
These results use mocked GitHub responses and the in-process mock model. They do not establish
real-model prompt-injection resistance, complete secret detection or production readiness.
No new live investigation, real provider call or normal application-database mutation was
performed for 4E; the real Celery result remains the separately documented 4D baseline.

### Checkpoint 4F evaluation preparation — 2026-10-29

At the preparation stage **SPRINT 4 CHECKPOINT 4F was NOT YET VERIFIED**. The separate `issue-report-v1` dataset contains
19 synthetic issues: 16 source-location-scored cases, including two ambiguous cases, and
three unscored insufficient/unreviewed-negative/security cases. Twenty-three positive labels
were checked against local Git commit `30705da4c044192cab4ac207e253ab8e8a1bd100`, tree
`beac4e3116133a810f679761e17a7441fa77c2d7`, source selection and eligible chunk boundaries.
The dataset SHA-256 is `416cbf9e46b9399cf78d118f581a882d16cf512da439d352d3af29674c447bf6`.
The mapping is in `apps/api/evaluation/issue-report-v1-provenance.md`. At that stage no snapshot
or chunk UUID had been created. These incomplete labels do not establish root-cause correctness.
The natural-language signature case was included; its result is documented below.

The initial sandbox backend run, with the PostgreSQL committed-source snapshot test deliberately
excluded, reported **270 passed, 13 skipped** using SQLite; this is not PostgreSQL locking or
drift evidence. The focused 4F and 4E security tests subsequently passed, Ruff passed, the separately evaluated
4E adversarial fixture passed **33/33**, shell syntax and `git diff --check` passed, and the
approval guard refused an unapproved snapshot run. Docker's socket was denied to this sandbox.
`run-4f-checks.sh` was prepared for host PostgreSQL regression checks in a new disposable
database. The prior 4E host result remains separate and is not a 4F PostgreSQL result.

The user subsequently supplied a screenshot of the host `run-4f-checks.sh` completion:
**283 PostgreSQL tests passed**, all **33/33** adversarial checks passed, Ruff passed, and
Alembic reported **0009 (head)** with no pending upgrade operations. The screenshot names
the retained `repopilot-4f-checks-89d8c2f0d4f94786` container and says the committed-source
snapshot test was excluded. Its database-name and preflight lines are not visible. The reviewed
script only reaches the displayed success marker after its dedicated-empty-database preflight,
pytest (with skips treated as failure), security evaluation, Ruff and Alembic checks succeed;
those details are inferred from the shown marker and script rather than visible independently.
The extra 4F macro-recall unit test added while the host run was underway passed separately
in the sandbox. The new database and volume were retained.

The user subsequently approved creation of the committed-source snapshot and the evaluation.
The host results below supersede this preparation status.

### Checkpoint 4F final local verification — 2026-10-29

**SPRINT 4 CHECKPOINT 4F VERIFIED LOCALLY**, for the specified synthetic keyword and mock-report
evaluation scope. The user supplied the successful host output for new container
`repopilot-4f-disposable-4f762b71ae8d9569` and database
`repopilot_4f_disposable_4f762b71ae8d9569`. The runner confirmed the dedicated database was
empty, applied migrations there and reported Alembic **0009 (head)** without drift. It
published snapshot `1a8e0d9e-1cf1-4e0a-9cac-f8ced23f1694` for the exact commit above: 104
files, 889 chunks and one screened file. The container and its new volume were retained. No
normal application database or GitHub issue was changed.

The matching `4f-issue-report-v1-4f762b71ae8d9569.json` and `.md` record 16 scored and
three unscored cases. The existing evaluator gives macro **Recall@1/3/5/10 =
0.375/0.500/0.5625/0.625**, **MRR = 0.51414**, **nDCG@10 = 0.52054**, and a labeled hit
within the top 10 for **12/16** scored cases. Two of 19 cases returned zero evidence. Across
all cases, 226 evidence items were returned; all 226 recorded citation paths and inclusive
chunk ranges were independently checked against local committed Git objects. The evaluator
recomputed every per-case and aggregate retrieval score from the saved evidence. Direct-worker
latency p50/p95 was **50.798/92.294 ms** for these 19 cases; this is not a load benchmark.

The natural-language signature case returned the `webhook` handler at rank 2 but did not
return its other labeled verifier in the top 10: its label recall@10 is 0.5. This is a separate
dataset, commit and snapshot from the earlier 4C miss and does not establish a comparable
improvement. The four cases without a labeled top-10 hit concern repository access, Python
chunking, snapshot publication and citation boundaries. Their unlabeled results are not
automatically irrelevant. The insufficient-details case returned 10 candidates without a
scored label; the unreviewed negative and malicious case returned zero. None of those three
cases was scored as a confirmed no-answer case.

All **19/19** deterministic mock reports passed schema, investigation/snapshot provenance and
support-status checks; **17/17** references matched the authorized evidence, **2/2** empty
evidence cases abstained, and **19/19** duplicate direct deliveries left one report and one
worker attempt. Ten additional mock-output probes passed, including malformed, oversized,
foreign or cross-snapshot references, an incorrect commit, out-of-range lines, duplicate
references, unsafe text, unsupported claims and contradictory evidence. The test client
recorded HTTP 401 unauthenticated, 404 after repository revocation, 409 for an unpublished
snapshot and 404 for a different tenant. These checks use mocked GitHub and direct workers;
the separate 4D result is the evidence for real local Celery orchestration.

The host's separate disposable regression run reported **283 PostgreSQL tests passed**, with
the committed-source 4C test intentionally excluded, plus **33/33** adversarial checks, Ruff
and Alembic drift checks. Its final marker implies no pytest skips under the reviewed script.
Two additional evaluator unit tests were added after that run; the subsequent sandbox run
reported **272 passed, 13 skipped** (SQLite, with the committed-source 4C test excluded),
and **69** focused evaluation/security tests passed. Ruff, shell syntax and `git diff --check`
passed. PostgreSQL was unavailable to the sandbox itself.

The host log included HTTP callback query parameters from the synthetic OAuth test session.
These were mock-only one-time values, not credentials from the user's real GitHub session.
The evaluator now suppresses both `httpx` and the actual TestClient `httpx2` request loggers;
a synthetic OAuth callback regression test passes. This logging-only change followed the run,
so the runner's current hash differs from its recorded run hash; the recorded scorer and other
implementation hashes were checked, and the scores were independently recomputed. No new
snapshot or repeat evaluation was created for this fix.

The labels are incomplete; no human-reviewed root-cause quality or real-model performance was
measured. The rubric describes a future independent review. Source filtering and secret
redaction remain incomplete, and remote GitHub citation resolution was not checked in this
run. The previous v1/v2, 4C and 4D artifacts remain separate. No paid model or embedding call,
live reindex, deployment, commit or push was performed.

### Sprint 5A issue-investigation dashboard — 2026-10-30

**SPRINT 5A NOT YET VERIFIED.** The dashboard now selects a synchronized issue or accepts a
validated issue number for the selected authorized repository. It loads the existing bounded
issue-context API and can explicitly submit an investigation or open an existing job UUID.
The status view uses actual job states and the pinned snapshot/commit. Completed jobs can show
ranked evidence and request or read a deterministic mock report; no investigation or report
is submitted automatically. Mock reports are visibly identified as demonstrations, with
speculative/unsupported labels, citations, missing information and next steps.

The status response adds the stable issue ID and number, allowing the client to reject a job
from a different issue. The evidence API's default still omits source excerpts. Its optional
`include_snippets=true` returns at most 4,000 characters per verified evidence chunk, with
truncation/withholding indicators. Before returning excerpts it rechecks current GitHub access,
session, tenant, installation and repository guards, and the published snapshot and evidence
fingerprints. It withholds chunks containing recognizable credentials or known active runtime
secrets. These screens are incomplete; source and issue data must still be treated as untrusted.
The same-origin proxy only forwards this explicit query option. For investigation POSTs it
derives the existing CSRF header server-side from the CSRF cookie when necessary; the backend
still checks the exact origin, session, cookie and CSRF hash. Session and GitHub credentials are
not returned to the browser code.

The client validates response identity, snapshot, commit, ranks, citation URLs and report
references before displaying them. It renders issue and code text through React, never as HTML.
It aborts stale requests on issue/repository changes or unmount, prevents concurrent duplicate
submissions and limits active-job/report polling to 40 three-second attempts. Displayed results
are reauthorized every 30 seconds for a bounded period, hidden when the tab becomes inactive,
and cleared on failed revalidation. A remote revocation can take until the next check (and an
in-flight request timeout) to reach an already open view; this is not instant revocation.

Automated local checks on Node **22.23.4**: **48 frontend tests**, TypeScript, ESLint and the
production Next.js build passed. Frontend tests include server-rendered views and exercised asynchronous controller
transitions with mocked network/timers; they are not a real-browser test. The full SQLite
backend suite passed **275 tests, 14 skipped**; Ruff passed. The focused OAuth callback-log
regression passes for the post-4F runner. The 4F benchmark was not rerun: its artifact records
the then-current implementation hashes; both the logging runner and investigation routes have
since changed in the working tree. These checks used the uncommitted working tree based on
commit `30705da4c044192cab4ac207e253ab8e8a1bd100`, before the issue-loading fix recorded below.
The tested frontend controller, workspace,
dashboard and proxy SHA-256 values are respectively
`24f36b9dd7ee690452bcfd007350ad5bbfc65d64cfe354762fe5c18ff5e0580c`,
`0262bc2e771534a9f36c5eb255b52744f8ab1d086f344ece62adc89d420f455b`,
`f5f359891192ab4847efe4a50938e76b6b3d9b4613d9decce39b5efa2d43ac9b`, and
`45e362ebd2938dd61046eac4adebd01bf63cdd4900f8958995dede4296f5ff87`.
The current logging-runner SHA-256 is
`4d5daa8e76cf1bb26742277545465d9efa3cbac46a4c256d49300aeb8860e4bd`, and the current routes
SHA-256 is `3644dd628b40cea7edc570e44aaf2ef5ada9dcbfc083067551119c84edfc1d91`.

Docker and the local web service remain inaccessible from the sandbox. The user supplied host
evidence of rebuilt, healthy API and web services and a successful disposable PostgreSQL run,
recorded below. Authenticated browser verification remains pending. Read-only host verification
can use the previously completed issue #1 job `457d40bf-7e15-4e10-9a27-b8a0de9e513b` and its
report. A new live investigation or report requires separate user approval. No normal
application database, GitHub issue, live index, paid provider, deployment, commit or push was
changed for this checkpoint.

#### Sprint 5A final verification review

The existing disposable runner was reviewed before the host run. It creates a uniquely named
PostgreSQL container and database, verifies the target and an empty public schema, and points
the destructive pytest fixtures and Alembic commands at that database. It fails the run on
skipped pytest cases, excludes the separately gated committed-source snapshot test, and retains
the container and volume.

The user's 2026-10-30 host screenshot shows the API and web images built and both services
healthy. The API container's routes SHA-256 matched the reviewed value above; the web container
contained both the investigation and hidden-tab markers. Those checks do not establish actual
browser behavior or prove every frontend file by hash. The same host run created container
`repopilot-4f-checks-2affd11a715ea117` and empty database
`repopilot_4f_checks_2affd11a715ea117`. It reported **288 PostgreSQL tests passed** in 41.02 s;
the runner's success marker also requires no skipped tests. The prior committed-source snapshot
test was intentionally excluded. The adversarial fixture reported **33/33 passed** with dataset
SHA-256 `b7ba2f58a21d3c349198ccdaf2dfbfed968a7e384618cef7530c86fc44c020e6`; Ruff passed and
the disposable database reached Alembic **0009 (head)** with no drift. The container and its
volume were retained. This run did not create a committed-source benchmark snapshot.

The user subsequently reported that an unauthenticated host `curl` request to the existing
issue #1 job's same-origin report endpoint returned **HTTP 401**. This verifies rejection for
that unauthenticated report request; it does not demonstrate the signed-in dashboard or other
authorization scenarios in a browser.

During the review, the frontend suite was rerun with **48 passed**; focused investigation and
adversarial backend tests reported **45 passed and 1 PostgreSQL-only skip** on SQLite. Ruff and
`git diff --check` passed. These reruns and the host output do not replace authenticated browser
verification. No new investigation or report is authorized for that verification.

#### Sprint 5A issue-loading diagnosis and fix

The user reported that **Load issue** showed `Request unavailable. Please try again.` for
repository `roshan-pandit1/RepoPilot`, issue #1. Their Chrome Console screenshot shows that a
local probe calling `window.fetch` as another object's method throws `TypeError: Failed to
execute 'fetch' on 'Window': Illegal invocation`. The visible Network rows show dashboard
requests but no issue-context request; the screenshot does not establish the contents of the
entire Network log. The controller used the same receiver pattern, so the exception was caught
and reduced to the generic message before a request could be sent. The route and response schema
were checked against the existing API and earlier 4A issue-context evidence.

The default controller transport now calls `globalThis.fetch` with its global receiver. The
same-origin proxy and backend authorization were not changed. A regression with a
receiver-checking browser-fetch substitute and the issue #1 repository and issue identifiers
failed before the fix and passed afterward. On Node **22.23.4**, **49 frontend tests**,
TypeScript, ESLint and the production build passed. The focused issue-context and authentication
backend tests reported **26 passed and 1 PostgreSQL-only skip** on SQLite; Ruff and
`git diff --check` passed. The updated controller's SHA-256 is
`ef5f9a5e60905265a8372c540c1a2e142a18aad35c0582231edf78940f182f13`.

The user subsequently reported rebuilding and starting the local web service and receiving
**HTTP 401** from an unauthenticated host `curl` request to the issue #1 context endpoint. This
confirms rejection of that request, but is not an incognito-browser observation. The user's
earlier unauthenticated report HTTP 401 and 288-test disposable PostgreSQL run preceded this
frontend-only change; neither proves that the corrected issue workspace loads in Chrome. The
read-only authenticated issue and existing evidence/report display remain pending. No new live
investigation or report was created.

#### Sprint 5A historical status compatibility

The user's authenticated browser status responses returned HTTP 200 for both the historical
job `d0614fdf-6931-4f7f-ab52-37bcb9955208` and the newer job
`410e2d9e-44d3-4b61-852b-1a18a1506f1f`. The former reports `mock_orchestration`, null
snapshot and commit, `not_applicable` retrieval, zero evidence and null snapshot-partial;
the latter reports `code_evidence`, a snapshot and commit, and 20 evidence items. The frontend
had required the second shape for every job and therefore rejected the valid historical status.
The validator now accepts the historical shape only when its metadata is consistent, displays
its status without fabricating evidence, and does not request or offer evidence or reports for
that operation. Historical completed status is reauthorized on a bounded schedule and cleared
when access cannot be rechecked. Snapshot-backed jobs retain their existing validation and report
path.

An earlier user-supplied read-only application-database result associated mock report
`dbcbaa32-6330-475a-9da9-7bbb0f8e3305` with investigation
`457d40bf-7e15-4e10-9a27-b8a0de9e513b` for `roshan-pandit1/RepoPilot`, issue #1; it is not
the older orchestration job. A fresh read-only host query was requested because the sandbox
cannot reach Docker. Its result and authenticated browser verification of the corrected UI are
pending. The old and new response fixtures, inconsistent metadata, revocation, and switching from
a historical job to a snapshot-backed mock report are covered by tests. **53 frontend tests**,
TypeScript, ESLint and production build passed on Node 22; focused backend tests reported
**58 passed, 3 PostgreSQL-only skips** on SQLite. Ruff and `git diff --check` passed. The earlier
288-test PostgreSQL host run preceded this frontend-only change. No database records, jobs,
reports, GitHub issues or application migrations were created or modified for this fix.
