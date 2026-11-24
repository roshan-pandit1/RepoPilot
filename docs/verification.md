# Verification record

## Orbital background frontend check

The decorative canvas uses deterministic orbital strands and respects reduced motion and
tab visibility. On 2026-11-05 the frontend suite passed **65 tests**, TypeScript and ESLint
passed, and a production build passed using the lockfile in an isolated Node 22 container.
The Mac shell did not have Node on its PATH; an initial container build using the Mac
`node_modules` failed because Linux native bindings were absent. A clean temporary container
install with development dependencies resolved that environment issue. Desktop/mobile visual
review and performance measurement remain outstanding; the reference page was inaccessible
and no comparison screenshot of the orbital artwork was available in this session.

## Final demo Stage 3 — in progress

**REPOPILOT — FINAL BROWSER ACCEPTANCE INCOMPLETE.**

On 2026-11-05 Docker Desktop was started after the daemon was unavailable; its existing restart
policies started the isolated services. The read-only preflight confirmed project
`repopilot-local`, database `repopilot`, revision `0014`, expected published snapshot
`b11f8c40-2d4b-4ab3-a4d4-d053249f8bc8` and commit
`1d26667b64527b41e67013bd00d326ab86ada8de`. The snapshot remains partial with one skipped
file. The API and web returned HTTP 200, Redis and outbox queues were empty, and one Celery
worker reported zero active, reserved and scheduled tasks. Mock mode and disabled paid
providers were verified. The user's GitHub sign-in resulted in one active repository-tenant
session; no credential or cookie was read. Baseline counts were two legacy investigations and
one report. Chrome automation was unavailable, so further browser actions require the user.
Two new completed investigations were subsequently observed despite the one-investigation
limit: `213efc43-176c-478d-ab46-84ec187060f8` and
`d4a174c6-e74e-4996-9d67-1b8194df1fc1`. Both are pinned to the approved current snapshot,
have one worker attempt and 20 evidence rows. The user's screenshot shows the second completed
and displaying the partial-snapshot warning. For the first job, the evidence manifest and
outbox validated, and **20/20** source ranges and full-file hashes matched the pinned local Git
commit. The first job was selected for remaining checks. The extra investigation is a departure
from the authorized count and must remain visible in the record.
The user's [history screenshot](screenshots/stage3-investigation-history.png) confirms the
signed-in dashboard, issue #1 and both new completed jobs before report generation. Later
[evidence](screenshots/stage3-completed-evidence.png) and
[report](screenshots/stage3-mock-report.png) screenshots show the first job's completed state,
20 evidence results, partial-snapshot warning and clearly labeled mock report. A read-only
database check found one new report `55caaefa-0264-42bd-ba76-95fd2c3ca8fa` and its completed
report job `8157b294-b30a-4700-90d2-70284d20526e`, attached to the first investigation and
using `mock` / `deterministic-v1`. The application revalidated its one citation against 20
evidence items. CIE output for this job, opening the GitHub link, reopening from history and
mobile acceptance remain pending.

## Final demo Stage 2 — isolated migration and service restart

On 2026-11-04, the user explicitly authorized the `repopilot-local` image rebuild, migration
from `0013` to `0014`, and replacement of the four application containers. Preflight confirmed
the database, volume, snapshot, empty pending queues and stopped application services. The
Stage 1 archive hash and isolated restore result were revalidated; current metadata matched
the pre-migration backup.

API and web images built successfully, including the Next.js production build. The resulting
API image is `sha256:839d58f92f8cd1fbf52e766934434133ed5c35f2d7adbdffa665ac393597ca9b`
and web image is `sha256:8c47e0f0104dadd5330952dfd536a47f4e360e338363775e3b28eef5b7dbdde1`.
The API, worker and dispatcher use the same new API image. Running backend source and `0014`
migration hashes matched the checkout.

The reviewed one-off API command applied **only `0014`**, with lock and statement timeouts,
without starting the Compose migration service. Read-only verification confirmed revision
`0014`, both new tables, and zero rows in both provenance tables. Existing repository,
snapshot, investigation, evidence and report metadata matched the pre-migration backup.
The same comparison passed again after restart, including the recorded session count.
Snapshot `b11f8c40-2d4b-4ab3-a4d4-d053249f8bc8` remains current at commit
`1d26667b64527b41e67013bd00d326ab86ada8de`, with one skipped file. The database still has
two investigations and one mock report; the latest indexing job was unchanged.

The four authorized application services were replaced and started. API and web health are
healthy; `/ready` and web root returned HTTP 200. Worker and dispatcher are running with zero
restarts, the worker responded to Celery inspection with zero active, reserved and scheduled
tasks, and their logs showed no traceback or critical/error lines. PostgreSQL and Redis remain
on their original containers and volumes. Database pending/active job counts and Redis queued
and unacknowledged counts were zero. OAuth configuration is present, and mock mode, real-model
disablement, disabled paid embeddings and disabled external token counting were verified.

Investigation and CIE GET routes are present in OpenAPI; unauthenticated backend and proxy
requests returned HTTP 401. An initial route check that inspected `app.routes` directly failed
because this FastAPI version exposes included routers as lazy wrapper objects; the OpenAPI
and HTTP checks passed. Compose's dry-run restart preview also returned a dependency-health
error while the old API was intentionally stopped; the actual authorized restart succeeded.
The one-off migration container `repopilot-local-api-run-9cb324c0d05a` was retained and is
reported as an orphan by Compose; it was not deleted. The stopped Stage 1 dispatcher had exit
code 137; its cause was not established, and Stage 1 worker and queue checks showed no active
tasks. The new dispatcher is running with no restarts.

No new investigation, report, OAuth session, reindex, paid request, legacy backfill, volume
deletion, restore or automatic rollback was performed in Stage 2. The current snapshot
predates `0014`, so it has no publication record: a new job can use it while current, but
superseding it will still leave that job ineligible for historical reads. The old demo jobs
remain fail-closed. Final authenticated browser acceptance and any new demo writes require
separate approval. **REPOPILOT STAGE 2 — VERIFIED LOCALLY.**

## Final demo Stage 1 — backup and isolated restore

On 2026-11-04, the user explicitly authorized the Stage 1 preflight, Celery inspection,
quiescence, backup and isolated restore. Read-only checks confirmed Docker context
`desktop-linux`, project `repopilot-local`, PostgreSQL container `repopilot-local-postgres-1`,
volume `repopilot-local_postgres-data`, database `repopilot`, revision `0013`, and published
snapshot `b11f8c40-2d4b-4ab3-a4d4-d053249f8bc8` at commit
`1d26667b64527b41e67013bd00d326ab86ada8de`. Database pending/active counts, other open
transactions, Redis queue and unacknowledged counts were zero. Authorized Celery inspection
found one responding worker and zero active, reserved or scheduled tasks.

The web and API were stopped first, the queues were checked again, then the dispatcher and
worker were stopped. PostgreSQL and Redis remained running on their existing volumes. The
backup procedure required a one-line correction: its `pg_restore --list` check now uses
`docker exec -i`, because Docker otherwise closes standard input. The corrected script passed
`bash -n` before execution. No service was rebuilt or restarted.

The private custom-format backup was written to
`/Users/roshan/Library/Application Support/RepoPilot/backups/repopilot-20261104T103046Z.RbmJ8dtx/database.dump`.
Its independently recomputed SHA-256 is
`2eba6de1d6fce0554bf646314f5836ecad3c9c80b295c6d32ebd175cabd39b77`;
the directory is mode 700 and the archive mode 600. The archive catalog and before/after
metadata checks passed. An actual restore into retained network-isolated container
`repopilot-final-restore-4212f9efe26c1817` passed the stored JSON verification: revision
`0013`, target repository/issue, current snapshot and recorded metadata matched. Restored
totals included 2 investigations, 40 evidence rows and 1 report. The source database was
subsequently rechecked at `0013` with the same published snapshot. The restore used
`--no-owner --no-privileges`; role/grant fidelity, external encryption keys and complete
application-level recovery remain unverified. The archive is not automatically encrypted.
No migration, reindex, new job/report, paid request, volume deletion or legacy repair was
performed. Stage 2 requires separate approval.

## Final demo preparation — read-only preflight

Current context `desktop-linux`, project `repopilot-local`, container
`repopilot-local-postgres-1`, volume `repopilot-local_postgres-data`, database `repopilot`,
PostgreSQL **16.15**, revision **0013** and 35 public tables were confirmed. The enabled
repository and issue #1 exist. Current snapshot `b11f8c40-2d4b-4ab3-a4d4-d053249f8bc8`
pins commit `1d26667b64527b41e67013bd00d326ab86ada8de`, with 135 files, 1,482 chunks and
one skipped file; latest index status is partial. The database has two investigations,
40 evidence rows and one report. No pending database work, Redis queued/unacknowledged
messages or other open database transactions were observed at that instant. In-memory Celery
active/reserved/scheduled state has not been inspected because its control protocol writes
temporary Redis messages. OAuth configuration is present; mock provider and paid-disabled
settings were verified. Running backend images lack `0014` and differ from current source.

The [execution plan](final-demo-execution-plan.md) and backup/restore scripts were reviewed;
the Compose config, sanitized target guard and read-only metadata queries passed, and the
scripts passed shell syntax checks. The new configuration guard also passed Ruff. These are
preparations, not evidence of a successful backup, isolated restore,
application migration, service restart or browser acceptance. No such action or database
write was performed. Current snapshot `b11f8c40-...` predates `0014` and cannot gain a
durable historical publication record merely by migration.

## Historical snapshot correction — disposable verification

Revision `0014` adds new publication and evidence-manifest tables, with no legacy backfill.
The publication record separates current selection from historical eligibility and records
security/integrity revocation; the worker atomically records an evidence count and versioned
digest at finalization. Historical evidence, reports and CIE require publication provenance,
no revocation, an intact manifest and the existing authorization and source/citation checks.
Partial snapshots carry an explicit warning; legacy superseded jobs without original records
remain closed. The normal application databases were not migrated or changed, services were
not restarted, and existing data was not repaired. The implementation is not deployed.

The final focused run used fresh disposable PostgreSQL container
`repopilot-historical-check-642ff6d15020631e`: **103 passed, zero skipped**, including the
legacy migration and concurrent duplicate-worker tests. Alembic reached **0014 (head)**
and reported no drift. The application databases were not migration targets. The existing
adversarial fixture passed **33/33**. In a network-isolated container with the web source
mounted read-only, **61 frontend tests passed**, TypeScript passed and ESLint passed for the
changed frontend files. Ruff and `git diff --check` passed. The migration and tests do not
establish browser acceptance or provide a trustworthy backfill for the legacy demo jobs.

## Historical snapshot forensic follow-up

See [the focused assessment](historical-snapshot-assessment.md). Sanitized API logs record an
authenticated index-request path for job `34d8ea4f-0e45-4e03-a9f2-406bc7aa3d4b`, and the
dispatcher/worker logs record its publication; the requester or button click cannot be
determined from these logs. Partial publication is deliberate current behavior. The old
snapshot retains 135 files and 1,482 chunks; 40 stored evidence fingerprints and the mock
report citations revalidated in a read-only transaction. The old source collection skipped
one file. Prior publication/revocation history and an immutable complete-evidence manifest
are not represented durably enough to loosen historical reads safely under the stated
constraints. The proposed additive provenance/manifest design and possible separately
authorized legacy backfill are documented; no source, schema or application data was
changed. Existing focused tests passed **82** on disposable PostgreSQL; SQLite reported
**74 passed, 8 skipped**. Ruff and `git diff --check` passed. Historical reopening after
replacement, citation navigation and mobile acceptance remain blocked or unverified.

## Final local demonstration — preflight, browser pending

On 2026-11-04 a read-only preflight confirmed project `repopilot-local`, PostgreSQL volume
`repopilot-local_postgres-data`, database `repopilot`, revision `0013`, and the approved
published snapshot `5d24f965-fb26-431b-80b4-14275467c07d` at commit
`1d26667b64527b41e67013bd00d326ab86ada8de`. Its tenant-scoped counts matched 135 files
and 1,482 chunks; repository/installation are active and issue #1 is present. At inspection
there were zero jobs, report jobs, reports and active sessions, zero pending database work,
zero Redis queued/unacknowledged messages and zero other open transactions. Counts are
point-in-time observations, not a lock.

The isolated API and web were already healthy, the compiled CIE proxy was present, and
hashes of the running CIE module, CIE schema, investigation routes and worker tasks matched
the checkout. API, worker and dispatcher use the same image and target `postgres/repopilot`;
the API's `postgres` DNS resolved to the isolated PostgreSQL container. The mock provider is
selected, real generation and external token counting are disabled, and embeddings are
disabled. The reviewed Compose override validated. No build, restart, migration, browser
action, new job or report was performed during this preflight. The running images had been
updated outside this preflight; their build and restart were not observed. The
[browser checklist](browser-acceptance.md) records the user's authorization and remains
unexecuted. API `/ready` and the web root returned HTTP 200; an unauthenticated CIE proxy
request returned HTTP 401. GitHub access and authenticated browser behavior are not yet
verified. `git diff --check` passed.

User-provided browser screenshots subsequently showed GitHub connected, repository and issue
#1, investigation history, and a completed investigation. A read-only database query confirmed
job `c96bdb12-ef45-4221-beec-4223f60063d3`, one worker attempt and 20 evidence rows against
the approved snapshot and commit. There was one investigation and zero report jobs or reports.
The screenshot shows evidence hidden after the tab became inactive; it does not verify source
rendering, citation navigation, CIE, a mock report, history reopening or mobile layout. Those
checks and the report ID remain outstanding.

Later user screenshots showed source rendering and a mock report with the required warning.
Read-only inspection found a second completed investigation
`7fb9fb0b-f9ec-46d6-9d14-1311de6ffa68`, also with 20 evidence rows on the approved snapshot,
and one completed mock report `aedcc03e-1dc4-4656-af5e-032253cd6c94` (report job
`34c6cb7f-2009-401d-b1b6-fc9102094b1a`) attached to that second investigation. The
database contained two investigations and one report at this later check; only one new
investigation had been authorized for the controlled demonstration. Actual citation
navigation, CIE output, history reopening and mobile layout have not yet been evidenced.

Further screenshots showed investigation `7fb9fb0b-f9ec-46d6-9d14-1311de6ffa68` reopened
by ID, the report warning, and CIE returning an explicit insufficient-evidence abstention with
limitations. They also showed indexing in progress. A later read-only query found index job
`34d8ea4f-0e45-4e03-a9f2-406bc7aa3d4b` had completed `partial`, publishing snapshot
`b11f8c40-2d4b-4ab3-a4d4-d053249f8bc8` at the same commit and unpublishing the original
snapshot. Existing investigation and report routes require their pinned snapshot to remain
published, so subsequent access to those jobs is expected to fail. Reindexing was outside the
controlled-demo scope and was not initiated by the assistant. Citation navigation, reopening
from history and mobile layout remain unverified; no additional job or report was created by
the assistant.

## Browser acceptance environment recovery — read-only assessment

On 2026-11-04, the default Docker Compose database had zero public tables and no Alembic
marker. The separate local database is at `0013` and has the target repository, issue #1 and
a published snapshot, but no investigations, mock reports or active sessions. Neither requested
historical job nor the associated mock report was found there. The benchmark fixture is
separate. The running isolated API and web images lack the CIE code/proxy. No matching
application backup was found in searched locations; the broader home search had access errors,
so recoverability is unconfirmed rather than disproved. The
[recovery assessment and non-executed options](browser-environment-recovery.md) contain
identities, limits and approval boundaries. No services were started, no database was modified,
and no jobs, reports, migrations or reindex were performed in this assessment.

## Code Intelligence Engine v1

**Final acceptance follow-up — CIE-v1 remains NOT YET VERIFIED.** On 2026-11-04 the saved
`b5b1c925a167ec16` log was reviewed: **606 PostgreSQL tests passed with no skips**, **33/33**
adversarial cases, Ruff and Alembic `0013`/no drift, with exit 0 and matching source
fingerprints. The current backend source fingerprint also matches that run. No full suite was
repeated. Fresh read-only paired retrieval run `6f4f95ac2ccd1965` used the already approved
fixture and snapshot. `terms-v2` remains the production strategy and measured Recall@1/3/5/10
**0.3750/0.5000/0.5625/0.7188**, MRR **0.5177**, nDCG@10 **0.5469**, direct retrieval
p50/p95 **83.847/115.989 ms**, and **298/298** source-checked citations; `terms-v1` checked
**226/226**. Offline CIE replay `b53ff5ae7a3a87d7` used that new `terms-v2` artifact, made no
database query and produced unchanged metrics and candidate positions, **4/19** findings,
and **15/19** abstentions. Analysis-only p50/p95 was **13.347/30.143 ms**; one spawned-process
sample was **282.719 ms**. See [CIE evaluation](code-intelligence-engine.md#evaluation).

The default Compose application database `repopilot` was inspected in a read-only transaction:
its public schema contained **zero tables** and no `alembic_version` table. Its current revision
is therefore unavailable and it is **not compatible** with the current application. No migration
or application startup was performed. Existing data or a compatible database elsewhere was not
established. The combined [read-only browser checklist](browser-acceptance.md) is prepared but
has not been performed; it requires a compatible running stack and existing authorized jobs.

**Timeout-fix follow-up:** Disposable PostgreSQL run `9b4a749619a3f267` failed with **596
passed and 3 failed**. Its runner invoked pytest from a heredoc; a reproduction with the same
fenced harness showed macOS `spawn` trying to reopen nonexistent `<stdin>` before the child
could analyze anything. The resulting pipe EOF was incorrectly labeled as a timeout, leading
to the same safe HTTP 503 in the two API tests. The host log suppresses captured child stderr;
the explicit spawn traceback was observed in the reproduction. The runner now uses an
importable guarded module and retains its dedicated-empty-database and network safeguards;
child crashes and actual deadlines are distinguished without disclosing exception details.
The reported three tests passed four times under the fenced SQLite harness, and the focused
suite passed **48 with one PostgreSQL-only skip**. Corrected disposable PostgreSQL run
`b5b1c925a167ec16` passed **606 tests**, **33/33** adversarial cases, Ruff, Alembic `0013`
and no drift, with matching source fingerprints and exit 0. See the
[successful log](../apps/api/evaluation/5c1-checks-b5b1c925a167ec16.log) and
[CIE record](code-intelligence-engine.md#verification-and-outstanding-work).
Browser acceptance and a fresh direct retrieval benchmark remain outstanding.

**CODE INTELLIGENCE ENGINE v1 NOT YET VERIFIED.** Opt-in AST analysis, an authenticated
snapshot-fenced endpoint and a separate rule-based dashboard section are implemented. The
final local backend suite passed **577 tests with 23 PostgreSQL-dependent skips**; the focused
suite passed **41 with one PostgreSQL skip**, Ruff passed, the adversarial fixture passed
**33/33**, and frontend **60 tests**, TypeScript, ESLint and production build passed. The
database integration and new PostgreSQL security regressions were outstanding at that time
because Docker's socket was unavailable; the successful follow-up above supersedes that
blocker. Browser acceptance for this feature and 5C2 is still outstanding.

The saved 5C1 `terms-v2` evidence was replayed offline against the same pinned local Git
source. Run `17a92df198280e40` produced unchanged labeled retrieval metrics and no changed
candidate positions; it returned findings for **4/19** cases and abstained for **15/19**.
Analysis-only p50/p95 was **14.384/35.263 ms**, one spawned-process sample was **292.446 ms**,
and one in-process traced allocation peak was **2,604,961 bytes**. These are not fresh
PostgreSQL retrieval, end-to-end latency, child-process RSS or diagnosis-accuracy measurements.
`terms-v2` remains the production order. No model, paid API, new live job, database migration
or repository reindex was used. See [CIE-v1 design and reproduction](code-intelligence-engine.md).

## Final local MVP implementation assessment

**REPOPILOT — PLACEMENT-READY MVP IMPLEMENTATION COMPLETE**, with the deferred dashboard
browser acceptance, current local-stack/schema verification, application-backup restore and
public deployment review explicitly outstanding. Final disposable PostgreSQL run
`44627f6c0aa305e1` passed **587 tests**, **33/33** adversarial checks, Ruff, Alembic `0013`
and no drift, with matching source fingerprints and exit 0. Frontend **58 tests**, typecheck,
ESLint and production build passed using Node 24.11.1 and existing dependencies. Compose
configuration validation and a mock configuration with no OpenAI key passed. A synthetic
two-row PostgreSQL/pgvector dump was independently restored in network-isolated container
`repopilot-restore-drill-c1acd8ebf541f8b3`; this does not validate any application backup.
No normal application database migration, live investigation, report, reindex or paid provider
call occurred in this pass. Details and component classifications are in
[final project status](final-project-status.md); [local operations](local-operations.md)
records the migration and recovery limitations.

## Sprint 5C2 — investigation dashboard

**SPRINT 5C2 NOT YET VERIFIED:** browser acceptance with persisted local investigations and
reports remains outstanding. The read-only history endpoint and workspace changes are described
in [the Sprint 5C2 report](sprint-5c2-dashboard.md), including the browser checklist and
limitations. Frontend verification passed: **58 tests**, TypeScript, ESLint and production build
with Node 24.11.1 and existing dependencies. Disposable PostgreSQL regression
`09581d0adb29861f` passed **587 tests**, **33/33** adversarial checks, Ruff, Alembic `0013`
and no drift, with matching fingerprints and exit 0. The committed-source benchmark test was
excluded; no normal application database was migrated. Server-rendered frontend tests do not
prove browser interactions. No paid provider calls or new live jobs were made.

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
recorded below. The user subsequently reported successful authenticated read-only dashboard
verification, also recorded below. A new live investigation or report requires separate user
approval. At this stage, no normal application database, GitHub issue, live index, paid provider,
deployment, commit or push had been changed for this checkpoint; the user later explicitly
authorized the commit recorded below.

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
frontend-only change; neither alone proves that the corrected issue workspace loads in Chrome.
The user later reported successful read-only browser behavior as recorded below. No new live
investigation or report was created for this fix.

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
cannot reach Docker; no result from that fresh query was supplied. The old and new response
fixtures, inconsistent metadata, revocation, and switching from
a historical job to a snapshot-backed mock report are covered by tests. **53 frontend tests**,
TypeScript, ESLint and production build passed on Node 22; focused backend tests reported
**58 passed, 3 PostgreSQL-only skips** on SQLite. Ruff and `git diff --check` passed. The earlier
288-test PostgreSQL host run preceded this frontend-only change. No database records, jobs,
reports, GitHub issues or application migrations were created or modified for this fix.

#### Sprint 5A read-only browser evidence and remaining acceptance gap

The user subsequently reported that the authenticated dashboard displays GitHub issue #1, a
completed historical investigation, 20 persisted source-evidence results, and an existing mock
report. They reported opening a verified GitHub source citation and seeing the visible
**MOCK REPORT — DEMONSTRATION ONLY** label, hypothesis, uncertainty, supporting evidence and
limitations. They also reported that the historical-status compatibility issue was corrected.
This is user-reported browser evidence; no screenshot, job ID or Network trace accompanied this
confirmation, so it is not an independent verification of every displayed item or link. Earlier
host evidence separately associated report `dbcbaa32-6330-475a-9da9-7bbb0f8e3305` with
investigation `457d40bf-7e15-4e10-9a27-b8a0de9e513b` and issue #1, but the latest browser
statement did not specify a job or report ID. The mock output is a demonstration, not AI
reasoning or a verified root cause.

The most recent supplied PostgreSQL regression result remains **288 passed, no skips**, plus
**33/33** adversarial fixtures, Ruff, and Alembic 0009 with no drift on a new disposable database;
the separately gated committed-source snapshot test was excluded. That run preceded the final
frontend compatibility adjustment and an additional backend test assertion. The latest recorded
frontend checks on that adjustment were **53 passed**, typecheck, ESLint and production build;
the focused SQLite backend checks were **58 passed, 3 skipped**. The API routes source hash
recorded for the PostgreSQL run remained unchanged. The changes were subsequently committed
and pushed at the user's request as `bcea57041721c895659ed38c398438ea91519d70`.

The read-only UI path is reported verified, but **SPRINT 5A remains NOT YET VERIFIED** in full:
the evidence supplied so far does not show the current dashboard's **Investigate issue** action
submitting a job through the real local backend and observing its lifecycle. The earlier 4C
live browser/API submission exercised the backend and real outbox/Redis/Celery pipeline, while
the current dashboard submission tests use mocked network responses. Evidence that the current
dashboard already submitted a real job would satisfy this gap without necessarily creating
another one. Otherwise a controlled new live submission requires separate authorization. The
request at that time prohibited creating an investigation or report, so neither was created in
that step. The user's later, limited authorization is recorded below.

#### Sprint 5A live dashboard submission verification — pending

The user has approved exactly one browser-initiated investigation for issue #1 in
`roshan-pandit1/RepoPilot` if existing evidence does not already demonstrate submission by the
current dashboard. The existing records demonstrate a real 4C backend pipeline and later
read-only dashboard access, but do not identify a verified dashboard-button POST for the later
job. Confirmation of any such prior evidence is pending. No new report, migration, reindex,
GitHub write, paid provider call, commit, push or deployment is authorized for this verification.

The agent cannot access Docker or the authenticated host browser. A read-only host preflight
was prepared to check service state, Redis and worker responsiveness, API/worker/dispatcher
fingerprints, the web bundle, the published snapshot, and issue-job counts before any submission.
Its actual output was pending at that point. No new investigation or report has been created by the agent.
The generic issue must not be used to claim root-cause relevance. **SPRINT 5A remains NOT YET
VERIFIED** until the browser submission and resulting live pipeline are demonstrated or prior
equivalent evidence is supplied.

The user attempted the host preflight, but its first Docker command failed because the Docker
daemon socket was unavailable (`no such file or directory`). The script was configured to stop
on that failure, before the read-only database and service checks. No browser submission was
reported at that point; Docker availability and preflight results were still outstanding.

The user subsequently supplied successful preflight output: one Celery node online, API HTTP
200 readiness, matching API/worker/dispatcher source fingerprints, web-to-API readiness,
embedding provider disabled, and a read-only transaction against the local `repopilot`
database. The enabled and active repository was `roshan-pandit1/RepoPilot`; its published
snapshot was `24e51533-c612-4833-921d-447cfed7df99` at commit
`63491908290e6874dbaaf2b15c2a96473aad1324`, with 278 chunks. The baseline was five issue #1
jobs, none queued or running. The web bundle contained the reviewed dashboard markers, but its
reported SHA-256 `6a69624ac52d7083ca0c466afd161dbde54d7b59bf4b8a9d7766d27deb83bac7` differs
from the agent's local build artifact; that difference and any prior dashboard POST evidence
are being checked before proceeding. No new submission has been reported.

The user then copied the running web page bundle for comparison. Both it and the locally tested
bundle were 59,653 bytes. Parsing their webpack page payloads showed that both executable module
bodies were byte-identical; their order and the generated entry-module ID differed. The outer
wrappers also matched after normalizing that entry ID. The investigation controller class,
including submission and status handling, matched byte-for-byte. This establishes equivalence
for the compared page modules, not every server-side file in the image. The earlier-recorded
issue #1 job still has no supplied evidence identifying a dashboard-button POST.

The user next supplied a dashboard screenshot showing issue #1, a Network row with HTTP 202,
and job `810a7792-7f48-45bf-8331-ad9aaaf416a4` displayed as queued with zero attempts and
zero evidence. The displayed snapshot was `24e51533-c612-4833-921d-447cfed7df99` at commit
`63491908290e6874dbaaf2b15c2a96473aad1324`. The screenshot did not open the 202 response
body or show the request method, so the returned ID and status still need direct confirmation.
The UI stated that polling had paused while the tab was inactive. A read-only status refresh,
persisted job/outbox and worker evidence, evidence display, and a duplicate check remain
pending; no report-generation action is authorized.

The user subsequently supplied the end of the correlated host evidence output. It shows two
`investigation_job_dispatched` events, two task receipts, one claim, evidence publication,
finalization and task completion for `810a7792-7f48-45bf-8331-ad9aaaf416a4`. The existing
4C evidence script reported that **20 evidence chunks** match local Git commit
`63491908290e6874dbaaf2b15c2a96473aad1324`. That script's successful validation requires a
completed job, processed outbox, published matching snapshot, unique evidence chunks and
contiguous ranks; the displayed screenshot does not include the initial job/outbox row or its
attempt counts. It does not check remote GitHub link resolution. A POST response body, the
compact database counts, and an authenticated dashboard terminal/reopen view remain pending.
The generic issue's results are not evidence of root-cause relevance.

The user then supplied the compact read-only database results for this job: `completed`, one
worker attempt, no error, outbox `processed` with two dispatch attempts, 20 evidence rows with
20 distinct chunks and ranks, and zero associated report jobs. The issue #1 job count increased
from five at preflight to six, consistent with one new job. Together with the two receipts and
single claim in the supplied logs, this supports safe handling of the observed duplicate
deliveries; no deliberate replay or second submission was performed. The 202 response body and
authenticated dashboard terminal/reopen observations were pending at that point.

#### Sprint 5A final verdict

**SPRINT 5A VERIFIED LOCALLY**, based on the combined user-supplied browser and host evidence.
The user reports that the authenticated dashboard submitted issue #1, displayed the completed
job and its 20 evidence results, and reopened job `810a7792-7f48-45bf-8331-ad9aaaf416a4`.
The correlated database and worker observations above show completion, one worker attempt,
a processed outbox with two dispatch attempts, and 20 unique chunks and ranks. The user also
reported opening a commit-pinned GitHub citation and viewing an existing mock report, its
uncertainty, supporting evidence and the demonstration-only label. The original submission
POST response body was not captured, and the screenshot's 202 row did not show its method;
these details have not been independently reconstructed. The generic issue and deterministic
mock report do not establish retrieval relevance or AI reasoning quality.

### Sprint 5B1 real-provider foundation — 2026-10-30

**SPRINT 5B1 VERIFIED LOCALLY within the mock-transport foundation scope.** The working tree based on
`bcea57041721c895659ed38c398438ea91519d70` adds an OpenAI Responses adapter, tenant-bound
experiment selection, a PostgreSQL reservation ledger and a separate real-report table.
Mock reports remain the default. Real generation and paid background execution both default
to disabled; a credential alone is insufficient. The provider adapter was exercised only
with an in-process mocked HTTP transport and synthetic content. No real model request,
paid embedding call, live investigation, report generation or normal-database migration
was performed for 5B1.

The simulated workflow tests cover provider and experiment gates, tenant selection,
grounded report publication, duplicate delivery, changed authorization, malformed output,
foreign citations, wrong commits, unexpected provider-model identity, no-evidence abstention, timeouts and unknown billing,
reservation lease takeover, request limits, and conservative usage reconciliation. The
request uses separate application instructions and untrusted data, no tools, strict JSON
schema, bounded response size and server-side citation validation. Prompt-injection
resistance and secret filtering remain incomplete for any future real model.

Executed in this sandbox on the current uncommitted working tree:

- Backend SQLite pytest: **301 passed, 17 skipped**. The skipped tests include both new
  PostgreSQL budget/concurrency races and the gated actual-mode fake-transport test;
  SQLite does not establish row-lock safety.
- Synthetic 4E adversarial fixture: **33/33 passed**, dataset SHA-256
  `b7ba2f58a21d3c349198ccdaf2dfbfed968a7e384618cef7530c86fc44c020e6`.
- Frontend: **54 tests passed**, TypeScript, ESLint and production build passed.
- Backend Ruff and `git diff --check` passed.
- On a newly created temporary SQLite database, Alembic upgraded through `0009` to
  **`0010 (head)`**, and `alembic check` reported no new operations. SQLite emitted
  warnings that the two existing full-text expression indexes could not be reflected;
  this does not substitute for PostgreSQL migration or drift verification.

Docker returned permission denied on the sandbox's Docker socket. A host runner is prepared:

```bash
cd "/Volumes/Samsung SSD/Project/RepoPilot"
bash apps/api/evaluation/run-5b1-checks.sh
```

It creates a uniquely named disposable container and empty database, fails on skipped selected
tests, runs the security fixture, upgrades an isolated database from `0009` to `0010` while
checking a pre-existing fixture, runs Alembic drift checks and retains its new container and
volume. The separately approval-gated committed-source snapshot evaluation is excluded.
The user's first host run reported **314 passed, 1 skipped**: the existing PostgreSQL
legacy-migration test's database-prefix guard did not yet recognize the new 5B1 disposable
name. The runner intentionally stopped before its security, Ruff and Alembic steps. The
guard has since been extended for this disposable prefix, and the legacy test now checks
that an existing mock report survives 0010. The user's next output reported successful
security, preservation, 0010 and drift checks, but the pasted pytest count reads
`16 passed`; its full count was not established from that output. A further
PostgreSQL-only actual-mode fake-transport test and a minimum collection guard were then
added. The user subsequently reported the final runner result: **317 passed in 33.12s**,
security fixture **33/33**, Ruff passing, the 0009 fixture preserved by the 0010 upgrade,
`0010 (head)`, and no new Alembic upgrade operations. The final success marker is printed
only after the runner verifies an empty dedicated database, at least 300 selected tests
and zero skips. The retained container was `repopilot-5b1-checks-414af65032edcbf5`.
The separately approval-gated committed-source snapshot test remained intentionally excluded.
The normal local application database has not received `0010`.

The proposed one-request experiment, rate assumptions, $10 total cap and $5.815551 maximum
reservation, accounting limitations and further approval requirements are detailed in
`docs/sprint-5b-provider-plan.md`. The existing 4F runner remains mock-only, and an
isolated real-model evaluation harness must be prepared and reviewed before any paid
experiment. Neither the adapter's fake transport tests nor the mock evaluations measure
real-model reasoning quality.

### Sprint 5B2A isolated provider evaluation — 2026-10-31

**SPRINT 5B2A VERIFIED LOCALLY — FAKE-TRANSPORT SCOPE.** The evaluation prepares a partial disposable snapshot
from the committed `signature_exact` source, runs the existing retrieval and report
workflow with a fake GitHub client and `httpx.MockTransport`, and records a simulated
ledger reservation and a metadata-only request preview. It has no real-provider execution
mode. The official pricing and provider-contract review found that the earlier adapter
could inherit a project-selected service tier. It now explicitly requests the standard
tier and 30-minute cache lifetime and holds the reservation for inconsistent response
metadata. Refusal and incomplete-response handling and related regressions were added.

The then-uncommitted working tree passed **322 backend tests with 17 PostgreSQL-only
skips** on SQLite, the **33/33** synthetic adversarial fixture, Ruff and
`git diff --check`. Frontend regression checks passed **54 tests**, TypeScript and
ESLint; no frontend files were changed for this checkpoint. A newly created temporary
SQLite database upgraded to `0010` and
reported no Alembic drift, with existing SQLite expression-index reflection warnings.
SQLite does not verify PostgreSQL row locks, the PostgreSQL migration or the real keyword
retrieval path.

Docker remains inaccessible from this sandbox, but the user supplied a successful host run
and its retained log and artifacts. The log confirms an empty, newly created database
`repopilot_5b2a_4f6d42946ddad6d4`, run `4f6d42946ddad6d4`, **338 selected PostgreSQL
tests passed with zero skips**, **33/33** adversarial checks, Ruff, and Alembic `0010 (head)`
without drift. The pytest summary has exit code 0 and all **40/40** recorded provider cases
passed, including the 17 cases required by the runner. The separately gated 4F
committed-source benchmark test was intentionally excluded. The final log records successful
evaluation completion; the user separately reported overall script exit status 0.

The log, report and preview identify snapshot `505277be-9f2e-45a4-900e-cf528a9052c2` in
that disposable database. The partial synthetic snapshot is pinned to commit
`30705da4c044192cab4ac207e253ab8e8a1bd100`; local Git and the dataset confirm its source
tree, blob and `valid_signature` label at lines 6–8. It returned two evidence records and
validated **1/1** report references. It omits 104 eligible files and is not a retrieval
quality benchmark. The report records one fake HTTP request, one worker attempt, a
simulated **$5.815551** reservation and no actual provider cost. Empty-evidence abstention
is covered by separate tests, not by this two-evidence evaluation.

The run recorded evaluator HEAD `bcea57041721c895659ed38c398438ea91519d70` while its
implementation was still uncommitted. Those changes were subsequently committed as
`0ccf57a349c553cca72ef112166ffb7c4c9fc4ef`; at reconciliation all **12/12** recorded
implementation fingerprints matched that committed tree. Sprint 5B2B subsequently changed
the Git reader, evaluation harness, adapter and ledger, so this historical run does not
verify the later code. Other supporting files were not fingerprinted, so the saved artifacts do not
independently establish byte-for-byte identity for every file used by the run. The preview
and report contain the same request-projection hash, but the omitted raw projection cannot
be independently rehashed from these metadata-only artifacts. The retained log and reports
are under `apps/api/evaluation/5b2a-4f6d42946ddad6d4*`.

**SPRINT 5B2B NOT YET VERIFIED** for a real-model experiment. The later checkpoint adds an
approval-bound executor; its fake-transport PostgreSQL verification is recorded below, while
independent security review and actual provider behavior remain pending.
The separate draft in `docs/sprint-5b2b-first-experiment-approval.md` records the proposed bounds
and remaining prerequisites. No real model call, paid embedding call, live job,
normal-database migration or repository reindex was made for this evaluation. See
`docs/sprint-5b2a-evaluation.md` for the pricing audit and safety limitations.

### Sprint 5B2B checkpoint 1 — executor and approval preflight

**SPRINT 5B2B CHECKPOINT 1 VERIFIED LOCALLY — DRY-RUN AND FAKE-TRANSPORT SCOPE.** The executor creates an offline disclosure
preview and supports an isolated simulated approval and fake HTTP transport. Approval is bound
to the fixture, commit, snapshot, experiment, report job, request bytes and manifest; the
existing ledger consumes the one-use approval in the same transaction as its send marker.
Ordinary report workers cannot use live transport. The separately invoked actual path requires
its own recorded approval, isolated PostgreSQL target, server-side gates and key; it has not
been enabled or exercised with live transport.

The local SQLite backend suite reported **358 passed, 19 skipped**; those skips include the
new PostgreSQL approval races and existing PostgreSQL concurrency tests. The 33-case
adversarial fixture passed; an earlier focused executor, report-model and adversarial regression
run reported **103 passed, 2 PostgreSQL-only skips** before the module-entry fix, and those
tests were included in the subsequent full run. Ruff, shell syntax and `git diff --check`
passed. A newly created
temporary SQLite database upgraded from `0010` to `0011`, preserved a fixture row, contained
the approval fields and reported no Alembic drift. SQLite does not establish PostgreSQL
migration correctness. No frontend code changed. The normal application database was not
migrated.

The fake-only host script `apps/api/evaluation/run-5b2b-checks.sh` creates a uniquely named
disposable PostgreSQL container and empty database, runs the selected backend suite with
mandatory fake-executor and locking cases and no skips, checks the security fixture, Ruff,
upgrade and drift, and retains its container and volume. It records and compares a combined
fingerprint of the API Python source, migrations, tests, runner and two fixture datasets
before and after the run. The current working-tree fingerprint is
`23ab78b696013fc7fc2c4651160996624a848a88c528e6beaae6e37af8f6aa64` over 124 files;
it does not fingerprint installed dependencies or documentation. It excludes the separately gated
4F committed-source benchmark. Docker access from this sandbox returned permission denied,
but the retained host log `apps/api/evaluation/5b2b-35c39ab76d883faa.log` records a
successful run in newly created, confirmed-empty database `repopilot_5b2b_35c39ab76d883faa`:
**376 PostgreSQL tests passed**, the **33/33** adversarial fixture passed, Ruff passed, and
Alembic reached **0011 (head)** with no drift. The runner's final success marker requires
zero test skips and its named executor, approval-race and budget-race cases to pass. The
before and after fingerprints both matched the then-current 124-file source fingerprint above.
The log records completion and retains the container and volume; it does not independently
record the shell's final exit status.

The source disclosure template is `apps/api/evaluation/5b2b-disclosure-template.json`; its
IDs are placeholders and cannot authorize a future request. The offline command writes the
full sanitized request and manifest to a temporary directory with mode `0700` and files with
mode `0600`. See `docs/sprint-5b2b-first-experiment-approval.md` for the exact review and
approval steps and the unresolved security and billing risks. The tests include an isolated
actual-mode ledger simulation with fake transport. No real-provider request, paid embedding
call, live paid experiment, normal-database migration or live job was made.

### Sprint 5B2B checkpoint 2 — security and exact-input review

**SPRINT 5B2B CHECKPOINT 2 NOT YET VERIFIED.** The checkpoint 1 run above predates the
checkpoint 2 modifications. This sandbox cannot access the Docker socket, but the user ran
`apps/api/evaluation/run-5b2b-readiness.sh` on the host. Its retained log and screenshot show
**222 selected PostgreSQL tests passed with zero skips**, including the fake approval and
reservation concurrency guards, **33/33** adversarial checks, Ruff, and Alembic
`0011 (head)` with no drift. A final success marker was recorded; a separate shell exit-code
value was not captured. The then-current 128-file API/test/migration/fixture fingerprint
`ff00ca67caf579027c77442542dd4efd98125e884258934d768d768903671f47` independently matches
the before and after values in the log. Installed dependencies and docs are not fingerprinted.
The runner retained its newly created container and volume; the normal application database
was not its target.

The checkpoint 2 local focused suite reported **214 passed, 8 PostgreSQL-dependent skips**;
Ruff, shell syntax, `git diff --check`, and the **33/33** adversarial fixture passed. These
SQLite results do not demonstrate PostgreSQL row locking. No frontend files changed. No
provider or paid embedding request was made. The historical checkpoint 1 host suite reported
376 selected PostgreSQL passes and a success marker with no skips; the shell exit code was
not independently captured.

The exact staged `signature_exact` request reviewed the specified committed 322-byte source
blob and both source ranges. Its synthetic database is `repopilot_5b2b_b3fa0088237c0c7a`,
snapshot `afa6679c-4822-44c2-bfd9-3ac635068945`, investigation
`98678679-7c39-4cca-9ae2-f516542e350a`, report job
`91fa2b4b-6695-4a12-bad9-63118cd36ae1` and simulated experiment
`e707c7d9-203c-45df-92f6-9722316eb317`. It has two evidence items, no paid approval,
reservation, provider request or report. The canonical request and manifest SHA-256 values
are `9211ff97ef966d0d648d3d175a1808116c576e7cd80adee746fed82a8a2700b5` and
`87f82f93e7338fe567cd43270b163dc268ad2e47326da8968f78977da5a46b0b`. The private files
were independently re-read, reconstructed, rehashed and their permissions checked against
the same run's sanitized artifact and log. The synthetic experiment expires at
`2026-11-01T03:20:26.146556+00:00`; after expiry a fresh run and review are needed. The
sanitized [disclosure review](sprint-5b2b-disclosure-review.md) records source and excerpt
hashes, request fields, pattern-screen results and limitations. The executor now requires
additional operator acknowledgements for source screening and account pricing before it
records an actual approval. Those acknowledgements are attestations, not proof of either.
Inconsistent usage metadata retains the conservative reservation, and narrowly filtered
provider events permit correlation without logging prompts, headers or credentials. An
unexpected upstream request-ID format is omitted. A positive paid-approval execution has
not been exercised, because creating or consuming a paid approval is prohibited here.

The selected fake-transport tests cover successful grounded publication and duplicate
rejection; missing, expired and mismatched approvals; modified request or manifest; budget
exhaustion and concurrent reservations; lease takeover before send and crash after the send
marker; timeouts, refusal, incomplete or malformed output; missing or inconsistent usage,
incorrect model/tier/cache metadata; foreign citations, cross-tenant evidence and revoked
access. The selected PostgreSQL race checks exercise atomic simulated-approval consumption
with the ledger marker. Unknown billing remains reserved. The runner's Python socket fence
and injected HTTP transport are test controls rather than an operating-system network sandbox.

The fixed request, manifest, tenant, investigation, snapshot and model are checked before
the fake provider sends; a one-use approval and ledger send marker share a transaction.
That provided replay and concurrency controls in those fake-transport tests, not a
guarantee against administrative database/code changes, provider invoice differences or a
revocation racing a network request. The synthetic fixture uses a fake GitHub identity; it
does not test current live GitHub access. Provider-internal processing and retention remain
outside the request-body review. A valid citation proves structural grounding, not that a
hypothesis is correct.

On 2026-11-01 the reviewed public pricing supports a **$5.815551** local reservation only
under the documented 30-minute cache, long-context and one 10% allowance assumptions. Taking
the rounded reservation as the base, one *additional* 10% uplift yields $6.3971061, and two
additional compounded uplifts yield $7.03681671; both exceed the $6 per-investigation cap.
Those are hypothetical stress scenarios, not a claim that these fees apply or stack.
Account-specific billing, model access, endpoint policy and any
stacking remain unconfirmed; execution must remain blocked if they cannot be justified.
The [draft approval packet](sprint-5b2b-first-experiment-approval.md) lists the separately
authorized actions, private review, shutdown and uncertain-billing procedure. Real-model
reasoning quality and provider billing accuracy remain unmeasured.

### Sprint 5B2B checkpoint 2B — pricing and project access gate

**SPRINT 5B2B CHECKPOINT 2 — BLOCKED.** Public documentation was rechecked on 2026-11-01;
project-specific model access, billing and fee applicability remain unknown. The application
now unconditionally rejects recording an actual approval and entering the live executor with
`pricing_unverified`; an acknowledgement or API key alone cannot clear this code gate. The
send-marker path repeats the gate and checks a stress-adjusted reservation against both caps.
This is deliberately not a usable paid-execution configuration.

The corrected microdollar calculation starts from the existing $5.815551 reservation,
which already contains one 10% allowance. One and two **additional** 10% stress uplifts are
$6.3971061 and $7.03681671, or $6.397107 and $7.036817 rounded up to whole microdollars.
The maximum whole-microdollar base under a $6 cap after two additional uplifts is $4.958677.
Neither additional uplift is asserted to be applicable to this account. The 30-minute cache
write uses a total 1.25× input rate rather than a separate charge on top of input pricing.

The historical staged request was independently rehashed at **3,826 canonical bytes**,
including 445 instruction bytes and a 1,215-byte canonical schema; it contains two evidence
items. The adapter now rejects canonical bodies above **8,192 bytes** before sending. A byte
limit and bytes/4 heuristic do not verify the provider's input token count, which can include
formatting and schema overhead. Therefore the ledger still reserves the full 1,050,000-token
window, and the current $5.815551 reservation does not satisfy the added stress gate. An
illustrative 16,384-token input and 2,048-token output would yield a $0.130663 base and
$0.158103 after two additional stress uplifts, but that input bound is not verified or
implemented and those numbers cannot authorize execution.

At `2026-11-01T02:41:06Z` the staged experiment had not yet expired. Its documented expiry was
`2026-11-01T03:20:26.146556+00:00`; it was expired when checked again after `03:23Z`. Its
manifest is also invalid under the changed byte limit and pricing gate, so do not reuse or
revive it. The old evidence and private files are
retained. A later approved verification must generate fresh identifiers, request and manifest
hashes, source review, pricing evidence and expiry. No new staged experiment was created.

The [approval packet](sprint-5b2b-first-experiment-approval.md) now includes a private,
non-API account and project checklist. If account terms or a safe, request-bound input-token
upper limit cannot be independently established, pricing approval remains blocked. The
provider input-token counting endpoint would itself be an external request and disclosure and
was not called. A new durable-ledger policy and its own disposable PostgreSQL regression
will be required before any paid approval can be considered.

Local SQLite verification after the checkpoint 2B changes: **394 passed, 20 skipped**;
the skips include PostgreSQL-specific tests. The **33/33** adversarial fixture, Ruff, shell
syntax and `git diff --check` passed. A focused run of the new pricing, executor and provider
tests reported **99 passed, 6 PostgreSQL-dependent skips**. The historical staged request
was rehashed and its old manifest was rejected by the current policy without accessing its
database. The earlier 222-test PostgreSQL run predates these changes and is not evidence for
the new gates. Docker access in the sandbox is denied, so the user ran the fake-only host
script `apps/api/evaluation/run-5b2b-pricing-checks.sh` against the confirmed-empty disposable
database `repopilot_5b2b_845d50be264c481f`. Its retained
[log](../apps/api/evaluation/5b2b-pricing-845d50be264c481f.log) records **239 passed**,
the **33/33** security fixture, Ruff, Alembic **0011 (head)** and no drift, followed by the
success marker. The runner requires zero skips and its named pricing, approval and PostgreSQL
locking cases to pass. The before/after fingerprint
`0defb35e5ff2f5fbea6381b5316927ebcf5fea56a0d370256bd35b78eef5b685` covers 128 files and
matched the independently recomputed source fingerprint before checkpoint 2C; it excludes documentation and
installed dependencies. The user reported overall script exit status **0**; the log itself
does not separately capture that numeric shell status. The container and volume were retained.

**PostgreSQL pricing-regression blocker: RESOLVED** for that tested source. Checkpoint 2
remains **BLOCKED** on account-specific pricing/model access and a verified request-bound
token budget. No paid provider, token-count endpoint, paid approval, normal database
migration or new staged experiment was used in this checkpoint. Any future implementation
change requires its own appropriate tests and fingerprint.

The focused [request-bound token-budget plan](sprint-5b2b-token-budget-plan.md) describes
the subsequent fake-only count implementation and the remaining ledger and provider-contract
work needed to use a verified bound. A real count would be a separate external request and
disclosure, requiring separate authorization. Account pricing, a reliable count-to-generation
bound, model identity stability and the count endpoint's billing/retention terms remain
unverified; the existing live gate stays closed.

### Sprint 5B2B checkpoint 2C — simulated token counting

**SPRINT 5B2B CHECKPOINT 2C VERIFIED LOCALLY — FAKE-TOKEN-COUNT SCOPE.** A fake-only input-count projection,
separate simulated one-use approval, tenant/snapshot/request binding and generation preflight
have been implemented. The persisted count state is restricted to simulated mode by additive
migration `0012`; the ordinary application database has not been migrated. The count adapter
accepts only an injected `httpx.MockTransport` and an isolated test database. It marks a fake
send durably before transport, rejects replay and malformed or over-limit results, and keeps an
uncertain outcome non-retryable. A separate simulated generation approval is still required.
When a count is selected, the generation send-marker transaction rechecks the current source,
authorization, request and count binding before consuming the approval. The original
full-window $5.815551 generation reservation remains unchanged.

OpenAI's [input-token count reference](https://developers.openai.com/api/reference/resources/responses/subresources/input_tokens/methods/count)
and [token-counting guide](https://developers.openai.com/api/docs/guides/token-counting) were
reviewed on 2026-11-01. The count response does not establish a pinned resolved model revision
or guaranteed billed generation input; the reviewed request has no suitable documented
provider-enforced input-token maximum. Fees and retention for an actual count are not
established. Any real count would be a separate external disclosure and require a separate
approval and justified fee policy. No real count, real generation, paid approval or new live
staging was performed. Count-to-generation stability, account pricing and project access remain
blockers for Sprint 5B2B real execution.

The sandbox could not reach the local Docker daemon. The reviewed
`apps/api/evaluation/run-5b2c-checks.sh` creates and retains a new disposable PostgreSQL
container, checks the database identity and empty schema, enforces named cases and zero skips,
runs the adversarial fixture and migration/drift checks, and records a source fingerprint and
final exit status in a run-specific log. Python socket fencing is not an OS sandbox.

On the updated local source, the full SQLite-backed backend suite reported **463 passed,
21 skipped**; the skips include PostgreSQL-only cases and are not concurrency evidence. The
focused fake-count suite reported **65 passed, 1 PostgreSQL-only skip**. The adversarial
fixture reported **33/33**, dataset SHA-256
`b7ba2f58a21d3c349198ccdaf2dfbfed968a7e384618cef7530c86fc44c020e6`. Ruff, the host
runner's shell syntax and `git diff --check` passed. A new disposable SQLite database reached
Alembic `0012`, contained the simulated count table and reported no drift; that check does not
establish PostgreSQL migration compatibility. The earlier checkpoint 2B PostgreSQL results do
not verify the later code or migration.

The user subsequently ran the script in Mac Terminal. Its retained
[host log](../apps/api/evaluation/5b2c-e1593aaca7524a85.log) records run
`e1593aaca7524a85`, newly created disposable container `repopilot-5b2c-e1593aaca7524a85`
and confirmed-empty database `repopilot_5b2b_e1593aaca7524a85`. It reports **309 passed**,
with the runner requiring zero skips and its named count-approval, generation-marker,
reservation-concurrency and legacy-migration cases to pass. The **33/33** adversarial
fixture, Ruff, Alembic **0012 (head)** and no drift are recorded, followed by success and
**script final exit status 0**. The before/after fingerprint
`bd002c874e4370563e6c775db07cc1d8b1bcedf37b6bba690f5979b52cb274c9` covers 131 files and
matched the independently recomputed fingerprint before the 5B2D test and runner changes; documentation and installed
dependencies are outside that fingerprint. The runner records Git HEAD
`0ccf57a349c553cca72ef112166ffb7c4c9fc4ef`, but the fingerprint includes uncommitted files
and must not be interpreted as verification of that commit alone. The container and volume
were retained. An earlier sandbox invocation `62f1e9e2d10223b2` exited 1 before creating a
database because the Docker daemon was inaccessible; it does not represent the host run.

These results verify simulated counting and the selected database/security regressions only.
They do not establish real OpenAI model access, count fees, a provider-enforced input bound,
real-model reasoning quality or invoice accuracy. Sprint 5B2B real-model execution remains
**NOT YET VERIFIED** and blocked pending separate approvals and resolution of those issues.

### Sprint 5B2D — token-budget policy and account review

**SPRINT 5B2D VERIFIED LOCALLY — FORMAL POLICY AND FAKE-TRANSPORT SCOPE.** The audit
confirmed that the **optional simulated** count path binds generation and count-projection
hashes to the tenant, source snapshot and commit, model, synthetic account/project, manifest,
pricing revision, expiry and limits. The full generation hash covers instructions, input,
schema, cache options, output limit, disabled truncation and other accepted generation fields.
At the simulated send marker, current local access and the exact request are rechecked before
the distinct generation approval is consumed. The existing server-side evidence validation
still controls report publication. At that checkpoint the count was not a mandatory
real-generation preflight: `execute_fake` could run without one, `execute_live` did not accept
one, and migration `0012` permitted simulated count records only. The actual-pricing gate
still rejects real approval and execution. Checkpoint 5B2E adds explicit account/project
binding and a separate, blocked external-count path; it does not establish project access.

The [formal proposed policy](sprint-5b2b-token-budget-plan.md#sprint-5b2d-proposed-fail-closed-policy)
requires independently verified account pricing and count-call fees, separate approval for the
count disclosure, a matching nonexpired provider count and defensible input allowance, an
unchanged canonical request, and an atomic ledger reservation and separate generation approval.
At that checkpoint no implementation made a real count mandatory or reduced the ledger reservation;
checkpoint 5B2E adds a blocked external-count preflight without reducing the reservation.
The reviewed offline placeholder request contains both sanitized source ranges, its structured
schema and **3,816 canonical bytes**; this is not a token count. The 16,384-token input and
2,048-token output values are candidates only, and neither real input size nor report sufficiency
has been measured. Its placeholder hash is not an approval; the earlier staged run is expired.

On **2026-11-01**, the public [GPT-5.6 Terra model page](https://developers.openai.com/api/docs/models/gpt-5.6-terra)
listed standard input/output rates of **$2/$12 per million tokens** and a 2× input/1.5× output
long-context rate for prompts over 272,000 input tokens. The [prompt-caching guide](https://developers.openai.com/api/docs/guides/prompt-caching)
describes the 30-minute write rate as a total 1.25× input rate, not an added charge on top.
The [pricing page](https://developers.openai.com/api/docs/pricing) lists 10% regional and
FedRAMP endpoint uplifts under their conditions; project applicability and stacking are unknown.
The [token-counting guide](https://developers.openai.com/api/docs/guides/token-counting) says
the output limit includes non-visible tokens. Count-endpoint fees and account terms remain
unverified. No provider-side maximum input-token or invoice guarantee has been established.

The existing full-window reservation remains **$5.815551** under its documented assumptions.
Applying two additional hypothetical 10% stress uplifts gives **$7.036817**, exceeding the
proposed $6 investigation cap; this is not a claim that those uplifts stack. If a 16,384-token
input upper bound were independently justified, the same conservative rates and two additional
stress uplifts yield an illustrative **$0.158103** for generation. That illustration excludes
unknown count fees and other account-specific charges and is not an enforceable total ceiling.
No reservation has been reduced and no spending has been approved.

The updated local SQLite backend suite reported **477 passed, 22 skipped**; the focused new
fake-transport and arithmetic cases reported **14 passed, 1 PostgreSQL-only skip**. The
**33/33** adversarial fixture, Ruff, shell syntax and `git diff --check` passed. Docker access
from the sandbox returned permission denied. The user ran the extended
`apps/api/evaluation/run-5b2c-checks.sh` on the host. Its retained
[log](../apps/api/evaluation/5b2c-383e0af929ee80d2.log) records run `383e0af929ee80d2`,
new container `repopilot-5b2c-383e0af929ee80d2` and confirmed-empty disposable database
`repopilot_5b2b_383e0af929ee80d2`: **324 passed, zero skips**, the **33/33** adversarial
fixture, Ruff and Alembic **0012 (head)** without drift. Its guard requires the named 5B2D
request-mutation, expiry, overflow, duplicate-approval and PostgreSQL concurrent-generation
cases. The final exit status was **0**, and the container and volume were retained.

The before/after fingerprint
`11d1eb7789295c277c9e1ff54209cace62e3ff55617693a1c47fa484982e1916` covers 131 files and
matched the independently recomputed source fingerprint at the time of that run, before
the 5B2E source changes; it excludes documentation and installed dependencies. The log
records Git HEAD `0ccf57a349c553cca72ef112166ffb7c4c9fc4ef`,
but includes uncommitted files and is not evidence for that commit alone. The earlier 2C run
predates the added tests and runner changes. These tests verify the existing simulated path
and fail-closed gate, not an actual-count implementation or a real-provider spending ceiling.
No live count, generation, paid approval, staging or normal-database migration was performed.
Account and project review remains a private human task in the approval packet.

### Sprint 5B2E — provider count and generation preflight

**SPRINT 5B2E VERIFIED LOCALLY — FAKE-TRANSPORT INTEGRATION SCOPE.** A separate additive migration `0013` introduces an
external-origin count authorization and its fee reservation; the existing `0012` simulated
counts remain separate and cannot authorize the actual path. The provider count and separate
generation approval are bound to the reviewed request, projected count payload, tenant,
repository, source snapshot and commit, report job, fixture, model, hashed organization and
project, pricing and fee policies, manifest, token limits, service tier and cache settings.
Before the generation send marker, the worker rechecks access and request identities and
atomically consumes the provider count and generation approval with the existing ledger
marker. A direct actual-mode adapter call cannot bypass the approval-bound model even with a
mock transport. The one-shot executor has its own configuration gate and requires paid
background workers to remain disabled; actual count authorization and sending require
PostgreSQL.

The count sender records its one-use send marker before network I/O. An uncertain or invalid
result retains its fee reservation, which is included in the same experiment and investigation
totals as generation. The generation reservation remains **$5.815551**; the extra count fee
and any unverified charges are not assumed to be free. The current generation-pricing and
count-fee gates both fail closed, and the external-count switch defaults to disabled. The
candidate 16,384-token allowance has not been verified against a real provider response or
approved as a reduced spending bound. Two hypothetical additional 10% stress uplifts on the
existing reservation total **$7.036817**, exceeding the proposed $6 per-investigation cap;
this does not establish that the uplifts apply or stack.

The updated local SQLite-backed backend suite reported **537 passed, 22 skipped**; its
focused provider-count integration file reported **54 passed**. SQLite results do not
establish PostgreSQL row locking. Earlier suites had reported **530 passed, 22 skipped** and
**522 passed, 26 skipped** before the later approval-boundary and executor-gate changes.
The current runner-compatible fingerprint is
`5c3523ad8fa36e89d25846cfe3e2dcf5a0fd66e26296c669d2ce07fbec9b857c` over 133 files; it
does not cover documentation or installed dependencies.
The adversarial fixture reported **33/33**, SHA-256
`b7ba2f58a21d3c349198ccdaf2dfbfed968a7e384618cef7530c86fc44c020e6`. Ruff, shell syntax,
`git diff --check`, and an isolated SQLite upgrade to `0013` with no Alembic drift passed.
The SQLite migration preservation test also passed. The sandbox could not access Docker;
the 5B2D PostgreSQL run predates these source changes.

The user's first 5B2E host run, retained as
[0923d253fd6c203b](../apps/api/evaluation/5b2e-0923d253fd6c203b.log), confirmed a new empty
database and recorded **373 passed, zero skips**, **33/33** adversarial checks, Ruff, Alembic
`0013` without drift and exit status **0**. Its before/after fingerprint
`2122c5db35233099d85a9d7fb36399775324c4a4bb572c6ac397abf87cdb9ab2` covered 133 files.
That run predates the subsequent separation of the executor from the paid-background gate,
the explicit PostgreSQL requirement for actual count authorization, and the expanded count
sender tests. It is preserved as historical evidence and does not verify those later changes.

The user then ran the updated fake-only host runner. Its retained
[log](../apps/api/evaluation/5b2e-8d8ccdd6c8a29bc9.log) records run `8d8ccdd6c8a29bc9`,
fresh container `repopilot-5b2e-8d8ccdd6c8a29bc9`, and confirmed-empty disposable database
`repopilot_5b2b_8d8ccdd6c8a29bc9`. The selected PostgreSQL suite reported **384 passed,
zero skips**; the runner's success guard required the named approval, count/generation
concurrency, fee-retention, replay, citation, reservation and migration-preservation cases.
It also recorded **33/33** adversarial checks, Ruff, Alembic **0013 (head)** without drift,
and final exit status **0**. The container and volume were retained.

The run's before/after fingerprint was
`5c3523ad8fa36e89d25846cfe3e2dcf5a0fd66e26296c669d2ce07fbec9b857c` over 133 files, matching
the independently recomputed fingerprint at the end of 5B2E, before later retrieval changes.
It includes the test runner, application
and test Python files, migrations and selected fixture/configuration files; documentation
and installed dependencies are outside its scope. The log records Git HEAD
`0ccf57a349c553cca72ef112166ffb7c4c9fc4ef`, but the fingerprint includes uncommitted source
and is not evidence for that commit alone.

The prepared `apps/api/evaluation/run-5b2e-checks.sh` creates a fresh, named disposable
PostgreSQL database, verifies its identity and empty schema, fences Python network access,
rejects real HTTP transports, requires named tests and zero skips, and records a source
fingerprint and exit status. Its synthetic PostgreSQL tests exercise an actual-shaped approval
and count only inside the disposable test database, with test-local pricing replacements,
synthetic credentials and `MockTransport`; these are not live approvals or provider results.
The Python fence is not an operating-system sandbox. No real count or generation request,
live approval, new live job, or normal-database migration was performed. Real-model execution remains **BLOCKED** pending
independent account and pricing review, a separately approved count disclosure, a valid
request-bound provider count and a separate generation approval.

### Sprint 5C1 — issue-to-code retrieval

**SPRINT 5C1 VERIFIED LOCALLY — 2026-11-02**, for the pinned synthetic benchmark and
scoped security regressions. Under explicit authorization, new disposable 4F fixture
`68ed7b3fd6171439` published snapshot `95751038-f44e-4715-b4bd-932e446f457b` for
commit `30705da4c044192cab4ac207e253ab8e8a1bd100` (104 files, 889 chunks). Paired run
`3d44ea7dbd159dd9` reproduced `terms-v1` Recall@1/3/5/10 **0.375/0.500/0.5625/0.625**,
MRR **0.5141**, nDCG@10 **0.5205** and measured production `terms-v2` **0.375/0.500/0.5625/0.7188**,
**0.5177**, **0.5469** on the same snapshot. Direct retrieval p50/p95 was **39.372/93.896 ms**
versus **82.396/124.066 ms**. Git-source checks passed for **226/226** and **298/298**
citations. The fixture's access and snapshot probes passed. Separate disposable PostgreSQL
regression `c92ea8e6468ed091` passed **586 tests**, **33/33** adversarial cases, Ruff,
Alembic `0013` and no drift, with matching pre/post fingerprints and exit 0. See the
[report](sprint-5c1-retrieval.md#authorized-paired-replay--2026-11-02) and
[regression log](../apps/api/evaluation/5c1-checks-c92ea8e6468ed091.log) for per-case
regressions, latency and benchmark limitations. No paid provider or normal application
database was used. The earlier pending statuses below document the preceding attempts.

**Host follow-up; SPRINT 5C1 NOT YET VERIFIED.** The user supplied a screenshot and retained
log for disposable regression `6da0508fe05c84e5`: **586 passed**, adversarial **33/33**,
Ruff passed, Alembic **0013 (head)** with no upgrade operations, matching source fingerprints
and exit 0. This includes the fixture-preparation code but excludes the separately gated
committed-source test. The paired replay was invoked with the example suffix and stopped
because its fixture report was missing; no paired metrics were produced. The instructions in
[the Sprint 5C1 report](sprint-5c1-retrieval.md#missing-fixture-recovery-and-replacement-preparation)
now prompt for the actual successful 4F fixture suffix after separate authorization.

**Host regression update; SPRINT 5C1 NOT YET VERIFIED.** User-provided output and the
retained `5c1-checks-5bd90a0e63d784ee.log` report **585 passed**, adversarial **33/33**,
Ruff passed, Alembic **0013 (head)** with no upgrade operations, matching source fingerprints,
and script exit 0 on the newly isolated database. This run excludes the separately gated
committed-source test. The user also reported that the original 4F container was unavailable;
the image was initially absent but the subsequent successful regression confirms it was
available at that time. Recovery is unconfirmed and saved reports do not restore a database.
Rebuild and paired replay preparation, its explicit authorization gate, commands and caveats
are in [the Sprint 5C1 report](sprint-5c1-retrieval.md#missing-fixture-recovery-and-replacement-preparation).
The successful run predates those changes; rerun verification against the final files.
Preparation checks in this environment passed Python syntax parsing, shell syntax and
`git diff --check`; invoking the fixture script without the approval flag exited before
Docker with its separate-approval message. The replacement and its added regression tests
have not been executed here because the project Python interpreter remains unavailable.

**Follow-up: SPRINT 5C1 NOT YET VERIFIED.** The production replay was wired directly to the
worker's versioned query builder, with a regression test, and the host scripts now diagnose a
missing interpreter. In this environment both project virtual environments link to an
unavailable Homebrew Python 3.14; system Python lacks pytest and SQLAlchemy. Python syntax
parsing, shell syntax and `git diff --check` passed. Docker inspection was denied in the
sandbox; an escalated production replay stopped before Docker at the missing interpreter.
No new benchmark, PostgreSQL, adversarial, backend suite or Ruff result is claimed. Exact
host commands, changed files and remaining gates are in
[the Sprint 5C1 report](sprint-5c1-retrieval.md#follow-up-verification-attempt).

**SPRINT 5C1 NOT YET VERIFIED.** The pre-change pipeline and historical 4F weaknesses are
documented in [sprint-5c1-retrieval.md](sprint-5c1-retrieval.md). A local read-only Git check
verified the unchanged pinned fixture's **23 labels across 16 scored cases**, with three
unscored cases. Rescoring the saved historical 4F evidence reproduced Recall@1/3/5/10 of
**0.375/0.500/0.5625/0.625**, MRR **0.514137** and nDCG@10 **0.520538**; this is not a
current-code PostgreSQL baseline.

The current sandbox cannot access Docker. A new read-only runner targets only the previously
retained 4F disposable snapshot and requires its expected database, snapshot, Git commit and
read-only transaction. It checks every returned citation against local Git objects and records
new run-specific artifacts. It does not create a snapshot or investigation job, access the
normal application database or call an external provider. The separate approval gate for
creating a new committed-source snapshot remains in place. The user ran the read-only replay;
artifacts [JSON](../apps/api/evaluation/5c1-baseline-eda70e4b43a14eb6.json) and
[Markdown](../apps/api/evaluation/5c1-baseline-eda70e4b43a14eb6.md) identify retained disposable
database `repopilot_4f_disposable_4f762b71ae8d9569`, snapshot
`1a8e0d9e-1cf1-4e0a-9cac-f8ced23f1694` and the unchanged pinned commit and dataset. Current
`terms-v1` direct retrieval reproduced **0.375/0.500/0.5625/0.625** recall, **0.514137** MRR,
**0.520538** nDCG@10, 12/16 labeled top-10 hits, and **226/226** citations checked against
local committed source. Latency p50/p95 was **54.520/97.672 ms**, direct retrieval only.
The stored implementation hashes matched the pre-change code. At that point no candidate comparison had been run.

At this preparation stage the local SQLite-backed backend suite reported **553 passed,
22 PostgreSQL-dependent skips**; focused replay/comparison and existing evaluation tests
reported **33 passed** at that stage. After adding evaluation-only candidate queries, the
focused replay/comparison/evaluation tests reported **37 passed**, and the full local suite
reported **557 passed, 22 PostgreSQL-dependent skips**. After the versioned retrieval change,
the full local suite reported **562 passed, 23 PostgreSQL-dependent skips**. The adversarial fixture reported **33/33**, Ruff, shell syntax and
`git diff --check` passed. The new disposable PostgreSQL regression runner is prepared but
has not been executed, so no PostgreSQL result is claimed for this work.

The user ran three read-only body-query experiments as run `1fdf3b79925eaede` on the same
snapshot. Plain body expansion kept Recall@10 at **0.6250** but reduced MRR to **0.4898**;
generic-identifier filtering raised Recall@10 to **0.6562** while reducing Recall@1 to
**0.3438** and MRR to **0.4742**; body-first had Recall@10 **0.6562** and MRR **0.4922**.
The respective returned citation counts were **298/298**, **288/288** and **288/288** checked
against local Git source. An offline rerank of the recorded plain-body candidates preserved
the first four baseline results and used symbol overlap for the remainder; run
`10c892705cc26aca` measured Recall@1/3/5/10 **0.3750/0.5000/0.5625/0.7188**, MRR **0.5177**,
nDCG@10 **0.5469**, and 13/16 cases with a labeled top-ten hit. The snapshot-publication
label appeared at rank 10, while the incomplete-tree label fell from rank 7 to rank 10.
This is a same-dataset exploratory selection and may overfit.

`terms-v2` now implements the selected bounded query expansion and protected symbol rerank;
`terms-v1` remains available for earlier jobs. The observed candidate p50/p95
**77.391/137.332 ms** is inherited from direct plain-body retrieval and excludes reranking;
it is not yet a direct production-strategy measurement. A new same-snapshot `terms-v2` replay
and disposable PostgreSQL regression run are still required before verification.
An offline parity check confirmed that the production `terms-v2` query builder and shared
reranker reproduce the recorded exploratory candidate order and query hashes for all 19 cases.
The local frontend regression suite reported **54 passed**, and TypeScript and ESLint passed
using Node 24.22.0. No frontend or proxy code changed for this checkpoint.

# RepoPilot 2.0 parser foundation — 2026-11-05

An isolated, non-integrated language analysis module was added; see
[the assessment](repopilot-2-assessment.md) for its fixture scope and the
remaining implementation and security gates. Local Tree-sitter grammar
packages were installed only in a temporary directory. No live repository,
application database, model weights, or job was changed. Focused tests with
those temporary parsers passed; the complete multilingual indexing workflow,
real embeddings, reproducible diagnosis, and automated repair remain unverified
and unavailable. Existing verification records above are preserved.

With temporary grammars present, the focused parser, Python chunking, collection
and retrieval-evaluation checks passed (38 tests). Ruff, the frontend's 72 tests,
TypeScript, ESLint, production build, and `git diff --check` passed. The broader
disposable PostgreSQL run did not pass: 627 tests passed, 10 optional-parser
cases skipped, and `test_fixture_workflow_with_fake_sqlite_retrieval` failed
because the existing provider harness accepts revisions only through 0013.
That run stopped before its migration checks. Separately, an initially empty
database in the same disposable container upgraded to 0014 and `alembic check`
reported no pending operations. The adversarial report fixture passed 33/33.
These results do not validate RepoPilot 2.0 end to end.

## RepoPilot 2.0 Step 1 — multilingual indexing, 2026-11-05

The production index path now supports explicitly opted-in multilingual jobs;
Python-only remains the default. See [the assessment](repopilot-2-assessment.md)
for scope, grammar versions, migration 0015 and language limitations. The prior
provider-harness failure was caused by its revision allowlist ending at 0013;
the guard now also accepts the verified additive revisions 0014 and 0015, and
the formerly failing test passed.

With uv 0.13.6, a fresh temporary environment installed the updated lock with
`uv sync --locked`. A copy of `run-5c1-checks.sh` using that environment's
Python, Ruff and Alembic created disposable PostgreSQL container
`repopilot-5c1-checks-00e91fea4ef1d5ff` and database
`repopilot_5b2b_00e91fea4ef1d5ff`. The final run passed **681 tests with no skips**,
including mixed-language PostgreSQL search/citations, job retry, authorization,
evidence/report and historical migration checks; the adversarial fixture passed
**33/33**. Alembic upgraded the fresh disposable database to **0015** and
reported **no schema drift**. The script's source fingerprints matched.

The standalone runner excludes `test_investigation_evaluation_pg.py`. That test
was run separately and **passed 1/1** against a verified empty disposable
database (`repopilot_5b2b_37e7b31fd6e44f09`) in an earlier disposable container.
It read a pinned local Git commit into a newly seeded fake `alice/public`
repository and used fake GitHub access; it did not reindex any enrolled
application repository. The final focused SQLite/locked-environment run passed
92 tests with 5 PostgreSQL-only skips; those PostgreSQL tests ran in the disposable
regression. Frontend tests passed 72/72, TypeScript and ESLint passed, and Ruff
and `git diff --check` passed. No local application database or enrolled
repository was modified.

## RepoPilot 2.0 Step 2A — local vector infrastructure, 2026-11-05

The opt-in ONNX adapter, vector identity checks and offline held-out evaluator
are described in [vector-search-foundation.md](vector-search-foundation.md).
No real model weights were downloaded or evaluated. A small synthetic ONNX
graph and deterministic vectors were used for mechanics only.

The focused local suite passed **44 tests**, with **5 PostgreSQL-only skips**.
The final network-fenced PostgreSQL run used disposable container
`repopilot-5c1-checks-abc0f9804c104d74` and dedicated database
`repopilot_5b2b_abc0f9804c104d74`. It passed **254 tests with no skips**,
including controlled local-provider jobs, pgvector ordering and integrity,
concurrent active-job uniqueness, tenant/revocation, migration preservation,
existing retrieval/evidence/report regressions and adversarial workflow tests.
The separate adversarial report fixture passed **33/33**. Alembic upgraded the
empty disposable database to **0016** and reported **no schema drift**; test
source fingerprints matched (`c95aad99fbf2e0f4a37309085e707d4820ba16d0d24d747781ae829574735fff`).
The held-out evaluator checked forged citation paths, ranges and snippets against
pinned local Git source, and its offline JSON command refused an existing output.
The run log is [5c1-checks-abc0f9804c104d74.log](../apps/api/evaluation/5c1-checks-abc0f9804c104d74.log).
Ruff and `git diff --check` passed. The optional
runtime libraries were installed in a temporary environment from the lockfile;
frontend files were not changed in this step, so frontend tests were not rerun.

No real semantic relevance, real-model latency, Apple Silicon model inference,
HNSW recall, or browser acceptance is claimed. No normal application database,
source snapshot, repository, investigation or report was modified.

## RepoPilot 2.0 Step 2B — CodeRankEmbed preparation, 2026-11-05

At this preparation checkpoint, public metadata was read for the selected export
and upstream model; no model weights, tokenizer files, remote model code or
evaluation datasets had been downloaded. At that time the export's model LFS
SHA-256 was published, but its tokenizer SHA-256 and the precise upstream
revision used by the exporter had not been verified.
The export and observed upstream tokenizer Git blob IDs differ. See the
[artifact review](vector-search-foundation.md#step-2b--coderankembed-artifact-review)
for exact metadata, the proposed destination, and evaluation blockers.

The local focused run passed **37 tests**, with **5 PostgreSQL-only skips**. A
subsequent network-fenced run against fresh disposable container
`repopilot-5c1-checks-20dee3b60f67687f` and database
`repopilot_5b2b_20dee3b60f67687f` passed **257 tests with no skips**. These
included a 768-dimensional synthetic ONNX graph, CLS and normalization checks,
prefix and tokenizer validation, deterministic repeated synthetic inference,
cache identity, exact vector and hybrid search, tenant/revocation and citation
regressions. The adversarial report fixture passed **33/33**. Alembic upgraded
the disposable database to **0016** with no detected schema drift; the test
source fingerprints matched. Ruff and `git diff --check` passed. The
[run log](../apps/api/evaluation/5c1-checks-20dee3b60f67687f.log) records the
results; the disposable container and volume were retained.

These are engineering tests with synthetic vectors and a synthetic graph, not
real CodeRankEmbed inference or retrieval-quality evaluation. The standalone
search endpoint does not provide the complete `terms-v2` investigation ranking;
a reviewed paired-capture procedure and independently labeled held-out data
are still needed. No application database, enrolled repository or normal
application service was modified or restarted during this step.

## RepoPilot 2.0 Step 2B — tokenizer-only verification, 2026-11-05

With separate tokenizer-only approval, `tokenizer.json` was downloaded from
`https://huggingface.co/zuliaio/coderankembed-onnx/resolve/72d8b338380c0b83d02b1e38b40b7b778c1c8703/tokenizer.json`
to the private artifact directory recorded in the
[artifact review](vector-search-foundation.md#step-2b--coderankembed-artifact-review).
The final file is 711,650 bytes with mode `0600`. `git hash-object --no-filters`
returned the expected Git blob ID `a8472b8cccbf1668d306ec32780fd096b4a00bfb`;
`shasum -a 256` returned
`ea725c60b9022a7a491ffc348b5622a199853c806d625f673d0e2ebf1c3b5312`.
JSON structure checks passed for the WordPiece vocabulary, token metadata and
expected special-token IDs. The calculated SHA-256 fingerprints the downloaded
bytes; it was not an independently published tokenizer checksum.

At that checkpoint, no model weights had been downloaded and no real-model
inference or embeddings had been run. The export's precise upstream model revision
and parity remain unverified, so the full artifact manifest is still incomplete.

## RepoPilot 2.0 Step 2B — ONNX download verification, 2026-11-05

With separate download-only approval, `model.onnx` was downloaded from
`https://huggingface.co/zuliaio/coderankembed-onnx/resolve/72d8b338380c0b83d02b1e38b40b7b778c1c8703/model.onnx`
to the private artifact directory at revision
`72d8b338380c0b83d02b1e38b40b7b778c1c8703`. The temporary file was exactly
547,637,263 bytes, and `shasum -a 256` matched the approved SHA-256
`12ba359756210927940f8a9ec569cc7d6d6f091e7fcfae6cbe09bba6aab8830d`.
An exclusive atomic rename placed it at
`/Users/roshan/Library/Application Support/RepoPilot/models/coderankembed/72d8b338380c0b83d02b1e38b40b7b778c1c8703/model.onnx`;
size, SHA-256 and mode `0600` were verified again at the final path. The existing
tokenizer was not modified, and its SHA-256 again matched
`ea725c60b9022a7a491ffc348b5622a199853c806d625f673d0e2ebf1c3b5312`.

At the download checkpoint, the graph had not been inspected or loaded, and no
inference or embeddings had been run. The precise upstream revision used for this
export and the publisher's numerical parity claim remain unverified.

## RepoPilot 2.0 Step 2B — offline static graph inspection, 2026-11-05

Model SHA-256 `12ba359756210927940f8a9ec569cc7d6d6f091e7fcfae6cbe09bba6aab8830d`,
tokenizer SHA-256 `ea725c60b9022a7a491ffc348b5622a199853c806d625f673d0e2ebf1c3b5312`
and model size 547,637,263 bytes matched. A custom bounded protobuf-wire scanner
ran in a macOS sandbox denying network access and file writes; no graph was
passed to ONNX Runtime and no inference session was created. Its synthetic
self-check passed. It observed ONNX IR 8, default opset 17, 3,593 nodes, 112
initializers and the expected three `int64[batch, sequence]` inputs and one
`float32[batch, sequence, 768]` output. All 26 observed default-domain operator
types were recognized by the installed runtime's static schema registry; no
external tensor references were found in the fields examined. See the
[static inspection](vector-search-foundation.md#offline-static-graph-inspection--incomplete)
for scope, bounds and limitations.

The installed environments had no ONNX parser/checker package. The wire scan is
not a full protobuf parse or `onnx.checker` validation, so static acceptance is
**incomplete**. A graph-independent attempt to enumerate the runtime kernel
registry exited with status 139; kernel support was not established. The symbolic
sequence dimension does not prove that 512-token input works. Tokenizer
compatibility, real inference, numerical parity, the export's upstream revision
and semantic quality remain unverified. No model or tokenizer inference,
additional package installation, database action or service restart occurred.

## RepoPilot 2.0 Step 2B — official checker blocked, 2026-11-05

The approved procedure specified an already installed macOS ARM64 CPython 3.12
interpreter and required stopping if it was unavailable. `uv python find
--offline 3.12`, installed-interpreter listing, shell lookup and common-location
searches found no Python 3.12; the discovered interpreters were CPython 3.14.10
and 3.9.6. The specified ONNX 1.23.0 universal2 wheel and its SHA-256 were
confirmed against PyPI metadata only. No wheel or dependencies were downloaded,
no environment was created, and the official parser and checker were not run.

The model and tokenizer SHA-256 values still matched the approved values, and
the model size was 547,637,263 bytes. The preceding bounded wire scan remains the
only graph inspection at that checkpoint; full parsing and structural validation
had not yet run. No model inference, database operation or service restart
occurred. The later official checker result is recorded below.

## RepoPilot 2.0 Step 2B — official ONNX static validation, 2026-11-05

After separate approval to use the installed GIL-enabled CPython 3.14.10 ARM64
on macOS 27.2, a new temporary environment was created at
`/private/tmp/repopilot-onnx-check.EAOtHoEC/venv`. The approved official
`onnx-1.23.0-cp312-abi3-macosx_13_0_universal2.whl` matched SHA-256
`6cc93aa89502acbf453a16d79b465d47d9c454f3a3cb3fc5507a8cb59ab53208` before
installation. Its four necessary dependencies were pinned and their official
PyPI wheel hashes verified before offline installation; versions, wheel names
and hashes are recorded in the [static validation](vector-search-foundation.md#official-onnx-1230-static-validation)
section. No production dependency file or environment was modified.

Both stored artifact SHA-256 values matched before and after inspection. Official
ONNX 1.23.0 fully parsed the model protobuf with external-data loading disabled,
then `onnx.checker.check_model` passed in a separate process using the file path,
without optional shape inference. The official parser confirmed ONNX IR 8, opset
17, 3,593 nodes, 112 initializers, the three expected `int64[batch, sequence]`
inputs and `float32[batch, sequence, 768]` output. No external tensor references,
custom domains or unknown operator schemas were found. The declared I/O matches
the adapter's structural CLS-pooling contract.

Both phases ran under a network- and write-denying macOS sandbox with unrelated
home/repository reads blocked, a 90-second CPU limit, 120-second wall timeout
and sampled 2 GiB RSS watchdog. Peak RSS was 1,155,350,528 bytes for parsing and
1,157,316,608 bytes for checking. The watchdog is not a hard kernel memory limit.
An initial deny-default sandbox probe exited 134 during Python startup even
without ONNX or the model; the adjusted sandbox passed network, write and
unrelated-read denial probes before model inspection.

No ONNX Runtime module or inference session was used in either model phase. The
earlier graph-independent `get_all_opkernel_def()` probe's status-139 exit was
not repeated; runtime compatibility remains unverified. The source model's
exact upstream revision, numerical parity, tokenizer behavior, successful
512-token inference and semantic retrieval quality remain unverified. No
inference, embeddings, database action, service restart or deployment occurred.

## RepoPilot 2.0 Step 2B.1 — runtime diagnostic, 2026-11-06

The macOS 27.2 ARM64 host has approximately 16 GiB physical memory. Homebrew
CPython 3.14.10 is ARM64, GIL-enabled and uses ABI `cpython-314-darwin`.
The earlier temporary ONNX Runtime environment and the separate official ONNX
static-checker environment no longer exist. ONNX Runtime was not installed in
the checked project, API, Homebrew or Apple Command Line Tools interpreters.
The project pins version 1.31.1, but the prior installed version and its native
dependencies could not be independently rechecked from the missing binary.
A later broad filename and Spotlight search found no runtime binary in the
accessible locations searched; it excluded the model directory and encountered
some inaccessible paths, so it cannot rule out every possible installation.

Two existing macOS crash reports show separate Python 3.14.10 ARM64 processes
faulting with `SIGSEGV` / `EXC_BAD_ACCESS` at a null address in the ARM64
`onnxruntime_pybind11_state.so` Python binding while returning `KernelDef`
objects. The previously recorded `get_all_opkernel_def()` call was independent
of the CodeRankEmbed model. The traces identify the failing component but do not
establish the underlying cause; they do not establish a CPU-architecture
mismatch. Both reports identify the same binding Mach-O UUID,
`c230574f-20c3-3c2c-a746-acfbd3af12ef`; report filenames are recorded in the
[runtime checkpoint](vector-search-foundation.md#runtime-diagnostic-checkpoint--2026-11-06).
The reports were reviewed without rerunning the failing probe.

Plain Python startup succeeded in a new sandbox with network, file writes,
home and repository reads denied, no inherited application credentials, a
20-second CPU limit, 64-descriptor limit, 25-second wall timeout and a sampled
512 MiB RSS watchdog. The denial canaries passed and Python reported peak RSS
16,269,312 bytes. This is a sampled watchdog rather than a hard memory limit.
Since no suitable runtime installation was found, no new ONNX Runtime import,
provider discovery, kernel-registry probe or synthetic inference was run.
Runtime readiness for real-model execution is **not established**. Installing
or identifying a runtime requires separate authorization or a supplied existing
environment. The source model's upstream revision, numerical parity and semantic
quality remain unverified. No real model or tokenizer was accessed, and no
package, database, repository job or application service was changed.

## RepoPilot 2.0 Step 2B.1 — disposable runtime and synthetic graph, 2026-11-06

After separate authorization, official PyPI ONNX Runtime 1.31.1 and its four
necessary dependencies were hash-verified and installed offline into the new
disposable `/private/tmp/repopilot-ort-runtime-fjkjao5k/venv`. The CPython
3.14.10 ARM64 runtime wheel SHA-256 matched
`8536ac43682caa7492c46d6cfd4c3c8db288dcf0619508431a22170b670ee1d0`.
The installed dependencies were FlatBuffers 25.12.19, NumPy 2.5.4, Packaging
26.3 and Protobuf 7.36.2; their wheel names, hashes and source details are in
the [runtime diagnostic](vector-search-foundation.md#disposable-onnx-runtime-diagnostics--2026-11-06).
No project dependency file or production environment was modified.

In separate macOS-sandboxed subprocesses, Python startup, NumPy import and
ONNX Runtime import/provider discovery passed. The available providers were
CoreML, Azure and CPU. A tiny synthetic graph initialized with **CPU only** and
returned the exact expected output; session initialization plus inference took
0.003649 seconds, with process-reported peak RSS of 58,310,656 bytes. These
figures are a single diagnostic, not a benchmark. Network, home and repository
reads, file writes, fork and spawn were denied and tested. The phases had
20-second CPU and 30-second wall limits and a sampled 768 MiB RSS watchdog;
the watchdog was not a hard memory limit.

One subsequent, separate `get_all_opkernel_def()` attempt reproduced the
previous native fault: `SIGSEGV` (signal 11, shell-equivalent status 139),
null address, with `KernelDef` frames in the same ARM64 binding Mach-O UUID
as the earlier crash reports. No further runtime probe was run. The exact
cause remains unknown, so overall runtime compatibility is **blocked**, even
though the synthetic CPU inference passed. A first Python launcher attempt was
blocked by the sandbox's no-spawn rule; the direct trusted framework executable
ran with the isolation rules retained. The outer sandbox also caused the
offline `uv` installer to panic; installation succeeded outside that outer
sandbox before the restricted runtime probes.

No CodeRankEmbed model or tokenizer was read or executed. Its export's exact
upstream revision, numerical parity, real inference and semantic retrieval
quality remain unverified. No application database, job or service was changed.

## RepoPilot 2.0 Step 2B.2 — real-model preflight blocked, 2026-11-06

The prescribed disposable environment reported CPython 3.14.10 ARM64,
ONNX Runtime 1.31.1 and NumPy 2.5.4, but no installed or importable
`tokenizers`. The RepoPilot adapter requires `tokenizers==0.23.3`; this task
explicitly prohibited installing additional model dependencies and required
stopping if the environment was incompatible. The smoke test therefore stopped
before opening or rehashing either pinned artifact, checking the current CPU
provider or initializing a model session. No real inference or embeddings ran.

The application-source audit found no direct use of the crashing
`get_all_opkernel_def` function or private ONNX Runtime pybind APIs; this does
not prove their absence from runtime internals. The previously reproduced
registry crash remains unresolved. Separately approved tokenizer provisioning
or a compatible approved environment is needed before another smoke-test
preflight. Upstream export revision, numerical parity and semantic relevance
remain unverified, and application embeddings were not enabled.

## RepoPilot 2.0 Step 2B.2 — real-model smoke-test retry, 2026-11-06

After separate approval, `tokenizers==0.23.3` and its required dependencies were
installed into the existing disposable runtime environment from verified
official binary wheels. The tokenizer wheel was
`tokenizers-0.23.3-cp310-abi3-macosx_11_0_arm64.whl`, SHA-256
`68649e97d5b43c44c031d8d848874a6eecae8f8fe40ea989aa777a5a83aca716`.
All installed dependency versions, wheel names and hashes are recorded in the
[smoke-test details](vector-search-foundation.md#real-coderankembed-smoke-test-retry--2026-11-06).
The model SHA-256 matched
`12ba359756210927940f8a9ec569cc7d6d6f091e7fcfae6cbe09bba6aab8830d`;
the tokenizer SHA-256 matched
`ea725c60b9022a7a491ffc348b5622a199853c806d625f673d0e2ebf1c3b5312`.

In an offline macOS sandbox, the tokenizer and isolation canaries passed. One
CPU-only ONNX Runtime 1.31.1 session processed only the approved fixed query,
code and repeated query. Token counts were 18 and 14, float32 hidden outputs
had shapes `(1, 18, 768)` and `(1, 14, 768)`, and the finite nonzero CLS
vectors normalized to length 768 with norm 1.0. The query repeat matched with
maximum absolute difference 0.0 at `rtol=1e-5`, `atol=1e-6`. Session
initialization was 0.632447 seconds; the three inference times were 0.010723,
0.006546 and 0.006737 seconds. Worker peak RSS was 1,473,921,024 bytes.
These measurements are not performance or relevance benchmarks.

The sandbox denied network, unrelated home and repository access, fork and
spawn, allowed read-only pinned artifacts and restricted temporary writes.
The 3 GiB RSS watchdog was sampled, not a hard memory limit; the attempted
address-space limit was unavailable. The prior kernel-registry crash was not
reproduced or invoked and remains unresolved. The precise upstream source
revision, numerical parity and semantic quality remain unverified. No
application embeddings, database operation or service changes occurred.

## RepoPilot 2.0 Step 2B.3A — synthetic capture runner, 2026-11-06

The focused capture, context-aware held-out scoring, retrieval evaluation and
existing issue-retrieval replay tests passed: **89 passed** using a separately
marked disposable PostgreSQL database in a new loopback-only pgvector container
with a temporary data filesystem and no Docker volume (the final run took
2.17 seconds). The suite exercised
actual `terms-v2` construction and retrieval, controlled-vector exact search,
fusion, shared inventory and citation checks, tenant and access rejection,
context ordering and truncation, malformed input, split leakage, and the
`heldout-v2` consistency checks. These are synthetic engineering tests, not a
measurement of semantic relevance. The targeted Ruff check and
`git diff --check` passed.

The completed CLI also ran successfully on a second fresh, marked disposable
database in that container, emitting two synthetic examples and six captures
covering keyword, semantic and hybrid modes. Each used the same six-chunk
universe and was marked `MECHANICAL_TEST_ONLY`. The development fixture's
SHA-256 is
`bc3ce070215cac2353e4a63fae237036dc8318695f8eb105096633fe855de809`.
The output directory was `/private/tmp/repopilot-capture-final-e3c4b62aaf1685d9`;
its mode was `0700` and its three output files were `0600`. Timings are
single synthetic observations, excluded from the deterministic mechanical
report and unsuitable as performance benchmarks.

The complete context and dataset contract, executable command, metric caveats,
and future independent-labeling protocol are documented in
[retrieval-capture-dataset-v1.md](retrieval-capture-dataset-v1.md). The
runner used no real model, real repository, external service, normal
application database, migration, app job or service restart. The output's
synthetic commit and citations are fixture identities, not Git provenance.
The disposable test container was stopped after testing; its temporary
filesystem data is no longer retained. No Docker volume was removed.
Real-data capture, independent labels, semantic relevance, upstream numerical
parity and the earlier kernel-registry crash remain unresolved.

## RepoPilot 2.0 Step 2B.3B — synthetic Git provenance, 2026-11-06

With a clean environment and no `TEST_DATABASE_URL`, focused backend tests
covering the new synthetic Git provenance validator, synthetic capture tests,
held-out scorer, retrieval evaluation and issue-retrieval replay reported
**115 passed, 17 skipped**. The 17 skips require disposable PostgreSQL; SQLite
is not presented as PostgreSQL evidence. The tests exercised actual locally
created synthetic Git commit/blob objects, changed working-tree content,
fingerprints, citations, metadata mismatches, comments, duplicate identities,
conflicting labels, split leakage, insufficient evidence and deterministic
report generation, disabled Git replacement refs and the Git-output cap.
Backend-wide Ruff, `git diff --check` and a shell syntax check of the disposable
PostgreSQL command below passed.

A request to start a new synthetic-only pgvector test container with
`--pull=never`, loopback binding and a temporary data filesystem failed before
creating the container: Docker reported it could not connect to the daemon at
the local Docker socket. No benchmark environment was started. The application
services were not restarted; current PostgreSQL regression verification
remains **blocked**, even though Step 2B.3A's separate earlier run passed.

The corpus selection, independent-labeling and offline resource plans are in
[retrieval-capture-dataset-v1.md](retrieval-capture-dataset-v1.md). The host
reported 16 GiB physical memory, 12 logical CPUs and approximately 76.2 GB free
at `/private/tmp` at the time of inspection. No public source/issue collection,
real embeddings, model inference, application database access or migration was
performed. Real corpus counts remain zero; the ONNX kernel-registry crash,
upstream export revision and numerical parity remain unresolved.

To rerun the missing synthetic-only PostgreSQL checks from `apps/api` when a
Docker daemon is already available, the following creates a new marked test
database in its own loopback-only container with temporary storage. It never
uses `repopilot-local` or pulls an image. This procedure now generates a fresh
test-only password and requires SCRAM for TCP connections, in addition to its
existing loopback, database-marker, empty-schema and temporary-storage guards.
The application test fixtures create and drop their own tables. The trap stops
only this new container and its temporary data disappears; no Docker volume is
deleted. The container is for synthetic data only.

```sh
bash <<'SH'
set -eu
test_id=$(.venv/bin/python -c 'import secrets; print(secrets.token_hex(8))')
test_password=$(.venv/bin/python -c 'import secrets; print(secrets.token_hex(32))')
test_name="repopilot-provenance-test-${test_id}"
test_db="repopilot_capture_disposable_${test_id}"
docker run -d --pull=never --name "$test_name" \
  --tmpfs /var/lib/postgresql/data:rw \
  -e POSTGRES_USER=capture_fixture -e POSTGRES_DB="$test_db" \
  -e POSTGRES_PASSWORD="$test_password" -e PGPASSWORD="$test_password" \
  -e POSTGRES_INITDB_ARGS='--auth-host=scram-sha-256 --auth-local=scram-sha-256' \
  -e POSTGRES_HOST_AUTH_METHOD=scram-sha-256 \
  -p 127.0.0.1::5432 pgvector/pgvector:pg16
trap 'docker stop "$test_name" >/dev/null 2>&1 || true' EXIT
ready=0
for attempt in $(seq 1 30); do
  if docker exec "$test_name" pg_isready -U capture_fixture -d "$test_db"; then
    ready=1
    break
  fi
  sleep 1
done
test "$ready" = 1
test "$(docker inspect --format '{{json .Mounts}}' "$test_name")" = '[]'
test "$(docker inspect --format '{{json .HostConfig.Tmpfs}}' "$test_name")" = '{"/var/lib/postgresql/data":"rw"}'
docker exec "$test_name" psql -X -v ON_ERROR_STOP=1 -U capture_fixture \
  -d "$test_db" -c "COMMENT ON DATABASE ${test_db} IS 'repopilot-synthetic-capture-v1'"
test_port=$(docker inspect --format '{{(index (index .NetworkSettings.Ports "5432/tcp") 0).HostPort}}' "$test_name")
test -n "$test_port"
test_host=$(docker inspect --format '{{(index (index .NetworkSettings.Ports "5432/tcp") 0).HostIp}}' "$test_name")
printf 'disposable_container=%s\ndisposable_database=%s\nloopback_port=%s\npublished_host=%s\n' \
  "$test_name" "$test_db" "$test_port" "$test_host"
test "$test_host" = 127.0.0.1
test_auth=$(docker exec "$test_name" psql -X -v ON_ERROR_STOP=1 -U capture_fixture -d "$test_db" -Atqc \
  "SELECT CASE WHEN count(*) FILTER (WHERE type='host' AND auth_method='scram-sha-256') > 0 AND count(*) FILTER (WHERE type IN ('host','local') AND (auth_method IS DISTINCT FROM 'scram-sha-256' OR error IS NOT NULL)) = 0 THEN 'scram-sha-256' ELSE 'unsafe' END FROM pg_hba_file_rules")
printf 'authentication_guard=%s\n' "$test_auth"
test "$test_auth" = scram-sha-256
test_target=$(docker exec "$test_name" psql -X -v ON_ERROR_STOP=1 -U capture_fixture -d "$test_db" -Atqc \
  "SELECT current_database() || '|' || current_user || '|' || shobj_description(oid, 'pg_database') FROM pg_database WHERE datname=current_database()")
test "$test_target" = "$test_db|capture_fixture|repopilot-synthetic-capture-v1"
test_url="postgresql+psycopg://capture_fixture@127.0.0.1:${test_port}/${test_db}"
printf 'database_marker=verified\n'
env -i PATH=/usr/bin:/bin HOME=/nonexistent TEST_DATABASE_URL="$test_url" \
  .venv/bin/python -B -c 'import os; from sqlalchemy import create_engine; from sqlalchemy.exc import OperationalError
try:
    with create_engine(os.environ["TEST_DATABASE_URL"]).connect():
        raise SystemExit("Passwordless connection unexpectedly succeeded")
except OperationalError as exc:
    if not any(s in str(exc).lower() for s in ("no password supplied", "password authentication failed")):
        raise SystemExit("Could not verify authentication refusal") from None
    print("Passwordless TCP connection rejected")'
env -i PATH=/usr/bin:/bin HOME=/nonexistent PGPASSWORD="$test_password" TEST_DATABASE_URL="$test_url" \
  .venv/bin/python -B -m pytest -q \
  tests/test_benchmark_provenance.py tests/test_synthetic_capture.py \
  tests/test_retrieval_heldout.py tests/test_retrieval_evaluation.py \
  tests/test_issue_retrieval_replay.py
SH
```

## Step 2B.3B — disposable PostgreSQL recovery, 2026-11-07

The earlier run recorded that Docker's daemon was unreachable; the underlying
cause of that earlier interruption was not established. During this recovery,
Docker Desktop's `desktop-linux` context was available at its local Unix
socket, with client and server version 29.8.2. Some ordinary sandboxed Docker
commands initially received a socket permission error; read-only commands and
the isolated test procedure succeeded with the approved Docker access. No
Docker context was switched and no application service was started, stopped or
restarted by this verification.

The originally documented test procedure used a passwordless `trust` role. To
meet the requested test-only-credential requirement, the same procedure above
was amended to generate a fresh disposable password and require SCRAM for host
and local connections. An initial amended run stopped after marking its new
database but before pytest; the exact failed guard was not printed. Its
PostgreSQL initialization log showed the default local trust warning. The
runner stopped that new temporary container. The initialization options were
then made explicitly SCRAM-only and the guard results made visible; no test or
application source was changed and no security assertion was disabled.

The documented procedure above was then executed successfully using:

- Container `repopilot-provenance-test-852c8eebf3cda4d5`, image
  `pgvector/pgvector:pg16`, image ID
  `sha256:0dd3149a06e4579a0d70d8fef9945636cd514005e7237deb27f9b67886f8dc4f`.
- Database `repopilot_capture_disposable_852c8eebf3cda4d5`, role
  `capture_fixture`, published only at `127.0.0.1:49269` for this run. The
  database name, role, test marker, no Docker mounts and temporary filesystem
  at `/var/lib/postgresql/data` were checked before tests.
- A newly generated test-only password. Both host and local PostgreSQL
  authentication rules passed the SCRAM guard; an attempted passwordless TCP
  connection was rejected. The existing URL, marker and empty-schema fixture
  guards remained in force.

The exact shell runner and pytest invocation are the block immediately above.
It reported **132 passed in 7.04 seconds, 0 failed, 0 skipped**; the 17 cases
previously skipped for lack of PostgreSQL therefore executed successfully.
Backend-wide Ruff and `git diff --check` passed. The two new test containers
from this recovery were stopped, their data was temporary, and no Docker
volume was removed. The existing `repopilot` project's API was observed as
unhealthy during the read-only container listing; it was not investigated or
modified by this task.

Only this verification record and `docs/repopilot-2-assessment.md` were edited
in this recovery; no application source or test file was changed. These
synthetic tests do not authenticate a real capture producer, establish
independent relevance labels, or measure CodeRankEmbed search quality. No real
data collection, model inference, app migration, reindex or benchmark ran.

## Step 2B.3C — metadata-only source selection, 2026-11-07

GitHub's public repository and commit-list metadata, issue-list titles and
dates, and license files at the proposed commits were inspected for
`encode/httpx`, `expressjs/express` and `go-chi/chi`. The resulting request
contains ten unapproved pilot leads in
[benchmark-source-approval-v1.md](benchmark-source-approval-v1.md) and its
machine-readable companion. Commit/issue applicability, pre-fix status,
complete issue context and independently reviewed relevance remain unknown.
The source-code licenses do not settle issue-text retention rights.

The offline manifest schema and synthetic negative tests passed: **18 passed**.
They check source identifiers, license and SHA fields, issue uniqueness,
pre-declared pilot-only split, denied permissions, conservative limits,
known-pattern secret screening and canonical serialization. Pattern screening
is not proof that arbitrary data contains no secrets. Backend-wide Ruff and
`git diff --check` passed. No repository source/tree, issue body or comment,
patch, PR diff, model inference, embeddings or benchmark execution was used.
No Docker service or application database was accessed for this step.

## Step 2B.3D — controlled HTTPX issue-context triage, 2026-11-07

Under explicit approval for `encode/httpx` issues #3712, #3713, #3728 and
#3734, anonymous, bounded GitHub REST requests retrieved the four issue
contexts and seven public text comments. A re-read of each issue's metadata
matched its initial projection; this does not make comment edits an atomic
snapshot or establish historical context at issue creation. No linked
attachments, source tree or code file, PR patch, or diff was fetched.

The private capture is under the previously proposed benchmark destination in
`httpx-issue-triage-20261107T022457Z-cd8f4a83`; its directories are mode `0700`
and files `0600`. The exact issue-request HTTP JSON response-body count was
**157,816 bytes**, including issue metadata fetched twice and comment pages,
but excluding headers and TLS overhead. Selected UTF-8 text totaled **66,956
bytes**. No issue exceeded 1 MiB and the aggregate stayed below 4 MiB.
Identity, comment order and count, per-file and canonical context SHA-256,
expected filenames and modes were checked. Requests were anonymous and no
authentication headers were recorded. Recognized credential-pattern scans
were negative; this is not proof that arbitrary text contains no secret.

The complete #3713 and #3734 contexts validate against `issue-context-v1` and
have standalone records. The complete #3712 context does not validate because
one comment has 2,244 characters (limit 2,000); #3728 does not validate because
its body has 45,564 characters (limit 10,000). Both originals are retained
without truncation and explicitly marked incompatible, not represented as
complete valid v1 records. A private triage report records #3734 as eligible
for conditional future source-labeling review, #3713 as insufficient evidence,
and #3712/#3728 as unresolved. The pinned commit's applicability remains
unverified for all four. Nine offline synthetic capture tests and the local
integrity verification passed; `git diff --check` passed. No source-code or
database change, search, model inference, embedding or benchmark occurred.

## Step 2B.3E — pinned HTTPX #3734 source review, 2026-11-07

The existing private #3734 envelope and standalone context matched the triage
manifest, repository and issue identities, schema and canonical SHA-256 before
source collection. Seven anonymous GitHub Git API requests fetched the approved
commit metadata, root tree, two necessary subtrees and exactly three selected
Python blobs. GitHub returned commit
`def4778d622e8bf49a9fea4dda78cca4cf666d8a`, root tree
`706b304f7f46b07fa19e000148be76c059890b26`, parent
`435e1dac899adeb0c156c00721ecbb1124d75842` and committer time
`2025-10-16T09:04:38Z`. The response-body count was **133,052 bytes** and
retained decoded source was **88,244 bytes**. The detailed paths, Git blob
IDs, SHA-256 fingerprints, tree IDs and limits are in the
[source review](benchmark-httpx-3734-source-review.md).

Reconstructed Git tree and blob IDs were recomputed in the collector and
independently with local `git hash-object`; replacement refs were disabled.
The private directory and files passed ownership, `0700`/`0600`, expected-file,
source byte and canonical manifest checks. The raw commit object was not
retrieved, so its SHA was matched against GitHub's metadata and the approved
value, not independently recomputed from raw commit bytes. Neither that check
nor SHA-256 authenticates the capture producer. Known credential-pattern
screening is not exhaustive. The original #3712, #3728 and #3734 envelopes
still matched their triage file hashes.

The named SSL helper, transport calls and stream wrappers exist in the pinned
source. The report's actual HTTPX version and runtime behavior are not
established, so the outcome is **SOURCE_APPLICABILITY_UNRESOLVED**, not an
independent relevance label or root-cause verification. In-memory Python
chunking, citations and fingerprint calculations were exercised with the
three reviewed files and synthetic identifiers; no database snapshot or
capture inventory was created. A complete Git object repository and complete
eligible source universe are not present for the stricter preflight.

From `apps/api`, the focused offline command was:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  --basetemp=tests/.httpx-source-review-pytest-20261107 \
  tests/test_httpx_pinned_source_review.py \
  tests/test_benchmark_source_approval_manifest.py tests/test_benchmark_provenance.py
```

It reported **81 passed, 0 failed, 0 skipped**. Pytest emitted one
`PytestConfigWarning` about the configured cache directory because the cache
plugin was intentionally disabled. The checks used synthetic local Git
fixtures and controlled data; no PostgreSQL was needed. Ruff on the changed
Python test and `git diff --check` passed. No other issue was fetched; no
source or issue text was executed; no model, embedding, benchmark, normal
database, migration, reindex, application service or GitHub write was used.

## Step 2B.3F — HTTPX historical applicability gate, 2026-11-07

The retained #3734 issue envelope and standalone `issue-context-v1` record
were revalidated against their recorded file hashes and canonical context
SHA-256. The three retained source blobs and three tree-object hashes were
recomputed against the existing source manifest; the original private data
was not modified or copied.

Six anonymous read-only GitHub metadata requests returned **38,561 HTTP
response-body bytes**, below the approved 1,048,576-byte aggregate limit.
They covered one issue-events page, the first tags page, a `0.28.1` tag commit,
the issue-referenced commit, and two bounded commit-history queries. No
additional issue or comment body, Python source, PR content, patch or
attachment was fetched. The issue-events endpoint returned four subscription
events and a reference to commit `6eb7ac2f0618025fc2e284f8863716acfb18d8bc`;
it is not the complete issue timeline. GitHub's history responses identify
the `0.28.1` tag commit as an ancestor of the pinned commit and the pinned
commit as an ancestor of the referenced commit. The referenced commit's
message describes a fix; its patch and effectiveness were not examined.

The reporter's HTTPX revision and dependency versions remain unknown, and the
reported memory behavior was not reproduced. Therefore the decision remains
**SOURCE_APPLICABILITY_UNRESOLVED**, with #3734 excluded from positive
held-out labels. The [human review packet](benchmark-httpx-3734-source-review.md)
contains the timeline, gate, candidate ranges, three existing replacement
leads and the remaining evidence needed. No source labels were created.

From `apps/api`, the same focused synthetic source-review, manifest and Git
provenance suite documented in Step 2B.3E was run with the new disposable
`--basetemp=tests/.httpx-history-pytest-20261107`. It reported **81 passed,
0 failed, 0 skipped**. One `PytestConfigWarning` about `cache_dir` was emitted
because the cache plugin was disabled. The synthetic temporary test directory
was removed after the run. No Python source changed; Ruff was not required.
`git diff --check` passed. No application database, repository indexing,
CodeRankEmbed inference, embedding, retrieval benchmark, service restart or
GitHub write occurred.

## Step 2B.3G — replacement issue triage, 2026-11-07

The explicitly approved Express #7506, chi #1188 and Express #7532 issue
contexts were captured using eight anonymous, allowlisted GitHub issue/comment
requests. Each issue's initial and final metadata matched; comment edits are
not an atomic snapshot. The response-body count was **33,231 bytes**, including
metadata rereads; selected UTF-8 text was **7,823 bytes** and the retained
private JSON files and summary occupied **17,364 bytes**. HTTP headers and TLS
overhead are excluded. All totals were within the separately approved limits.

All three complete original contexts passed `issue-context-v1`, canonical
fingerprint, issue/comment identity and ordering checks. The existing
production `terms-v2` builder accepted each context without using comments;
no search was run. Private files were checked as owner-only `0600`, directories
as `0700`. Known credential-pattern scans were negative, but are not
comprehensive. The [triage record](benchmark-replacement-issue-triage-v1.md)
contains exact identities, hashes, comparison and future approval scope; raw
issue text remains only in the private capture.

Chi #1188 is recommended for a separately approved pinned-source review. Its
reporter names chi `v5.3.2` and short master commit `3d1777a`, matching the
proposed commit prefix. That association, the reported reproduction and source
relevance are not independently verified. Both Express cases remain
applicability-unresolved. No gold labels were created.

Ten synthetic tests of the temporary scoped collector passed. The first
unittest invocation used an absolute pathname as a module name and failed
before running tests; rerunning by module name passed. A further **40 focused
manifest, held-out schema, synthetic capture-context and production query
builder tests passed**, with one `PytestConfigWarning` because the cache plugin
was disabled. Ruff passed for the temporary capture, test and independent
verification helpers; `git diff --check` passed. No source or Git object was
downloaded, no additional issue was retrieved, and no normal database, model,
embedding, real benchmark, service restart or GitHub write was used.

## Step 2B.3H — chi #1188 pinned-source review, 2026-11-07

The retained chi #1188 envelope and `issue-context-v1` record were rechecked
against their recorded file and canonical context hashes before collection.
GitHub returned the approved commit
`3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc`, expected root tree
`7c01dddb05b4c19847a3d6259a3f4d519e3b27fb`, parent
`b1c9ab47626cc46b34393ad4d35779c4363c4e1e` and committer time
`2026-09-18T11:51:53Z`. Its commit-list metadata resolved short SHA
`3d1777a` to that full commit. Tag `v5.3.2` targets
`38939062c5df4d3e8814aad1a488983112627ced`; the pinned commit is 13
single-parent steps later according to GitHub's commit metadata. This was a
metadata-only version comparison, not a comparison of source at the two
revisions. The raw commit object was not obtained or independently hashed.

The root tree and five selected Go blob identities were independently
recomputed with `git hash-object`; file SHA-256, private paths and `0700`/`0600`
permissions also passed. Twenty-three anonymous requests read **162,617 HTTP
response-body bytes**, of which **53,845** were metadata and **108,772** blob
responses. Decoded source retained was **77,909 bytes**. The narrower prior
limits of 10 files, 100,000 bytes per file, 1,000,000 source bytes and 4 MiB
response bodies were enforced. The [chi review packet](benchmark-chi-1188-source-review.md)
records paths, hashes, license attribution, observations and limitations.

The reporter's short commit and the APIs present in the pinned source support
`APPLICABILITY_SUPPORTED` for independent human review. No behavior or root
cause was verified and no authoritative label was created. The five files are
a partial source selection, not a complete Git or benchmark inventory.

In-memory Go language identification, fallback coverage, synthetic chunk
fingerprints and citations passed for all five files. Both local Python
environments lacked `tree_sitter` and `tree_sitter_go`; each source analysis
returned `parser_unavailable`, so syntax-aware Go parsing remains unverified.
The targeted synthetic Go parser test reported **1 skipped** for this missing
dependency. The Step 2B.3H source-applicability review is complete, but the
requested syntax-aware compatibility verification remains **incomplete**.
No packages or Go modules were installed.

Twelve synthetic collector tests and **98 focused existing provenance,
manifest, path, citation and fallback tests passed**. Pytest emitted one
`PytestConfigWarning` about `cache_dir` because its cache plugin was disabled.
Ruff passed for the temporary helpers; `git diff --check` passed. No Go source
or test was executed; no other issue, source revision, PR patch, normal
database, model, embedding, real benchmark, service restart or GitHub write
was used.

## Step 2B.3H.1 — Go parser recovery and native crash, 2026-11-07

The previously skipped test had used the application's existing Python test
tooling, CPython `3.14.10` on macOS `27.2` ARM64, GIL-enabled ABI
`cpython-314-darwin`. A new temporary environment was created at
`/private/tmp/repopilot-go-parser.wvnGBw94/venv` with no pip installed in it;
the existing pip tool installed only these two approved binary wheels into
that environment. Their official PyPI JSON metadata, project lockfile, actual
download and an independent `shasum -a 256` agreed:

| Wheel | SHA-256 |
| --- | --- |
| `tree_sitter-0.26.0-cp314-cp314-macosx_11_0_arm64.whl` | `5fc2f41bf246ff2f70a9cc3690be35ec7580a4923151873d898c8bcb1a4503d3` |
| `tree_sitter_go-0.25.0-cp310-abi3-macosx_11_0_arm64.whl` | `503b81a2b4c31e302869a1de3a352ad0912ccab3df9ac9950197b0a9ceeabd8f` |

Both wheel tags were compatible with this interpreter and both imports and
installed versions were verified from the disposable environment. The wheel
metadata had no active runtime dependencies on this interpreter; neither
wheel contained `.pth` or wheel script entries. The environment's installed
distribution inventory contained exactly `tree-sitter==0.26.0` and
`tree-sitter-go==0.25.0`. No application or global Python environment,
dependency lockfile or Go module was modified. Install and tests used a macOS
`sandbox-exec` policy denying network; a loopback connection probe returned
`EPERM`. The application's existing test interpreter was given the isolated
wheel site-packages path explicitly, with a sanitized environment.

The isolated harness first passed its synthetic Go check with the actual Go
grammar and no fallback: 48 syntax nodes, a recognized function and type
declaration, validated UTF-8 byte positions and two syntax-aware chunks. Its
subsequent five-file check terminated with **SIGSEGV / exit 139** before
reporting any completed file. After that crash, the exact formerly skipped
small Go case completed separately: **1 passed, 13 deselected**. Pytest emitted
one `PytestConfigWarning` because the cache plugin was disabled.

A macOS crash report showed `EXC_BAD_ACCESS` in the Python/Tree-sitter native
call stack, including `node_get_text` and `PySlice_Unpack`. A single controlled
synthetic diagnostic with 700 Go functions also exited 139; its Python stack
pointed into `analyze_source`'s parser input callback and symbol text access.
An attempted narrow source-buffer slicing correction was tested once and
also crashed on the larger synthetic input; it and its temporary regression
test were reverted. The underlying native cause is not established. No further
real-source parser attempts were made, and no individual real-file parse can
be claimed as passed. This is distinct from the earlier unresolved ONNX Runtime
kernel-registry crash.

An offline hash-only pass, without importing or invoking a parser, reverified
all five retained Go files against their recorded SHA-256, Git blob hashes,
sizes and snapshot metadata. The earlier fallback coverage remains valid; it
is not evidence that syntax-aware parsing passed. Ruff passed on the restored
parser and temporary helpers, and `git diff --check` passed. No Go code or
test, source download, model inference, embedding, database, indexing,
benchmark, service restart or GitHub write was used. The source-applicability
decision remains `APPLICABILITY_SUPPORTED` for independent human review, while
this parser verification remains **blocked** pending a separately reviewed
synthetic crash investigation.

## Step 2B.3H.2 — synthetic-only Tree-sitter crash investigation, 2026-11-07

**Finding: `NODE_ACCESS_CRASH`; native cause unresolved.** This describes
the observed failure stage, not a proven reference-count, ownership or
grammar-ABI defect. No production parser, lockfile, indexing behavior or
application configuration was changed.

### Earlier crash evidence

| Earlier process | Last supported stage | Saved evidence and limits |
| --- | --- | --- |
| Five-file check, 13:32 | The process reported its preceding small synthetic check passed, then crashed before any individual file result. Its precise source file and completed parse/traversal stage are **unknown**. | macOS report `Python-2026-11-07-133250.ips`: SIGSEGV / `EXC_BAD_ACCESS`, with `node_get_text`, `bytes_subscript` and `PySlice_Unpack` in the faulting stack. |
| 700-function synthetic diagnostic, 13:34 | `Parser.parse()` had returned and `analyze_source` was traversing nodes; the traceback reached symbol `node.text` and its source callback. | SIGSEGV / exit 139; `Python-2026-11-07-133459.ips` also includes `node_get_text`, `bytes_subscript` and `PySlice_Unpack`. |
| Previously attempted and reverted byte-slicing change, 13:36 | Parsing had returned; the traceback reached symbol byte slicing during traversal. | SIGSEGV / exit 139; `Python-2026-11-07-133627.ips` includes Python slice frames. The attempted change and its temporary test were reverted. |

The stacks do not show which earlier operation first corrupted memory, if any.
They do not establish a shutdown crash. The current code creates a fresh
parser for each `analyze_source` call; source bytes, parser and tree remain
referenced during traversal. A language object is passed into the parser
constructor rather than retained as a separate local. The code reads point
rows/columns and `node.text`, uses `named_children`, and provides a callback
that slices the source byte buffer by the requested offset. It does not use
`TreeCursor`, `Parser.reset()`, or node byte offsets. The audit did not
establish an application ownership error. The syntax-aware parser is shared by
non-Python languages; only the Go failures above were observed locally.

### Installed environment and public reports

The existing disposable environment
`/private/tmp/repopilot-go-parser.wvnGBw94/venv` was reused: macOS 27.2
ARM64, GIL-enabled CPython 3.14.10, ABI `cpython-314-darwin`,
`tree-sitter==0.26.0` and `tree-sitter-go==0.25.0`. Both retained wheel
SHA-256 values still matched the Step 2B.3H.1 table. Installed files matched
all 8 and 11 applicable wheel payload files respectively; installed RECORD
hashes checked 11 and 14 files respectively. Native bindings were ARM64
Mach-O bundles:

| Binding | Installed SHA-256 |
| --- | --- |
| `tree_sitter/_binding.cpython-314-darwin.so` | `d8bfcceadd69d12f7f55c663deabfb5984f1787d8de658f59f6de2a7ed952359` |
| `tree_sitter_go/_binding.abi3.so` | `e7be46029b8773f5559c1dd561e4982fa65ddc131427d2e43ae9fee35bf4c917` |

The runtime reported supported grammar ABI 13–15 and the installed Go grammar
reported ABI 15. ABI acceptance is not evidence of runtime stability.
[Trailmark #61](https://github.com/trailofbits/trailmark/issues/61) reports
larger-Go-file node-access crashes in 0.26.0; its
[merged #64](https://github.com/trailofbits/trailmark/pull/64) pins the 0.25
series. [py-tree-sitter #500](https://github.com/tree-sitter/py-tree-sitter/issues/500)
discusses a `Point` reference-count fix, and
[#505](https://github.com/tree-sitter/py-tree-sitter/issues/505) reports
different behavior between 0.26.0 and 0.25.2 for `Point.row`. These reports
are diagnostic leads, not proof that RepoPilot has the same cause. No
reproduction repositories were downloaded or executed.

### Safe synthetic checks

The runner and byte-identical temporary copies of the current analyzer,
selection, chunker and small test were placed under
`/private/tmp/repopilot-go-crash.Eo6lNFJX`; their copy hashes were checked.
The diagnostic used the existing disposable parser packages and, for pytest
only, read the existing application virtual environment's test packages. It
did not alter either environment. The sandbox denied network, reads of the
home directory and repository, writes, and process forks. The pytest profile
allowed read-only access to the existing test packages; it still denied the
repository root and home. A loopback-network canary returned `EPERM`, both
read canaries returned `EPERM`, and `sandbox_check` confirmed fork denial.
Environment variables were sanitized; no database or credential access was
needed.

The initial attempt to apply a nested macOS sandbox from the enclosing tool
sandbox was denied; the same preflight ran successfully after operating-system
authorization. Core dumps were disabled, CPU time was limited to 8 seconds,
and an in-process alarm was set to 15 seconds. The operating system rejected
`RLIMIT_AS`, so an external watchdog sampled RSS against 256 MiB and enforced
a 20-second wall timeout. This is a **sampled** limit, not a hard memory
limit. For the four-scenario diagnostic, peak sampled RSS was 28,400 KiB;
the process reported peak RSS 29,081,600 bytes and exited 0. For the focused
pytest run, peak sampled RSS was 44,576 KiB and the process exited 0. No
watchdog or timeout event occurred.

Four deterministic Go cases—35, 84, 102 and 88 UTF-8 bytes—passed, with
**4 passed, 0 failed, 0 skipped**. They cover one function, multiple
declarations, nested route-like calls and regexp-like strings, UTF-8, and
bounded repeated declarations. Each passed parsing, root and shallow/deep
node traversal, byte bounds, point rows/columns, node text, and actual
RepoPilot analysis and syntax-aware chunking with `fallback_reason=None`.
Tree, parser, language, node and source references were retained through each
direct inspection. The process printed its normal-cleanup and `atexit`
markers and exited successfully.

The copied exact small Go test ran under the same isolation as
`pytest -q -s -p no:cacheprovider -p no:logging
project/tests/test_language_analysis.py -k x.go`: **1 passed, 0 failed,
0 skipped, 13 deselected**. Two earlier attempts stopped during pytest startup
before collecting tests: default output capture needed a writable temporary
file, and then the logging plugin tried to open `/dev/null` for writing.
Disabling those features preserved the no-write sandbox; neither attempt
crashed or ran a native parser test. Ruff passed for the temporary diagnostic
scripts. `git diff --check` passed.

The earlier synthetic traceback already locates node access after parsing, so
the optional larger crash-prone reproduction was **not run**. No retained chi
source file was read or parsed; no Go code, model, database, embedding or
benchmark was run. The prior five-file syntax-aware verification remains
blocked. The source-applicability decision stays
`APPLICABILITY_SUPPORTED` for independent human review; it is not a
reproduced bug or a relevance label. The
[review packet](benchmark-chi-1188-source-review.md#synthetic-only-native-crash-investigation)
compares the unimplemented remediation options. Testing another official
runtime in disposable environments and any subsequent production change each
require separate approval. Existing exception fallback cannot catch SIGSEGV.

## Step 2B.3H.3 — Tree-sitter 0.25.2 synthetic Go compatibility, 2026-11-07

**Result: synthetic compatibility passed for the cases below.** This is a
Go-only experiment, not proof of universal stability or approval to change
production dependencies. The earlier 0.26.0 node-access crash and its
underlying cause remain unresolved.

### Isolated environment and wheel verification

The new disposable environment is
`/private/tmp/repopilot-tree-sitter-0252.BpTXH2o2/venv`. It uses GIL-enabled
CPython 3.14.10, `cpython-314-darwin`, on macOS 27.2 ARM64. The exact
[official PyPI release metadata](https://pypi.org/project/tree-sitter/0.25.2/)
matched the approved runtime filename and SHA-256. The Go wheel was reused
from the previously verified disposable wheelhouse. Both installed wheel
payloads were compared with their verified archives, and both native
extensions are ARM64 Mach-O bundles.

| Wheel | Bytes | SHA-256 |
| --- | ---: | --- |
| `tree_sitter-0.25.2-cp314-cp314-macosx_11_0_arm64.whl` | 137,732 | `bda059af9d621918efb813b22fb06b3fe00c3e94079c6143fcb2c565eb44cb87` |
| `tree_sitter_go-0.25.0-cp310-abi3-macosx_11_0_arm64.whl` | 48,674 | `503b81a2b4c31e302869a1de3a352ad0912ccab3df9ac9950197b0a9ceeabd8f` |

The runtime wheel was downloaded only from the official PyPI file host after
checking metadata and platform tags; a first request from the restricted tool
sandbox failed DNS resolution, then the authorized download succeeded.
Installation was offline, binary-wheel-only and `--no-deps`, in the new
environment alone. No other package was installed. The Go native binding
matched the previously used 0.25.0 grammar binary. Grammar ABI 15 falls within
the runtime-reported supported range of 13–15. Parser construction, basic
parsing and RepoPilot's callback-based `Parser.parse` invocation succeeded.

### Synthetic results

The four prior small fixtures and the medium and larger fixtures were
synthetic Go text; no Go program was run. Each medium or larger run used a
fresh process. The larger workload has 700 generated function declarations,
the same reported structure as the previous 0.26.0 diagnostic. That prior
diagnostic did not retain an input fingerprint, so byte-for-byte identity
across the two historical runs cannot be independently established.

| Workload | Input bytes | Input SHA-256 | Result |
| --- | ---: | --- | --- |
| Small: previously passing | 35 | `9677317627f1fa65818f5821bbd0b5e95fef8f7086e2a2ac3dadc2c9c2e43e18` | Passed. |
| Small: declarations | 84 | `16dcafc3327253ca130de1db7a038bd8a7f76c37f476c0db5d86e2fb90ba6507` | Passed. |
| Small: nested/UTF-8 | 102 | `1ff5f8eb8ca054b74cf5a5bb7a9a44ab7d9e986d957b570f57f29770ff4a3f5e` | Passed. |
| Small: repetition | 88 | `cdd525cac0210b8b588620e38231bcae03dda14ebb819d435b8a3bd99cac817f` | Passed. |
| 200 functions | 2,900 | `ee7346d7793977ecefb62f3e8f51bc4fd9ebd565111543ddf069eeea337f0f67` | Passed: 1,804 nodes, 200 symbols, 201 chunks. |
| 700 functions | 10,400 | `e2837fa61e44807608bb5ccdffa3d587208e69b5d6bcbd63793472132d7089db` | Passed once, then passed three independent fresh-process repetitions: 6,304 nodes, 700 symbols, 701 chunks each time. |

Each case exercised parser initialization, tree and child traversal, node
text, UTF-8 byte offsets and point rows/columns, and unchanged RepoPilot
analysis and syntax-aware chunking without fallback. The small cases covered
imports and declarations; malformed syntax and a node limit produced the
expected explicit fallbacks. Every chunk's line coverage and citation
boundaries were checked. The pure `fingerprint_chunk` function was extracted
unchanged from a hash-verified copy of the application module to avoid
importing database infrastructure. The 700-function chunk/citation/fingerprint
manifest had SHA-256
`1c01abb7af426c7480fe05ac2d680468b0fda2016273a0fd97dd85845c610538`
in all four independent processes. This checks determinism on the synthetic
fixture, not authenticated real-source provenance.

All **six diagnostic processes passed**, covering **nine case executions**
(four small, one medium, four large); no case failed, skipped, crashed or hit
a watchdog. The first attempt to launch the supervisor failed before starting
any probe because system Python 3.9 evaluated a newer type annotation. A
temporary supervisor-only correction resolved startup; no application file
was changed.

### Containment and outstanding verification

Each diagnostic used the macOS sandbox with network, home and repository
reads, writes and process forks denied; network/read/fork canaries passed.
The worker used `faulthandler`, disabled core dumps, a 10-second CPU limit
and an 18-second alarm. An external supervisor enforced a 24-second wall
limit and sampled RSS against 256 MiB. macOS rejected `RLIMIT_AS`, so the RSS
guard was **sampled, not a hard memory limit**. The largest sampled RSS was
38,864 KiB; no limit event occurred. Private diagnostic logs and the exact
temporary harness are under the disposable directory above. Ruff passed for
the temporary helpers and `git diff --check` passed.

Tree-sitter 0.25.2 is a candidate for a separately approved cross-language
compatibility matrix, not a production recommendation based on Go alone.
That matrix should cover Python's existing AST path; JavaScript/JSX;
TypeScript/TSX; Java; Go; Rust; C and C++; and C#, including their existing
grammars, Unicode/CRLF, symbol and import ranges, malformed input, limits,
chunk and citation integrity, and synthetic indexing/retry regressions.
No additional grammars were installed or tested here. A supervised parser
worker remains a useful separately reviewed containment option because an
in-process SIGSEGV cannot be caught by ordinary fallback, even if a runtime
change reduces this particular risk.

No 0.26.0 crash reproduction was rerun, and no retained chi file was read or
parsed. The chi applicability decision remains `APPLICABILITY_SUPPORTED`
for independent human review; its five-file syntax-aware verification remains
outstanding. Model provenance, numerical parity, semantic retrieval quality
and the separate ONNX Runtime kernel-registry issue remain unresolved.
Production dependency changes, further real-source parsing and real-model
benchmarking each require separate approval.

## Step 2B.3H.4 — synthetic cross-language matrix, 2026-11-07

The separately authorized experiment reused the disposable Tree-sitter
0.25.2 environment and installed only the seven missing, lockfile-pinned
grammar wheels. All eight grammar wheels matched their locked and official
PyPI SHA-256 identities; the existing Go wheel was reused. GIL-enabled
CPython 3.14.10 and macOS ARM64 were verified. The eight grammars reported
ABI 14 or 15, within runtime range 13–15. The
[matrix report](tree-sitter-0252-synthetic-matrix.md) records every wheel,
fixture SHA-256, extension, grammar and observed ABI. The original synthetic
fixture generator is retained under
`apps/api/evaluation/fixtures/tree_sitter_0252_matrix_fixtures.py`; it does
not execute or parse the generated text.

Fifteen registered extensions each passed an initial and independently
repeated small synthetic test; ten larger synthetic workloads covered Python
AST and every distinct Tree-sitter grammar entry point. **40 processes passed,
0 failed, 0 blocked**, with no native crash or unexpected nondeterminism.
The copied existing adapter tests also reported **14 passed, 0 failed,
0 skipped**. The tests used the unchanged analyzer, chunker and in-memory
collector with a synthetic client, and checked syntax-aware symbols, imports,
UTF-8/CRLF ranges, source coverage, 120-line chunk bounds, malformed and
node-limit fallbacks, citations and fixed-identity fingerprints. No live
database, authentication path or publication transaction was tested.

The requested deterministic production chunk-ID property is **not met**:
`publish_snapshot` assigns new snapshot, file and chunk IDs with `uuid4`.
A separate no-database identity audit confirmed that the existing
`fingerprint_chunk` changes when a chunk ID changes and remains stable for
the same IDs and contents. The matrix's repeated IDs were deterministic
synthetic fixture IDs; they do not prove deterministic production ID
generation across publications. This is a pre-existing contract limitation,
not a demonstrated Tree-sitter 0.25.2 regression. The task-level verdict is
therefore **TREE-SITTER CROSS-LANGUAGE COMPATIBILITY INCOMPLETE**, despite the
passing synthetic language matrix.

The parsing workers denied network, home and application-repository reads,
writes and process forks, with core dumps disabled. Their 256 MiB RSS guard
was sampled rather than a hard kernel limit; the maximum sampled RSS was
36,368 KiB for the matrix and 46,512 KiB for the small pytest suite. Ruff and
`git diff --check` passed. No 0.26.0 crash was rerun, no chi source was read,
and no production dependency, database, snapshot, model or service was
changed. The [report](tree-sitter-0252-synthetic-matrix.md#production-impact-and-remaining-work)
documents the 0015/0016 considerations, needed disposable PostgreSQL
regressions, rollback planning and separately authorized next steps.

## Step 2B.3H.5 — staged Tree-sitter 0.25.2 update, 2026-11-07

**Verdict: TREE-SITTER STAGED UPDATE INCOMPLETE.** The local pin and lock are
staged and the synthetic/SQLite checks below passed, but the required
disposable PostgreSQL checks did not execute. Do not activate this pin in
normal services on the basis of this result.

### Dependency change and environment

Only `tree-sitter==0.26.0` changed to `tree-sitter==0.25.2` in
`apps/api/pyproject.toml`. The project-required uv 0.13.6 resolved a copied
lockfile in a disposable directory before it was applied. A structural
comparison of all 80 locked packages found changes only to the project
requirement metadata and the Tree-sitter package/artifact record; all eight
grammar package records and all unrelated package records remained identical.
The Tree-sitter wheel list changed from 24 to 21 artifacts. The verified macOS
ARM64 CPython 3.14 wheel has SHA-256
`bda059af9d621918efb813b22fb06b3fe00c3e94079c6143fcb2c565eb44cb87`.
The [prior matrix](tree-sitter-0252-synthetic-matrix.md#runtime-and-grammar-wheels)
records all eight locked grammar wheel identities.

The 0.25.2 lock has CPython 3.12, 3.13 and 3.14 wheels for macOS x86-64 and
ARM64 and manylinux x86-64 and ARM64. Unlike the 0.26.0 lock, it has no
Linux RISC-V prebuilt wheel; a binary-only installation on that platform is
therefore not covered. Only macOS ARM64 was actually installed and tested.
The staged lock passed `uv lock --check --offline`.

The project-required [uv 0.13.6 wheel](https://pypi.org/project/uv/0.13.6/)
was downloaded to a temporary tool environment and verified with SHA-256
`51361029b7cf91185d0092c4b356d110b4ad629e9cb11593f1e006ac72a72ca9`.
A separate CPython 3.14.10 ARM64 test environment was provisioned with
`uv sync --locked --no-build --no-install-project` from the staged lock.
It installed 66 packages; the runtime and all eight installed grammar
payloads were independently compared to the previously verified wheels.
No normal application Python environment was modified.

### Identity contract and synthetic results

The clarified contract intentionally generates opaque UUIDv4 snapshot, file
and chunk IDs per publication. For identical source and fixed parser
configuration, path, source content hash, parser metadata, symbols, imports,
chunk boundaries and source text should agree. Each publication retains its
own IDs, ownership and commit-pinned citations. The existing evidence
fingerprint includes chunk ID, file ID, snapshot ID, path, content hash,
symbol, line range and source text: it is repeatable for the same stored
identity and content, and can differ across independent publications. No ID
or fingerprint format was changed.

The source client's Git blob SHA-1 is calculated from Git's blob header and
raw bytes; identical bytes have the same blob identity independently of the
publication. Indexed files persist a SHA-256 content hash, path and owning
snapshot rather than a separate blob-SHA field. Citations use repository,
commit, path and inclusive line range. The existing `languages-v1` parser
metadata includes runtime and grammar versions, while the chunker has a
120-line default but no separate persisted chunking-version field. Exact
future regeneration therefore also depends on the chunker implementation;
this milestone does not add a schema field or rewrite historical records.

- The newly added publication-identity and supervised 700-function Go tests
  initially reported **4 passed, 0 failed, 0 skipped** on disposable in-memory
  SQLite. After the identity fixture was made robust to configured demo IDs,
  its **3 tests passed** again; the Go test was unchanged. They exercise
  UUIDv4 ownership, stable source processing, pinned citations,
  tenant/repository foreign-key rejection and cross-snapshot evidence rejection.
- The staged environment reran the synthetic cross-language matrix:
  **40 isolated processes passed, 0 failed, 0 blocked**, covering every
  registered extension twice plus one larger workload per grammar. No native
  crash or nondeterminism was observed.
- The final offline synthetic ingestion, publication, citation, retrieval,
  historical-evidence and provenance suite reported **200 passed, 7 skipped,
  0 failed**. The seven skips require PostgreSQL full-text search or row
  locking. The copied existing adapter suite is included in that count.
- The existing legacy migration regression passed **1 test** against a
  temporary SQLite database, including its upgrade-to-head and drift check.
  This does not verify PostgreSQL migration behavior.
- Ruff passed on `apps/api`; `git diff --check` passed. Pytest emitted one
  configuration warning because the cache plugin was disabled.

An earlier exploratory broad run reported **218 passed, 7 skipped, 6 failed
and 41 errors**. Its disposable copy omitted synthetic evaluation fixture
files, and its temporary pytest launcher lacked a multiprocessing main guard;
the latter made three synthetic code-intelligence cases return 503. The
launcher was corrected and those cases passed in the final suite. The
held-out Git-object case stopped on its missing fixture before reading Git
source; it and the unrelated retrieval-benchmark fixture cases were not rerun
under this synthetic-only authorization. These initial failures were not
production parser fixes.

The independent matrix denied network, home and repository reads, writes and
forks; its 256 MiB RSS guard was sampled, not a hard memory limit. The offline
pytest suite used a byte-verified disposable copy of application and test
Python files, in-memory SQLite, no `TEST_DATABASE_URL`, and a network-denied
sandbox. Its RSS watchdog sampled the pytest parent only. The large-Go
regression ran its parser in a child with a 20-second parent timeout, a
10-second CPU limit and core dumps disabled.

### Disposable PostgreSQL blocker and next run

`docker ps` failed both inside and outside the workspace sandbox with an
unreachable `desktop-linux` daemon. No process named `Docker` was found;
the exact cause of daemon unavailability was not established. No application
container was started or restarted, and no PostgreSQL connection or container
creation was attempted.

The documented SCRAM-only, loopback, marker-checked temporary-storage
procedure was adapted for the disposable test environment and syntax-checked
at `/private/tmp/repopilot-ts0252-stage.sJz6LqCp/run_disposable_postgres.sh`.
It has **not** been executed. Once Docker is safely available without
restarting normal services, review and run:

```sh
bash /private/tmp/repopilot-ts0252-stage.sJz6LqCp/run_disposable_postgres.sh
```

**Step 2B.3H.6 update:** the temporary directory containing this runner and
its test environment no longer exists. The command above is historical and
cannot currently run. See the recovery record below before attempting a new
disposable PostgreSQL run.

It checks a unique test container and database, no mounts, PostgreSQL tmpfs,
loopback binding, SCRAM and passwordless rejection, a disposable marker, an
empty schema, current test-copy hashes and the staged lock before running
synthetic tests. It uses `--pull=never` and stops only its own test container.
The temporary runner and backups can disappear; if they do, rebuild and
review them using the documented Step 2B.3B procedure rather than targeting
an ambiguous database.

The [parser-process follow-up design and guarded rollback](tree-sitter-0252-synthetic-matrix.md#parser-process-follow-up-design)
preserve the current UUID contract and the exact pre-stage local dependency
files. Normal activation, real-source parsing and real-model evaluation need
separate authorization; no existing snapshot or normal database was changed.

## Step 2B.3H.6 — staged PostgreSQL recovery attempt, 2026-11-07

**Verdict: TREE-SITTER 0.25.2 POSTGRESQL VERIFICATION BLOCKED.** Docker's
`desktop-linux` context points at
`unix:///Users/roshan/.docker/run/docker.sock`; the socket exists. Sandboxed
read-only queries reported a socket permission error, while read-only Docker
queries outside the workspace sandbox reported that the daemon could not be
reached. `pgrep -xl Docker` found no matching process. This does not establish
why the daemon is unavailable or prove whether the current context is the
intended one. Existing containers, Compose projects and volumes could not be
inspected while the daemon was unreachable. Docker Desktop was not started,
the context was not switched, and no application service was changed.
The read-only diagnosis used `docker context ls`,
`docker ps --all --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'`,
`docker compose ls -a`, `docker volume ls` and `pgrep -xl Docker`.

The previous temporary runner, disposable test environment, uv 0.13.6 tool
and pre-stage dependency backups are no longer present. The staged
`pyproject.toml` and `uv.lock` still have the exact SHA-256 values recorded
in the [rollback section](tree-sitter-0252-synthetic-matrix.md#guarded-rollback-of-this-staged-pin).
An independent standard-library TOML check confirmed the 0.25.2 runtime, all
eight pinned grammar versions and 80 lock records. This is a static check,
not a dependency resolution.

A candidate runner was reconstructed from the documented Step 2B.3B
SCRAM-only procedure at
`/private/tmp/repopilot-ts0252-pg-review-u0c_wl__/run_disposable_postgres.sh`
(SHA-256 `174490f20b18962450800856091f301a162c19ec0ecae6930c5c4513a11e834f`).
Static review found explicit checks for the source copy and staged file
hashes, the parser wheels and installed payloads, a unique container and
database, the previously recorded image ID, temporary PostgreSQL storage,
no mounts, loopback binding, SCRAM and passwordless rejection, the database
marker and an empty schema. Cleanup targets the created container ID only
after checking its run label and name. It includes the seven previously
skipped test names and the PostgreSQL migration test, and checks their JUnit
outcomes. No image pull, application
volume operation or normal Compose command is included. **These Docker and
database guards have not been exercised and must be reviewed again when the
missing prerequisites are available.**

`bash -n` passed. A clean-environment preflight using

```sh
env -i PATH=/usr/bin:/bin HOME=/nonexistent /bin/bash \
  /private/tmp/repopilot-ts0252-pg-review-u0c_wl__/run_disposable_postgres.sh
```

exited 1 before any Docker operation with `verified disposable environment
and source copy are missing`. No test container or database was created, so
there is no container identity, database marker or PostgreSQL authentication
result to report. The runner itself is retained in the private temporary
directory; four temporary copies of tools and dependency files created for
this check were removed. No existing Docker container or volume was removed.

This attempt executed **0 PostgreSQL tests**: the earlier seven skips were not
collected, and no pass, failure or skip count is claimed for this attempt.
No focused pytest suite could be rerun under the staged runtime because the
verified disposable parser environment and wheels have disappeared. The
previous exploratory run's **6 failures and 41 errors** remain documented
above: three launcher-related failures were covered by the corrected focused
suite, while the fixture-dependent held-out and benchmark cases were not
rerun. The retained summary does not identify every affected test; this is not
a full-suite pass.

Ruff 0.17.3, copied without installation to private temporary storage, passed
on `apps/api` using `ruff check --no-cache apps/api`; `git diff --check`
passed. The available copied uv is 0.9.5. The attempted offline check used

```sh
env -i PATH=/usr/bin:/bin HOME=/private/tmp/repopilot-ts0252-pg-review-u0c_wl__ \
  UV_CACHE_DIR=/private/tmp/repopilot-ts0252-pg-review-u0c_wl__/uv-cache \
  /private/tmp/repopilot-ts0252-pg-review-u0c_wl__/uv lock \
  --project /private/tmp/repopilot-ts0252-pg-review-u0c_wl__ --check --offline \
  --no-cache --python /opt/homebrew/opt/python@3.14/bin/python3.14
```

It refused to run because the project requires uv 0.13.6. The copied tool was
subsequently removed. The successful uv 0.13.6 offline check recorded for
Step 2B.3H.5 remains prior evidence, not a new check in this attempt.

To resume, first restore Docker daemon access without starting or restarting
the normal RepoPilot services. Restore a verified disposable Python
environment, byte-identical test copy and the previously verified parser
wheels without changing the application environment; this attempt does not
authorize downloading dependencies. Review the reconstructed runner and
verify its isolation checks against the new disposable instance before
pytest. If the local pgvector image or wheels are unavailable, a separate
approval is needed before downloading them. Runtime activation and normal
database migration remain separately unauthorized.

## Step 2B.3H.7 — durable disposable PostgreSQL harness, 2026-11-07

**Verdict: DISPOSABLE POSTGRESQL VERIFICATION HARNESS PREPARED.** This
preparation did not run the PostgreSQL gate. The repository-local test-only
[runner](../apps/api/evaluation/tree_sitter_pg_harness.py) and its
[synthetic guard tests](../apps/api/evaluation/test_tree_sitter_pg_harness.py)
replace reliance on the vanished temporary draft. The detailed
[procedure](tree-sitter-disposable-postgres.md) records prerequisites, the
exact future commands, test scope, cleanup and limitations.

The previous draft was inspected as untrusted material and not executed. Its
fixed temporary paths could disappear, it did not stage all required fixture
files, its JUnit gate did not reject every selected skip, and its `--rm`
container option could also remove associated anonymous volumes. The durable
runner uses a fresh private source copy and manifest, explicit fixture list,
verified local wheelhouse, separate clean environment and owned-container
cleanup without a Docker volume-removal option. Its HBA check covers all
`host%` rule types and parse errors as well as local rules. These are static
and mocked checks; the new runner has not been tested against a real daemon
or database.

The current working-tree selection contained **133 files** and four explicit
fixtures. The locked base/development graph selected **66 packages**, with no
optional ONNX, NumPy or tokenizer package. The read-only `check` action found
that verified uv 0.13.6, its official wheel and a verified offline wheelhouse
were unavailable at the supplied defaults. It exited before contacting Docker,
installing packages or creating a database. This is not a real offline uv sync.
The earlier staged pyproject and lock hashes remain unchanged.

The standard-library command

```sh
/opt/homebrew/opt/python@3.14/bin/python3.14 -I -B \
  apps/api/evaluation/test_tree_sitter_pg_harness.py
```

reported **38 passed, 0 failed, 0 skipped**. The suite uses fake external
adapters for daemon failure, container ownership, mounts, ports, marker,
SCRAM, authentication and cleanup; it also checks missing environment,
wrong uv, missing or tampered wheels and fixtures, URL validation and JUnit
gates. Ruff 0.17.3 passed on both new Python files, Python syntax checks passed,
and `git diff --check` passed. There is no new shell runner to syntax-check.

The release command explicitly includes the seven previously skipped
PostgreSQL cases, the PostgreSQL migration case, and the listed synthetic
publication, provenance and citation regressions. It includes fixture-only
capture and retrieval metadata cases that need the formerly missing fixture
files. The real-Git held-out case is explicitly deselected, and the capture
suite's separately guarded PostgreSQL cases require another disposable
database contract. The earlier exploratory **6 failures and 41 errors**
remain historical evidence, not a full-suite pass; the remaining affected
cases have not all been individually identified or rerun.

Docker Desktop, normal services and PostgreSQL were not started or contacted;
no image or package was downloaded, no dependency was installed, and no
model, retained chi source or benchmark was executed. The seven PostgreSQL
cases and migration verification remain **unexecuted**, and normal activation
remains unauthorized. The H.6 rollback backups are still unavailable.

## Step 2B.3H.8 — disposable PostgreSQL gate, 2026-11-07

**Verdict: TREE-SITTER 0.25.2 DISPOSABLE POSTGRESQL GATE PASSED.** Docker CLI
29.8.2 used the `desktop-linux` context. The workspace sandbox could not
access its Unix socket; the approved read-only Docker query outside that
sandbox succeeded. Existing RepoPilot containers were observed and left
untouched. The previously recorded local pgvector image was present; no image
was pulled, Docker context switched, or normal service restarted.

Official PyPI metadata matched all **67** artifact identities: uv 0.13.6 and
the 66 locked base/development wheels. The wheel transfer was **50,963,767
bytes**, plus **1,775,024 bytes** of PyPI metadata. Every wheel's filename,
size and SHA-256 was checked again after download. The full public artifact
inventory and hashes are in the [sanitized gate manifest](../apps/api/evaluation/tree-sitter-0252-postgres-gate-3faa77a8ded7c798.json)
(SHA-256 `f2daecdb1823053f9654dcf96c9964de54d464021a33b45536e64fdda6c61adb`);
the [sanitized summary](../apps/api/evaluation/tree-sitter-0252-postgres-gate-3faa77a8ded7c798.log)
contains no test credentials. The official uv wheel hash was
`51361029b7cf91185d0092c4b356d110b4ad629e9cb11593f1e006ac72a72ca9`.
No model weights, optional ONNX package or paid provider were used.

The first offline harness attempt stopped before Docker creation because
`uv sync --locked --no-index` tried to resolve the unrequested ONNX extra.
An offline frozen-lock diagnostic also could not use registry-locked wheel
URLs from the local wheelhouse. No unexpected dependency was downloaded.
The test-only harness was corrected to generate exact, SHA-256-pinned
requirements from the verified lock closure and use `uv pip sync
--require-hashes --offline --no-index --no-build`; it separately ran
`uv lock --check --offline` successfully. All **66** installed distributions
matched the lock, including Tree-sitter 0.25.2 and all eight grammar pins.
The normal Python environments, `pyproject.toml` and `uv.lock` were unchanged.

The macOS network sandbox was independently probed with two self-owned
loopback listeners: no-network mode denied both, and the test profile allowed
only its selected port while retaining local IPC. The harness enforces
no-network installation and permits pytest to contact only its disposable
database port. Its synthetic safety suite reported **43 passed** both before
the run and from the staged disposable environment before container creation.

Container `0319ca991517327e34d996cdd1aa16b11dec2c4127080b675671a4fbf211a159`
(`repopilot-ts0252-pg-3faa77a8ded7c798`) used image
`sha256:0dd3149a06e4579a0d70d8fef9945636cd514005e7237deb27f9b67886f8dc4f`,
database `repopilot_5b1_checks_3faa77a8ded7c798`, test-only role
`capture_fixture` and `127.0.0.1:49775`. Before pytest, the harness checked
the unique identity and labels, unprivileged bridge configuration, empty
mount list, temporary PostgreSQL data filesystem, loopback-only port, SCRAM
rules, passwordless rejection, empty schema, disposable marker and strict
database URL. It created the container directly with test labels; the source
image's labels were independently inspected and were `null`, so no
application Compose ownership label was inherited. No application database
or volume was used.

The runner reported **260 passed, 0 failed, 0 skipped, 1 deselected**, with
one `PytestConfigWarning` because the cache plugin was disabled. All seven
previously skipped PostgreSQL cases and
`test_postgres_legacy_job_survives_migration` executed. The latter exercised
the legacy migration path through Alembic head **0016** and verified legacy
records; a separate PostgreSQL `alembic check` was not run. The exact pytest
argv is preserved in the sanitized manifest; the runner supplied its
test-only password through transient process and container environments and
did not store it in the verification artifacts. The scope was the listed
selected suite, not the entire backend.

The original working tree and the staged copy matched the **135-file**
source manifest after testing; all **66** staged wheel hashes and generated
hash-pinned requirements were independently rechecked. The snapshot is
explicitly a current working-tree copy, not a pinned Git commit. The private
pytest log, JUnit XML and source manifest were retained under
`/private/tmp/repopilot-ts0252-pg-9brlze1d` at the time; that temporary
directory was no longer present on 2026-11-08. Their hashes are recorded in the
sanitized manifest. An independent read-only Docker query by the complete
container ID returned no rows after cleanup. No Docker volume was removed.

The selected fixture cases included **33** synthetic-capture cases, **9**
retrieval-evaluation cases and **5** held-out synthetic cases. The actual
real-Git held-out case was explicitly deselected, and the synthetic-capture
PostgreSQL cases requiring a different database identity were not run. The
earlier exploratory **6 failures and 41 errors** are not individually fully
accounted for, so this is not a full-suite claim. Backend-wide Ruff and
`git diff --check` passed. The 0.26.0 native-crash cause, parser-process
isolation design, normal-service activation, real source processing and real
retrieval quality remain outside this gate.

## Step 2B.3H.9 — supervised parser prototype, 2026-11-07

**Verdict: SUPERVISED PARSER PROTOTYPE VERIFIED** for the specified synthetic
tests only. The [test-only design](supervised-parser-prototype.md) documents
the protocol, temporary source staging, OS controls, fallback distinctions,
production integration requirements and rollback proposal. No production
dispatch, database schema, dependency pin or normal service changed.

The existing disposable environment was CPython 3.14.10 on macOS ARM64 with
Tree-sitter 0.25.2 and all eight previously locked grammar packages. No package
was installed. Each parser and direct-comparison process ran in its own macOS
sandbox with a clean environment. The session canary confirmed denial of an
external temporary-file read and write, a loopback connection and an unrelated
executable; `sandbox_check` reported fork denial. The sandbox also denies Mach
lookup and home/project reads. It permits system/runtime reads and temporary
path metadata, and is not a complete hostile-input sandbox. CPU, descriptor,
file-size and core-dump limits were set inside the child. A 768 MiB RSS
watchdog samples the verified worker PID; this is not a hard memory limit.

The final command, run from `apps/api`, was:

```sh
/usr/bin/env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 \
  /private/tmp/repopilot-ts0252-pg-9brlze1d/venv/bin/python -B -m pytest \
  -q -x --tb=short -p no:cacheprovider evaluation/test_supervised_parser.py
```

It reported **64 passed, 0 failed, 0 skipped, 0 deselected**. This includes
all 15 registered extensions, 11 malformed-syntax cases, 20 controlled failure
scenarios, monitor-limit and cleanup/setup scenarios, and input/protocol checks. Direct
comparisons used separate restricted children. Failure cases returned no
chunks, reaped the owned child and allowed a subsequent synthetic request.
The reported SIGTERM was deliberately generated by the synthetic simulator;
no native crash was deliberately triggered. The test's cache-plugin setting
caused one `PytestConfigWarning`, not a test failure.

The following separate command ran the existing small-source regressions with
networking denied and no database URL:

```sh
/usr/bin/sandbox-exec -p '(version 1)(allow default)(deny network*)' \
  /usr/bin/env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 \
  /private/tmp/repopilot-ts0252-pg-9brlze1d/venv/bin/python -B -m pytest \
  -q --tb=short -p no:cacheprovider tests/test_language_analysis.py \
  tests/test_multilingual_indexing.py \
  --deselect tests/test_multilingual_indexing.py::test_opt_in_job_publication_is_partial_pinned_and_idempotent \
  --deselect tests/test_multilingual_indexing.py::test_postgres_multilingual_search_and_citations \
  --deselect tests/test_multilingual_indexing.py::test_typescript_evidence_and_mock_report_keep_verified_citations
```

It reported **53 passed, 0 failed, 0 skipped, 3 deselected**, with the same
cache-plugin warning. Backend-wide Ruff and `git diff --check` passed. The
disposable test environment later disappeared from `/private/tmp`; on
2026-11-08, the final backend lint was rechecked with the already installed
`apps/api/.venv/bin/ruff` 0.17.3 using `check --no-cache .`. This read-only
lint invocation did not install packages or modify that environment. The
commands above record the actual tests; rerunning them requires a separately
prepared disposable environment with the same dependencies.

Development attempts are retained as evidence: the first nested-sandbox suite
reported **51 setup errors** because its `ps` monitor could not start; after a
direct macOS process-information monitor was substituted, a nested sandbox
attempt stopped at **1 setup error** because macOS denied nesting. One later
run reported **33 passed and 1 failed** when an oversized-response cleanup
race raised a permission error. A stricter executable policy then caused **1
setup error** by blocking Python's macOS launcher. The monitor, owned-child
cleanup and launcher allowlist were corrected before the final passing run;
the tests were not weakened to hide those failures.

The known Tree-sitter 0.26.0 crash remains unexplained; no claim of universal
0.25.2 stability is made. The existing 260-test disposable PostgreSQL result
remains a selected suite, not a full backend run or separate schema-drift
check. The five retained chi files, real CodeRankEmbed, real repository source,
databases and Docker were not accessed in this milestone. No real retrieval
quality, upstream ONNX parity or production sandbox assurance was established.
Production integration, operational activation and any real-source work require
separate authorization.

## Step 2B.3H.10 — feature-flagged supervisor, 2026-11-08

**Verdict: FEATURE-FLAGGED SUPERVISED PARSER INTEGRATION INCOMPLETE.** The
application collector now has an opt-in supervised path, but the actual
supervised Tree-sitter cross-language suite and a new disposable PostgreSQL
integration gate could not run. The previously recorded 64 prototype tests
and 260 selected PostgreSQL tests predate these changes and are not evidence
that this integration passed those gates.

`INDEX_MULTILINGUAL_SUPERVISED_PARSER_ENABLED` and
`INDEX_MULTILINGUAL_ENABLED` both default to false. Newly admitted supervised
jobs use `multi_supervised` in the existing 20-character job mode field;
snapshots still use `multilingual`. A queued supervised job fails with
`supervised_parser_disabled` if its worker's flag is off, rather than
silently using the legacy parser. Existing queued multilingual jobs use the
supervisor when the worker flag is on. No schema, dependency lock or normal
service configuration changed. The worker still applies its existing
authorization, pinned snapshot and lease checks before atomic publication.

The supervised collector binds its per-request ID to the repository, commit,
blob, path, source hash and nonce, and validates the returned contract before
building chunks. Failures become sanitized `supervised_parser_<outcome>` job
errors and do not publish a partial collection. Explicit syntax fallback and
missing-grammar fallback retain their existing file status. The application
copy retains the prototype's macOS profile, clean environment, fixed child,
timeouts, sampled RSS guard and no-retry policy; an AST comparison checks
the copied profile and core supervisor functions against the original
prototype, along with the fixed child. It fails closed on Linux and on macOS outside the reviewed
disposable-venv prerequisites. See the [design](supervised-parser-prototype.md#step-2b3h10--disabled-by-default-integration)
for the duplicated-code, isolation and resource limitations.

Using the pre-existing application test interpreter, with a clean environment,
network denial and only in-memory SQLite fixtures, this command ran the new
integration suite from `/private/tmp`:

```sh
/usr/bin/sandbox-exec -p '(version 1)(allow default)(deny network*)' \
  /usr/bin/env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 \
  '/Volumes/Samsung SSD/Project/RepoPilot/apps/api/.venv/bin/python' -B -m pytest \
  -q -x --tb=short -p no:cacheprovider \
  -c '/Volumes/Samsung SSD/Project/RepoPilot/apps/api/pyproject.toml' \
  '/Volumes/Samsung SSD/Project/RepoPilot/apps/api/tests/test_supervised_parser_integration.py'
```

It reported **62 passed, 0 failed, 0 skipped, 0 deselected**. These tests
use controlled child responses, including synthetic parser-version strings;
they exercise real parent validation, flag dispatch, sanitized failures,
SQLite publication/rollback and tenant/citation identities, but do not run
the installed Tree-sitter grammars. All 15 extension mappings were checked
mechanically. No dependency was installed and the normal venv was not changed.

The following command, also from `/private/tmp`, ran the integrated child and
transport directly under its restricted macOS profile using the already
installed resolved base interpreter:

```sh
/usr/bin/env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 \
  '/Volumes/Samsung SSD/Project/RepoPilot/apps/api/.venv/bin/python' -B -m pytest \
  -q -x --tb=short -p no:cacheprovider \
  -c '/Volumes/Samsung SSD/Project/RepoPilot/apps/api/pyproject.toml' \
  '/Volumes/Samsung SSD/Project/RepoPilot/apps/api/evaluation/test_supervised_parser_native_smoke.py'
```

It reported **25 passed, 0 failed, 0 skipped, 0 deselected**: normal,
malformed and long synthetic Python, the missing-Go-grammar fallback, 20
controlled child failures and one isolation canary. Each failure was followed
by a successful synthetic request, and owned children were reaped. The
deliberate signal was SIGTERM, not a native segmentation fault. It did not
call the production `run()` availability gate and did not load a Go grammar.
The existing selected parser, collector, workflow, evidence and
tenant regressions reported **71 passed, 0 failed, 16 skipped, 17 deselected**
under the same clean, network-denied SQLite setup. Ten skips were missing
Tree-sitter grammar packages and six required PostgreSQL; the 17 deselections
were grammar-dependent multilingual cases. Each pytest command emitted one
cache-plugin configuration warning.

The prior disposable Python environment, uv 0.13.6 and verified wheelhouse
were unavailable. The existing application venv has no Tree-sitter runtime or
grammar packages. No package download, installation, new environment, Docker or
PostgreSQL operation was performed. Restoring a disposable environment and
any missing artifacts requires separate authorization; then rerun actual
supervised parsing for every extension and the reviewed disposable PostgreSQL
publication, isolation and schema-drift tests. The macOS sandbox and sampled
watchdog are not established as a production hostile-source boundary, and no
Linux equivalent is implemented. Full backend verification, native-crash
explanation, real semantic quality and ONNX export parity remain open.

Backend-wide Ruff 0.17.3 (`check --no-cache`) and `git diff --check` passed.
The staged `pyproject.toml` and `uv.lock` hashes remain respectively
`e0fe0e272583fefecbc09d4c9e0631c41771f370b267a4dd4569fa349ee4e240`
and `40139126d31b521cc5377f1333b22d7c18de733840d1c63d848309ba7ad9c09a`;
no dependency pins were changed in this step. No normal service was started or
restarted, and no real source, private chi file or CodeRankEmbed artifact was
processed.

## Step 2B.3H.11 — supervised parser verification (2026-11-08)

This later synthetic verification supersedes the missing-environment and
missing-PostgreSQL test limitations recorded for H.10; it does not authorize
activation. On macOS 27.2 ARM64 with GIL-enabled CPython 3.14.10, Docker's
`desktop-linux` daemon was reachable, and the pinned local
`pgvector/pgvector:pg16` image was available. The existing application
containers were not stopped, started or restarted. The unrelated pre-existing
unhealthy application API container was left alone. No normal database,
private chi source, model or real repository source was accessed.

The disposable environment used verified official `uv==0.13.6`,
`tree-sitter==0.25.2`, and the eight unchanged locked grammar versions. It
installed 66 locked wheels offline with hashes enforced, from a private
wheelhouse; the uv distribution is the 67th verified wheel. PyPI's published
filenames, versions, sizes, platform tags and SHA-256 values were checked
against the downloaded bytes and the lock. The wheel total was **50,963,767
bytes**, and metadata plus wheel response bodies totaled **52,767,028 bytes**,
below the authorized 200 MiB cap. No ONNX or model dependency was downloaded.
The exact 67-wheel inventory, official URLs and hashes are in the sanitized
[verification manifest](../apps/api/evaluation/supervised-parser-h11-verification-e4a57ec5c92db88d.json)
(SHA-256 `dbe9d24d7282dad700f3908b1d593108fbf31ddfe133adb87aa669d1744d3daf`).
The source staging manifest covered 148 selected working-tree files, SHA-256
`07f8a164f7da808f4d88856d64027de3ecca0e3f6244e8497b6645a2a8c13000`;
this was an uncommitted working-tree snapshot, not a pinned Git commit.
`uv 0.13.6 lock --check --offline` passed without modifying the lock.

The reviewed test-only harness was run with the verified uv, Python,
wheelhouse, Docker CLI and socket:

```sh
/opt/homebrew/opt/python@3.14/bin/python3.14 -I -B apps/api/evaluation/tree_sitter_pg_harness.py run \
  --python /opt/homebrew/opt/python@3.14/bin/python3.14 \
  --uv /private/tmp/repopilot-h11-artifacts-yyrn4s74/uv \
  --uv-wheel /private/tmp/repopilot-h11-artifacts-yyrn4s74/uv-0.13.6-py3-none-macosx_11_0_arm64.whl \
  --wheelhouse /private/tmp/repopilot-h11-artifacts-yyrn4s74/wheels \
  --docker /Users/roshan/.docker/bin/docker \
  --socket /Users/roshan/.docker/run/docker.sock
```

These private paths identify this run and may not survive cleanup or reboot;
the repository-local harness and its [preparation guide](tree-sitter-disposable-postgres.md)
are the durable procedure. It verified a uniquely owned container
`repopilot-ts0252-pg-e4a57ec5c92db88d` and database
`repopilot_5b1_checks_e4a57ec5c92db88d`, temporary data, no application mounts,
loopback-only binding, SCRAM, rejected passwordless TCP, the disposable
database marker and an exact test URL before pytest. It removed only that
container; a subsequent read-only Docker query found no matching container.
No Docker volumes were removed. Logs and JUnit results were initially retained
in `/private/tmp/repopilot-ts0252-pg-tu1ffots`, but that temporary directory
was no longer present on 2026-11-12. The sanitized manifest preserves their
recorded hashes and result counts; it is not a replacement for the raw logs.
The original 148-file source manifest was also in that directory and is no
longer available, so its individual file hashes cannot now be independently
rechecked from the retained summary.
A [reconstructed sanitized summary](../apps/api/evaluation/supervised-parser-h11-verification-e4a57ec5c92db88d.log)
is retained alongside it and is explicitly marked as reconstructed, not as
the original test output.

Results, with no failures or skips in these suites:

| Suite | Passed | Failed | Skipped | Deselected |
| --- | ---: | ---: | ---: | ---: |
| Synthetic native supervisor, child and prototype | 119 | 0 | 0 | 0 |
| Selected PostgreSQL and synthetic regressions | 322 | 0 | 0 | 1 |
| Native-child PostgreSQL publication and migration/drift | 3 | 0 | 0 | 0 |
| Disposable harness synthetic safety checks | 44 | 0 | 0 | 0 |
| Later missing-interpreter `run()` checks | 2 | 0 | 0 | 0 |

The pytest runs emitted a configuration warning about `cache_dir` because the
cache provider was deliberately disabled; the 44-case harness run also
reported 14 passing subtests. After the staged run, a test-only change made
the unreviewed-interpreter check enter through `run()` and added an actual
missing-interpreter launch check. Both targeted checks passed against the
final test file, whose SHA-256 is recorded in the manifest. This later file
is not represented as part of the earlier source-copy manifest.

The native suite called the actual application `run()` availability gate and
supervised collector with pinned grammar packages and original synthetic
inputs for all **15** registered extensions. It verified a real Go grammar,
parser identities, source hashes, syntax fallback, source ranges, fingerprints
and citations; missing isolation and an unreviewed interpreter failed closed.
Children used the reviewed macOS no-network sandbox. The trusted native test
coordinator used a Python-level IP socket guard, not an OS network sandbox.
No known native crash was intentionally reproduced, and no native crash was
observed in these tests.

The 322 selected cases include the H.10 integration tests, the formerly
skipped PostgreSQL cases and the previously deselected grammar-dependent
cases: 14 chunking variants, 11 language extraction variants, and the three
other selected cases now executed. The previous 16 skips and 17 deselections
are therefore covered by the new selections. The single current deselection
is the separate held-out test that reads real repository Git objects, which
was not authorized here. The separate three-case PostgreSQL phase exercised
supervised job admission, claim and publication using real sandboxed native
children on synthetic Go, TypeScript and Python, citation and source identity,
and explicit syntax fallback. Its Alembic test independently upgraded a fresh
disposable schema through **0016** and ran **`alembic check`**, which reported
no new upgrade operations. A successful upgrade alone is not treated as a
drift check.

Because macOS will not nest the parser's sandbox inside the PostgreSQL test
sandbox, the native PostgreSQL phase uses a **test-only local socketpair
broker**: the database pytest process stays restricted to its verified
loopback port, and proxies the worker's `_execute` call to a clean-environment
broker that invokes the real, unmodified `run()` and launches the actual
no-network parser child. The broker receives no database URL, test password
or GitHub credentials, and uses a Python-level IP socket guard. The broker
coordinator itself is not OS-network-sandboxed. Direct collector-to-`run()`
and real child execution were also tested independently in the native suite.
The exact unproxied same-process worker-plus-PostgreSQL path was not exercised;
these results must not be described as that test.

The original exploratory **6 failures and 41 errors** involved incomplete
fixtures and a multiprocessing launcher. Relevant staged fixture and corrected
launcher cases ran in the selected gates, but the original case list is not
fully recoverable and the full backend suite was not run. The current
staged 148-file test copy is selected rather than a complete backend fixture
set. The Linux isolation mechanism remains unavailable, the 768 MiB RSS
watchdog is sampled rather than a hard memory limit, and the 10-second wall and
five-second soft CPU limits have not been validated as production limits.
The earlier 0.26.0 native crash remains unexplained. Both multilingual flags
still default to false. Real-source processing, normal-service activation,
Linux isolation and an operational rollout require separate approval.

On the later 2026-11-12 documentation pass, the disposable environment and
wheelhouse were also no longer present. Backend-wide Ruff 0.17.3
(`check --no-cache apps/api`), `git diff --check`, a whitespace check of the
new test and evidence files, and manifest/hash validation all passed. Ruff was
run read-only from the pre-existing application environment; no package was
installed into it. The offline `uv 0.13.6 lock --check` had passed earlier in
the disposable staged copy. The original native and PostgreSQL tests were not
repeated after their temporary environment disappeared.

## Step 2B.3I — chi human review preparation (2026-11-12)

The existing `go-chi/chi` issue 1188 envelope matched SHA-256
`800cc6dbb868a166bc033224b44b195850ac3269b35a5a7ce4b2606340270ba6`;
its complete ordered `issue-context-v1` matched
`61d54f284c13e89445d1b5ff0c4761a67d32190157b4dcc49b716ef67e4469e7`.
The previously retained metadata, source manifest and five source files were
rechecked. Their exact sizes, Git blob SHA-1s, SHA-256s and all previously
recorded ranges matched the [source review](benchmark-chi-1188-source-review.md).
The 22-entry root tree was rehashed as
`7c01dddb05b4c19847a3d6259a3f4d519e3b27fb`. The raw commit object was not
available for an independent commit hash; its binding to the tree remains a
retained metadata assertion. The five files total **77,909 bytes** and are not
a complete repository.

The two blind copies are under
`/Users/roshan/Library/Application Support/RepoPilot/benchmarks/source-selection-v1/chi-1188-human-review-20261112T101323Z-19f88e6b`.
All packet directories were checked as `0700`, all files as `0600`; each copy
contains ten files and both matched. The initial per-copy canonical
filename/SHA-256 manifest digest was
`f898c90504e3f44e2bd73bd13479304acf272f8f4fc03a1a1cff886a27f934dd`.
The `human-review-inventory-v1` digest was
`23e84c9f7661db61d37e16cb0db95536bd3bbac7f22f81935eba89268ae0e25a`.
An independent read-only packet check confirmed full line coverage, unchanged
display of this issue's title/body and source, a withheld comment, blank
judgment templates and absence of prior audit ranges from packet instructions
and metadata. The copies alone do not enforce reviewer separation on a shared
OS account. The retained issue and source contents were not copied into Git.

The separate [human-review protocol](chi-1188-human-labeling.md) preserves the
existing 0–3 rubric, defines explicit unjudged and abstention outcomes, and
requires human self-attestation, pseudonyms, provenance and partial-source
warnings. Its validator checks identities and ranges but cannot authenticate
reviewers or prove independence. An adjudicated status requires two distinct
self-declared blind reviewers and a separate adjudicator; a single reviewer
remains exploratory. Initial comments and prior audit findings are withheld;
any later disclosure must be recorded. **Human label count: 0.**

From `apps/api`, the synthetic-only annotation and packet tests were run as:

```sh
/usr/bin/env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  '/Volumes/Samsung SSD/Project/RepoPilot/apps/api/.venv/bin/python' -B -m pytest -q \
  -p no:cacheprovider \
  --basetemp /private/tmp/repopilot-human-review-tests.4nBwNfEg/pytest5 \
  tests/test_human_relevance.py
```

They reported **46 passed, 0 failed, 0 skipped**, with one pytest configuration
warning because the cache provider was disabled. A nested macOS `sandbox-exec`
attempt was rejected by the workspace sandbox before tests started; the
successful synthetic tests used the existing restricted execution environment
and a clean environment, and the packet test explicitly rejected network and
subprocess use. Ruff passed for the changed Python files and `git diff --check`
passed. No source download, native Go parsing, Go execution, model, embedding,
retrieval benchmark, database or normal service was used.

The source is MIT according to the existing attribution record, but the full
copyright and permission notice was not retained. Resolve notice requirements
before distributing source copies; retrieving the pinned license text, a full
repository capture, model inference and benchmarking each need separate
authorization. The original applicability assessment is unchanged, and no
claim is made about a reproduced bug, root cause or full-repository quality.

## Step 2B.3J — chi review packet license (2026-11-12)

Before the update, both owner-only reviewer copies matched their recorded
canonical per-copy filename/SHA-256 manifest
`f898c90504e3f44e2bd73bd13479304acf272f8f4fc03a1a1cff886a27f934dd`.
The complete retained issue context and five source blobs were reverified;
their context and source-inventory SHA-256 values remain respectively
`61d54f284c13e89445d1b5ff0c4761a67d32190157b4dcc49b716ef67e4469e7`
and `23e84c9f7661db61d37e16cb0db95536bd3bbac7f22f81935eba89268ae0e25a`.
The retained source-review records contained license attribution but no full
license file. The rehashed root tree
`7c01dddb05b4c19847a3d6259a3f4d519e3b27fb` identifies its `LICENSE` entry
as a regular `100644` blob of 1,123 bytes with Git SHA-1
`d99f02ffac5185e2550770d33333a67e2cf2092b`. The pinned commit-to-tree
association remains based on retained metadata; the raw commit object was not
available for independent rehashing.

One anonymous official GitHub request retrieved only that
[Git blob](https://api.github.com/repos/go-chi/chi/git/blobs/d99f02ffac5185e2550770d33333a67e2cf2092b),
bound by the retained tree to the
[commit-pinned LICENSE path](https://github.com/go-chi/chi/blob/3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc/LICENSE).
It read **1,833 HTTP response-body bytes** and returned **1,123 decoded
bytes**. The complete UTF-8 MIT copyright, permission and disclaimer notice
matched the expected Git blob and SHA-256
`a2d51b7515acfaff2f7a88688650f2fc4fd99561383e72bba2305e3db59a1647`.
`git hash-object --no-filters` and `shasum -a 256` independently confirmed
the identities of both packet copies and the retained original. No redirects,
additional GitHub content or credentials were used.

The original notice and provenance are retained under the private directory
`/Users/roshan/Library/Application Support/RepoPilot/benchmarks/source-selection-v1/chi-1188-license-20261112T102846Z-992fa356`.
Each reviewer copy now contains `source/LICENSE` and
`source/LICENSE.provenance.json`; its README's license paragraph was updated.
All other original packet files were checked unchanged by reconstructing their
pre-update per-copy manifest. Both updated copies have twelve files and match
canonical manifest SHA-256
`3286432f96f0b36a0a3035c45bff9f408ae95ea9c53da8ea69312f077e57fc1f`.
The packet and archive directories are `0700`, their files are `0600`, and
the original issue and source text remain outside Git. The comment is still
withheld from initial blind review; templates remain blank and no reviewer IDs
or relevance grades were created. **Human label count: 0.**

The existing synthetic annotation suite reported **46 passed, 0 failed,
0 skipped**, with one pytest cache-configuration warning. `git diff --check`
passed; no repository Python code changed in this step. No Go parser or Go
code, model, embedding, retrieval benchmark, database or normal service was
used. The [review protocol](chi-1188-human-labeling.md) describes how a
coordinator must provide separate access and keep the independent submissions
apart; two owner-only directories under one account do not enforce that
separation. The five-file source remains a partial pilot, and the reported
behavior and root cause are unverified. Full-corpus capture, model inference
and benchmarking still require separate authorization.

## Local dashboard service recovery (2026-11-12)

The local web server on port 3000 was pointing to the separate API on port
8000 while Docker Desktop was stopped. Docker Desktop was started to restore
the existing services; their restart policies resumed the existing containers.
The `repopilot-local` API, PostgreSQL and Redis became healthy. Its API image
matched the previously documented `0014`-compatible image, and a read-only
database query confirmed revision `0014`. The `repopilot-local` migration
container remained exited; no migration or image rebuild was run. The other
pre-existing `repopilot-api-1` remained unhealthy and was not changed.

A new owner-only, Git-ignored `apps/web/.env.local` points host-run Next.js
to `http://127.0.0.1:8001`, the existing `repopilot-local` API. The web
server was restarted on loopback port 3000. The home page returned HTTP 200,
`/api/health` returned `{"ready":true}`, and an unauthenticated
`/api/auth/me` request returned HTTP 401 rather than a service error. This
does not verify a real GitHub sign-in or browser interaction. The available
Node 26 runtime is outside the project's declared Node 22–24 range.

## chi #1188 reviewer coordination and corpus request

The existing two private blind packets were left unchanged. Reviewer identities
and a handoff method have not been provided, and no invitations were sent. The
[coordinator drafts](chi-1188-reviewer-coordination.md) describe separate
handoffs and human adjudication; they do not contain issue text, source or
suggested ranges. No submissions were found in the packet directories during
the preceding audit; submissions stored elsewhere remain unknown.

The [full eligible-corpus proposal](chi-1188-full-corpus-approval-v1.md) and
its machine-readable request specify the exact chi commit/tree, private
storage, existing source-selection policy, collection caps and fail-closed
verification. They are explicitly **NOT APPROVED**. The raw Git commit object,
complete recursive source inventory and real-corpus capture path remain
unavailable. Source collection, real-source parsing, CodeRankEmbed inference,
embeddings and a retrieval benchmark were not performed. The existing capture
runner remains restricted to its synthetic fixture; no held-out example or
human judgment was invented.

A local disposable synthetic Git-object check exposed an additional preflight
limitation: with an excluded non-source blob absent, `git ls-tree -l` returned
a nonnumeric `BAD` size for that entry, which the existing `GitSource` cannot
parse. The same synthetic tree was listed successfully without `-l`. The
proposed source-only approval therefore requires a reviewed metadata-only
enumeration fix before using that preflight, or a separately approved expanded
blob scope. No real repository was fetched or parsed during this check.

## Automated patch workflow — staged synthetic verification

The local implementation adds a disabled-by-default, evidence-bound proposal API, strict
in-memory unified-diff validator, transactional outbox, lease-fenced worker, private
non-executing workspace preparation and an investigation-page panel. The test-only provider
is a synthetic fixture; there is no configured live provider. The test execution adapter
reports `VALIDATION_UNAVAILABLE`: no untrusted repository command or before/after test was
executed. Human approval records a decision and does not apply or publish a patch.

On 2026-11-12, the reviewed repository-local disposable harness was extended only to include
the new tests and their required case names. Its read-only preflight passed with CPython
3.14.10, uv 0.13.6 and 66 wheels checked against the unchanged lockfile. The 67 previously
approved official wheels (including uv) were fetched into a private temporary wheelhouse,
verified against official published hashes and the recorded inventory; aggregate response
bytes including metadata were 52,738,791. No model artifacts were downloaded.

The final harness run created only container
`repopilot-ts0252-pg-159d4127c2093db0` and database `repopilot_5b1_checks_159d4127c2093db0`.
It verified the pinned local image, unique ownership, temporary database storage, no
application mounts, loopback-only access, SCRAM, passwordless rejection and its disposable
marker before testing. Cleanup of that container was confirmed; no existing volume or
service was changed. The exact invocation was:

```sh
/opt/homebrew/opt/python@3.14/bin/python3.14 -I -B apps/api/evaluation/tree_sitter_pg_harness.py run \
  --python /opt/homebrew/opt/python@3.14/bin/python3.14 \
  --uv /private/tmp/repopilot-patch-artifacts.E9ohAs60/uv \
  --uv-wheel /private/tmp/repopilot-patch-artifacts.E9ohAs60/wheels/uv-0.13.6-py3-none-macosx_11_0_arm64.whl \
  --wheelhouse /private/tmp/repopilot-patch-artifacts.E9ohAs60/wheels \
  --docker /Users/roshan/.docker/bin/docker --socket /Users/roshan/.docker/run/docker.sock
```

Results: **372 passed, 0 failed, 0 skipped, 1 deselected** for the selected PostgreSQL
suite; **3 passed, 0 failed, 0 skipped** for native PostgreSQL integration, including
upgrade to revision 0017 and a separate Alembic schema-drift check; **120 passed** synthetic
native parser tests; and **44 passed** harness safety tests. The deselected test reads pinned
local Git objects for a separate retrieval evaluation. Private sanitized logs, JUnit reports
and a source hash manifest were retained under `/private/tmp/repopilot-ts0252-pg-k4yc0pes`;
that temporary directory was no longer present on 2026-11-13. No normal database migration
or service restart occurred.

The initial broad run using the normal host `.venv` reported **908 passed, 20 failed,
60 skipped and 3 errors**. Eighteen parser failures and three fixture errors were caused by
missing Tree-sitter/grammar packages, and one failure by missing NumPy. One failure was an
existing synthetic provider harness hard-coded to stop at revision 0016; it was updated for
the additive 0017 migration, and its targeted test then passed. These earlier results are
preserved here rather than represented as passing. A later verified disposable environment
provided the locked parser wheels. The exact locked NumPy 2.5.4 wheel was also independently
verified against PyPI and `uv.lock` (SHA-256
`ffa6ce09a1c6a08e9667dd9c97aa0b14184e8d18f2a14b78b2a2328c9147f076`) and installed only
into a separate offline temporary target for the synthetic backend regression. No ONNX
runtime or model execution was needed for that check.

The frontend tests, type checking, lint and production build were run using the existing
Node 26.13.0 installation. The package declares Node `>=22 <25`, so this build is not proof
of a supported-Node release build. The build used a private copy of the web source and
dependencies, with no application service restart. The new code remains staged; see
[patch workflow verification](patch-workflow-verification.md) for release blockers.

The broad backend rerun used the verified disposable Python 3.14.10 environment, the separate
locked NumPy target, no `TEST_DATABASE_URL`, and a macOS network-denial sandbox. It completed
with **947 passed, 0 failed, 51 skipped and 1 deselected**. The skips include PostgreSQL-only
and unavailable optional-provider cases; the selected PostgreSQL run above is the database
evidence for this milestone. The single deselection is the separate real Git-object retrieval
fixture noted above. The earlier incomplete-environment failures remain recorded above.

The frontend suite completed **77 passed, 0 failed, 0 skipped**, including the patch proxy
and rendering tests. TypeScript, ESLint and Ruff passed; a copied-source production build
completed on the unsupported Node 26 host as noted above. These tests do not establish browser
fetch-transition coverage or release readiness.

## P4 — trusted synthetic patch-execution gate

On 2026-11-13, a test-only adapter and two immutable synthetic specifications were added.
The exact fixed command is `/usr/local/bin/python -I -B /fixture/test_add.py`; the fixture,
test, patch, image and specification identities are bound by SHA-256 or a pinned image ID.
The adapter accepts no user- or model-supplied command and rejects nonfixture repository,
snapshot, source or patch identities before contacting Docker. The flag
`PATCH_SYNTHETIC_EXECUTION_ENABLED` defaults to false and is rejected outside `APP_ENV=test`.

The Docker daemon 29.8.2 reported Linux ARM64, cgroup v2 and the built-in seccomp profile. The
local image ID `sha256:839d58f92f8cd1fbf52e766934434133ed5c35f2d7adbdffa665ac393597ca9b`
was inspected without pulling an image. The adapter creates only uniquely named, labeled
containers and checks non-root execution, read-only filesystems, capability dropping,
no-new-privileges, memory, CPU, process, mount and network settings before starting its fixed
trusted preflight probe. The in-container checks also cover seccomp, cgroup limits, scratch,
credentials-related mounts and network interfaces.

The real probe did **not** pass: Docker reported `network=none`, while its probe reported 11
sysfs interfaces, 10 proc/socket interfaces and zero IPv4 routes. The loopback-only guard
blocked execution. The result does not prove external connectivity; the inconsistent network
view remains unresolved. One initial one-case actual-test attempt failed at preflight and five
subsequent one-case trusted-preflight diagnostic attempts also failed; **no baseline or
patched fixture test ran**. No comparison such as `BASELINE_FAILED_PATCH_PASSED` is claimed.
The adapter did not weaken its checks. A read-only label query found no remaining P4 probe
containers after cleanup.

The initial mixed focused test runs used the in-memory SQLite fixture for database-backed
worker cases despite the P4 instruction to use disposable PostgreSQL for such tests. No
application database was touched. That was a departure from the requested test constraint;
those results are not PostgreSQL evidence. The first run also found a transcribed fixture hash
error (**51 passed, 11 failed, 3 skipped**); the hash was corrected. A later mixed local run
reported **70 passed, 4 skipped**, but is retained only as local diagnostic evidence.

The reviewed PostgreSQL harness was then extended to stage the P4 tests and explicitly
deselect the three actual execution/preflight cases. Its source inventory and unchanged lock
were rechecked; 67 previously approved official wheels including uv were reverified into a
private temporary wheelhouse, with 52,738,791 response bytes including metadata. An initial
database run returned **394 passed, 0 failed, 0 skipped, 4 deselected**. After adding
cleanup-ownership and monitoring checks, the final run used the reviewed runner:

```sh
/opt/homebrew/opt/python@3.14/bin/python3.14 -I -B apps/api/evaluation/tree_sitter_pg_harness.py run \
  --python /opt/homebrew/opt/python@3.14/bin/python3.14 \
  --uv /private/tmp/repopilot-p4-artifacts.LrIb9mEr/uv \
  --uv-wheel /private/tmp/repopilot-p4-artifacts.LrIb9mEr/wheels/uv-0.13.6-py3-none-macosx_11_0_arm64.whl \
  --wheelhouse /private/tmp/repopilot-p4-artifacts.LrIb9mEr/wheels \
  --docker /Users/roshan/.docker/bin/docker --socket /Users/roshan/.docker/run/docker.sock
```

It created only container `repopilot-ts0252-pg-6c7bb7d70e671bcb` and database
`repopilot_5b1_checks_6c7bb7d70e671bcb`, checked the image, temporary storage, ownership,
SCRAM, marker, loopback and mounts, and confirmed cleanup. Its exact pytest command and
sanitized JUnit logs are in `/private/tmp/repopilot-ts0252-pg-swvmg48w` while it exists.
The selected suite reported **398 passed, 0 failed, 0 skipped, 4 deselected**, including
26 P4 synthetic/mock cases. Three deselections were the blocked P4 actual cases and one
was the separate Git-object retrieval case. Pytest emitted one `cache_dir` configuration
warning because its cache provider was disabled. The native PostgreSQL/migration suite
reported **3 passed**, the separate parser suite **120 passed**, and harness safety checks
**44 passed**. These are not evidence that the P4 Docker execution sandbox passed.

The current non-database selection reported **49 passed, 0 failed, 0 skipped, 8 deselected**;
it includes a mocked check that an exception in the cancellation monitor kills and reaps
the owned CLI process. Frontend tests reported **78 passed**, and TypeScript,
ESLint, Ruff and `git diff --check` passed. No normal database migration, model inference,
repository test execution, image pull, GitHub write or service restart was performed by this
work. The separately requested local web development server was started on localhost:3000;
its page and the existing backend health endpoints returned HTTP 200 when checked.

## Dashboard visual and accessibility pass

On 2026-11-13, the existing Next.js dashboard received a dark token system, locally
bundled Geist fonts, a responsive navigation and repository combobox, clearer signed-out
and error states, issue-row and code-search presentation, a higher-contrast preference,
and a footer with additional clearance. The existing dashboard, health, authentication and code-search endpoints and
the normal 30-second dashboard refresh were retained; demo polling remains five seconds.
The one-second update-age clock changes presentation only. The current issue-list API does
not supply issue labels; the UI shows labels only when they are present in its input.

Frontend verification on the existing Node 26.13.0 environment: **91 passed, 0 failed,
0 skipped**; TypeScript, ESLint and `git diff --check` passed. An optimized Next.js
production build also completed in a private copied-source directory using the existing
dependencies. Node 26 is outside the project's declared `>=22 <25` range, so this is
not a supported-Node release build.

A nonpersistent local WebKit preview checked a populated synthetic fixture at widths 375,
768 and 1440 pixels, plus signed-out and error states at 375 pixels. It found no horizontal
overflow at those widths. The synthetic preview exercised repository search and keyboard selection,
the `/` search shortcut, and mobile-menu Escape/focus behavior; a separate simulated
503 showed the error state with its details collapsed. The visible enabled controls in
the checked states met the 40px target measurement. Axe-core 4.14 reported no definite
violations in those states, but marked color contrast incomplete because the decorative
canvas makes the background indeterminate to the tool. Independent token tests checked
the text and semantic colors against the solid surface tokens and the primary-button
gradient endpoints. Those tests do not establish contrast for every composited state.
Lighthouse and a complete manual WCAG audit were not available, so the requested
Lighthouse scores, overall WCAG conformance and layout-shift target remain unverified.
The local frontend was restored on port 3000 after the tool-session restart and returned
HTTP 200. At the latest infrastructure check the API on port 8000 and Docker daemon were
unavailable; no normal backend service or container was restarted.

## Local dashboard service recovery (2026-11-13)

At the user's request, Docker Desktop was started after its socket was unavailable.
Existing container restart policies resumed the previously configured local services;
the `repopilot-local` API, PostgreSQL and Redis reported healthy. The existing
migration container remained exited. The host-run frontend preview was restarted on
loopback port 3000 with `API_INTERNAL_URL=http://127.0.0.1:8001`, targeting the
existing local API instead of the separate service on port 8000. The home page
returned HTTP 200, `/api/health` returned `{"ready":true}`, and an unauthenticated
`/api/auth/me` request returned HTTP 401. No migration, image build, reindex or
GitHub operation was initiated. These checks do not verify a real GitHub sign-in.

## Section-aware dashboard navigation

The top navigation now follows the visible inbox, repository and code-search sections,
including when scrolling upward or reaching the end of the page. It observes layout changes
and uses the sticky-header position; existing hash links and the mobile menu remain in use.
When account controls are hidden, the Repositories link scrolls to the visible repository panel.

On 2026-11-13, the frontend suite reported **94 passed, 0 failed, 0 skipped**; TypeScript,
ESLint and `git diff --check` passed. A local WebKit check using synthetic signed-in and
signed-out data exercised scrolling in both directions and navigation-link clicks at 1440px
and 375px. An initial desktop check using a fixed two-second startup delay did not update
the highlight; readiness was not captured in that attempt. Subsequent checks after the
dashboard rendered passed at both widths. The live dashboard health endpoint remained ready.

## P4.1 — network and mount isolation diagnosis

**Result: trusted synthetic patch execution remains blocked.** Docker CLI and Engine were
29.8.2 on `desktop-linux`, using Docker Desktop's Linux ARM64 VM; the installed Docker
Desktop CLI plugin reported 4.95.0, while the application bundle version was not verified.
The previously approved local image was present as
`sha256:839d58f92f8cd1fbf52e766934434133ed5c35f2d7adbdffa665ac393597ca9b`.
No image or package was downloaded.

Uniquely named containers were created with the existing test adapter's `--network none`,
non-root UID/GID 65534, read-only root and fixture, all capabilities dropped,
no-new-privileges, 128 MiB memory, eight processes, one CPU, bounded tmpfs and ten-second
timeout. Docker inspection found only the approved declared read-only fixture bind and a
`none` network attachment with no assigned addresses. The in-container probe independently
reported seccomp mode 2 and the existing resource and privilege checks passed. This was a
non-executing diagnostic of container state; it did not run fixture source.

`/proc/net` linked to `self/net`. `/proc/self/net/dev` and `socket.if_nameindex()` both
listed `lo` and `erspan0`, `gre0`, `gretap0`, `ip6_vti0`, `ip6gre0`, `ip6tnl0`, `ip_vti0`,
`sit0` and `tunl0`. Socket `SIOCGIFFLAGS` and sysfs showed those nine as down virtual
interfaces; `SIOCGIFADDR` found only loopback's primary IPv4 address. `/proc/self/net/if_inet6`
showed only loopback's IPv6 address. The IPv4 route table was empty; IPv6 showed the local
loopback route and rejected defaults. This is not a complete IPv4-address dump or proof of
network isolation. `/sys/class/net` had those ten interfaces plus the non-interface control
file `bonding_masters`, explaining the original 11-versus-10 count. The kernel reason for the
nine devices is not established.

Two overlapping diagnostic containers had distinct network namespace IDs and each reported
the same device names. Their individual `/proc/1/ns/net` and `/proc/self/ns/net` agreed. A
first attempt at the concurrent diagnostic had a wrapper return-value unpacking error; both
owned containers were cleaned up, and the corrected attempt succeeded. No host network or
external endpoint was probed. Read-only `/sys` exposes kernel metadata, including the control
file; the evidence does not establish that the nine interfaces are macOS-host interfaces.

`/proc/self/mountinfo` also showed read-only `/etc/hostname`, `/etc/hosts` and
`/etc/resolv.conf` mounts on the VM filesystem, absent from Docker's declared `Mounts` list.
Their exact backing-file provenance and any information exposure remain unverified; their
contents were not read. Runtime `/proc` and `/sys` mounts are separate from the sole declared
fixture bind. The policy now rejects unapproved runtime mounts and unexpected sysfs entries,
and checks IPv6 address/routes, network attachments and required inspection fields. It remains
conservative across unrecognized filesystems, route flags and kernel formats. The final real
preflight returned `preflight_network_runtime_mounts`; the independent IPv6 loopback check
passed for the observed records, but the overall preflight did not. **No baseline or patched
fixture test ran**, and no genuine worker/API/UI execution-result propagation was tested.

Synthetic tests, with network denied, ran from `apps/api`:

```sh
python -m pytest -q -p no:cacheprovider tests/test_patch_synthetic_execution.py \
  tests/test_patch_validation.py -k 'not worker and not mocked_validation and not actual'
python -m pytest -q -p no:cacheprovider evaluation/test_tree_sitter_pg_harness.py \
  tests/test_patch_proposals.py::test_before_after_comparison_only
```

The first selection reported **66 passed, 0 failed, 0 skipped, 8 deselected**. The second
reported **52 passed, 0 failed, 0 skipped, 0 deselected**, plus 14 passed subtests. These
cover mocked guard failures and comparisons, not actual fixture execution. Both emitted a
pytest `cache_dir` warning because the cache provider was disabled. Ruff passed for the two
changed Python files and `git diff --check` passed. The first attempt to invoke macOS
`sandbox-exec` inside the workspace sandbox was denied; the listed tests were subsequently
run with an operating-system network-denial profile outside it.

The reviewed disposable PostgreSQL harness's read-only prerequisite check stopped because
the verified uv 0.13.6 executable, official uv wheel and offline wheelhouse from the prior run
were missing. It did not contact Docker or PostgreSQL. The earlier 398-test PostgreSQL run
predates these changes and is not current integration evidence. No application database,
normal service, Docker context or volume was changed. Each diagnostic container was cleaned
up by ownership checks; a subsequent read-only label query found none remaining.

Before any synthetic execution, the network interfaces and runtime mounts must satisfy a
reviewed isolation policy, complete IPv4 address and metadata exposure checks must be
established, and the real preflight must pass. Before real-repository execution, a separate
reviewed untrusted-code sandbox and explicit authorization for the repository, source,
test specifications and execution are required. Production patch execution remains disabled.

## P5 — patch provider boundary and synthetic browser workflow

The patch provider registry remains unavailable. A versioned provider-neutral request now
separates fixed instructions from issue/source data and checks repository, tenant,
investigation, snapshot, source hashes, evidence IDs, citation paths and ranges before a
provider is called. Configurable request, response and timeout caps cannot exceed the stated
defaults. The worker rejects mismatched repository or tenant identities, and incomplete
provider/model/credential configuration produces sanitized failures. Recognized credential
patterns are screened, but this is not complete secret detection. The timeout is supplied to
the adapter; a future transport must enforce its own deadline and streaming bounds. No real
provider was configured or contacted and no real patch was generated.

From `apps/api`, with `TEST_DATABASE_URL` absent, a clean environment and macOS network
denial, the selected tests ran:

```sh
python -m pytest -q -p no:cacheprovider tests/test_auth_enrollment.py \
  tests/test_investigation_evidence.py tests/test_patch_provider_contract.py \
  tests/test_patch_proposals.py tests/test_patch_validation.py \
  tests/test_patch_synthetic_execution.py -k 'not postgres and not actual'
```

They reported **176 passed, 0 failed, 0 skipped, 6 deselected**. This includes the
**30-case** provider-contract suite, which also passed separately. The selected API and
worker tests used an in-memory SQLite fixture; they do not prove PostgreSQL row locking or
concurrency. The deselections were three PostgreSQL cases and three actual P4
fixture/preflight cases. Pytest emitted a `cache_dir` configuration warning because the
cache provider was disabled. Ruff passed for the changed Python files.

The existing frontend tests reported **94 passed, 0 failed, 0 skipped**; TypeScript and
ESLint passed, with network denied. The only located Node runtime was macOS ARM64
**26.13.0**, outside `>=22 <25`; no supported-Node production build was run. No runtime or
package was installed.

An existing system WebKit-based test approach was extended in
`apps/web/tests/patch-workflow.browser.swift`. A private copied-source Next.js preview ran
on loopback port 3159 using the existing Node 26 installation, with the backend URL set to
the unreachable `127.0.0.1:1`. Browser-side application fetches were intercepted by
synthetic fixtures. Three final scenarios passed: opening an investigation and evidence,
generation/queued state, diff and static check, unavailable isolated tests, approval for
review; a provider-unavailable state; and a denied proposal request. No real database or
provider was involved. Two earlier browser attempts failed on the test harness selecting an
evidence snippet instead of the proposal diff; after the selector was corrected the three
scenarios passed. This is browser UI verification with intercepted APIs, not an end-to-end
PostgreSQL or authenticated GitHub run. The preview process and its private copy were removed.

The prior 398 selected disposable PostgreSQL tests and migration 0017/drift checks predate
P5. The previously verified uv executable and offline wheelhouse were absent, so no P5
PostgreSQL or migration test ran. The P4.1 Docker isolation decision and execution preflight
were not changed or rerun; **no baseline or patched fixture was executed**. No normal
service, database, feature flag or dependency lockfile was changed. The
[release matrix](patch-workflow-verification.md#release-matrix) records the remaining
provider, Node, execution, retention and deployment blockers.

## Step P6 — verified toolchains and blocked PostgreSQL gate (2026-11-13)

The macOS ARM64 GIL-enabled CPython 3.14.10 test host used a privately retained official
Node **24.18.0**, npm **11.16.0**, and uv **0.13.6**. The Node archive
`node-v24.18.0-darwin-arm64.tar.gz` was 52,087,559 bytes and its SHA-256 was
`e1a97e14c99c803e96c7339403282ea05a499c32f8d83defe9ef5ec66f979ed1`, matching the
official Node release checksum over HTTPS. The checksum manifest's signature was **not**
verified because GnuPG and a trusted release-key ring were unavailable. The verified uv
wheel SHA-256 was `51361029b7cf91185d0092c4b356d110b4ad629e9cb11593f1e006ac72a72ca9`.
The private cache contains 66 compatible locked wheels plus that uv wheel, 50,963,767
bytes total. Their filenames, exact versions, official artifact URLs, sizes and SHA-256
hashes are in `apps/api/evaluation/p6-toolchain-artifacts.json`; the sanitized actual
verification record is `apps/api/evaluation/p6-toolchain-verification.json`. The API
lockfile SHA-256 remained `40139126d31b521cc5377f1333b22d7c18de733840d1c63d848309ba7ad9c09a`.
Tree-sitter remained 0.25.2 and its eight locked grammar versions were not changed.

The offline toolchain check verified the entire installed Node tree against its verified
archive, the uv executable and the wheel hashes. Seven synthetic artifact-guard tests
passed. A separate first attempt to invoke those tests via `python -I -m unittest` failed
with one loader error because isolated mode omitted the repository from the import path;
the supported direct-script invocation passed all seven. The cache resides in
`~/Library/Application Support/RepoPilot/toolchains/p6` under owner-only directories;
the downloaded archives and wheels are mode 0600, while extracted Node files retain their
archive modes behind those directories. It contains no credentials, private repository-source
corpus or model weights.
See [the durable preparation and harness commands](tree-sitter-disposable-postgres.md#p6-persistent-test-toolchain).

In a copied frontend workspace, Node 24 passed TypeScript, ESLint, **94 tests** and the
production build. The 14 patch component/proxy tests were also rerun separately and passed;
they are included in the 94-test total. Existing installed dependencies matched 359 lockfile package versions;
this was not a clean `npm ci` or independent integrity verification of every installed
file. The default `~/.npm/_cacache` directory was absent, so the persistent Node toolchain
alone cannot restore a missing frontend dependency installation. An initial build with symlinked `node_modules` warned that 27 standalone trace files
were omitted. Repeating the build with a private full dependency copy passed without that
warning and the standalone server and Next.js server files were present. Against that
production build, **three synthetic WebKit scenarios passed**, with application API calls
intercepted and the backend set to an unreachable loopback address. The first browser
attempt exposed a test-window visibility problem; the test-only window activation was
corrected. The owned preview was stopped after testing.

An offline disposable Python environment passed `uv lock --check --offline`, **44 mocked
harness safety tests**, **120 synthetic native parser tests**, and the selected suite below
with **176 passed, 0 failed, 0 skipped and 6 deselected**. The six deselections comprise
three PostgreSQL cases and three real patch-sandbox fixture/preflight cases. The selected
database-backed cases used in-memory SQLite; they do not establish PostgreSQL locking.
The native and selected runs each emitted one `cache_dir` pytest configuration warning
because the cache provider was disabled. Ruff passed. Source staging hashed and rechecked
166 current working-tree files and fixtures; the copy is not represented as a Git commit.

```sh
python -m pytest -q -p no:cacheprovider tests/test_auth_enrollment.py \
  tests/test_investigation_evidence.py tests/test_patch_provider_contract.py \
  tests/test_patch_proposals.py tests/test_patch_validation.py \
  tests/test_patch_synthetic_execution.py -k 'not postgres and not actual'
```

The active Docker context was `desktop-linux`. The daemon and the approved local pgvector
image were initially inspectable, but the configured Unix socket disappeared before the
reviewed runner could create a container; its actual output was `BLOCKED: explicit local
Docker Unix socket is unavailable`. No disposable container, database, real isolation
checks, P5 PostgreSQL tests, Alembic 0017 upgrade or separate PostgreSQL schema-drift check
ran in P6. Earlier disposable PostgreSQL results predate the P5 provider changes. The
runner was extended to require the P5 provider and tenant cases, including selected
parameterized identities, rather than silently treating their absence as success. No normal
service was restarted, no application database was contacted, and no production migration
was applied. The private staged source and logs remain available for inspection; the
persistent cache deliberately excludes them.

The live patch provider remains unconfigured. The patch execution sandbox remains blocked
by the earlier isolation preflight; no before/after fixture executed. Real provider use,
real-repository execution, normal database migration, GitHub publication and deployment
require their respective separate approvals and security review. RepoPilot is not production ready.

## Step P7 — local Ollama patch adapter (2026-11-14)

The inspected host reported macOS **27.2.1**, Apple **M6**, **16 GiB unified memory**,
and about **30 GiB available** on the default home/model volume; the project volume reported
about **774 GiB available**. The base Python was GIL-enabled CPython **3.14.10** on ARM64.
No Ollama executable was found on the checked PATH or standard application locations, no
default Ollama model manifest/blob directories were present, and the read-only local
`/api/tags` request could not connect to `127.0.0.1:11434`. `OLLAMA_MODELS` was unset.
No MLX or llama.cpp Python package was found in the checked base interpreter, and no
`llama-cli` or `llama-server` executable was found on the checked PATH. These observations
are not an exhaustive search of all environments or custom locations.

For a later separately approved experiment, `qwen2.5-coder:7b` is the conservative initial
candidate: [Ollama's listing](https://ollama.com/library/qwen2.5-coder) gives approximately
**4.7 GB**. The 14B variant is listed at **9.0 GB**, and the
[qwen3-coder:30b listing](https://ollama.com/library/qwen3-coder) gives **19 GB**. Model
files, context buffers, the OS and
other applications share the Mac's memory; artifact size alone does not guarantee that a
model will fit or perform well. No model or runtime was installed or downloaded, and no
inference or real-source transmission was performed.

The new local adapter is disabled by default and uses strict numeric IPv4 loopback,
proxy/redirect rejection, a bounded async transport and an explicit model digest. Its
metadata preflight requires cloud-disabled status and local GGUF completion metadata before
sending bounded evidence snippets. The Ollama status response is self-reported and its
`/api/status` endpoint is experimental; this does not authenticate the daemon, eliminate
the model-tag race, or enforce operating-system egress restrictions. The shared source,
evidence, diff and publication checks remain authoritative. Cancellation closes the HTTP
request and fences publication, but does not guarantee server-side generation stops.

With all network access denied, the selected synthetic backend suite reported **234 passed,
0 failed, 0 skipped, 6 deselected**; the 58-case Ollama suite is included. Three deselected
cases require PostgreSQL and three require the actual blocked patch sandbox. The run emitted
one pytest `cache_dir` configuration warning because its cache provider was disabled.
Fourteen existing frontend patch/proxy tests passed on Node 24.18.0. The first Ollama test
attempt reported **26 passed, 26 failed and 2 setup errors**: mock HTTPX responses had been
eagerly consumed and the test file lacked its authentication fixture. After the test-only
stream and fixture were corrected, the selected suite passed. Ruff and `git diff --check`
were run separately. The normal application database was not contacted; SQLite-backed test
fixtures do not establish PostgreSQL locking or concurrency.

Docker's configured socket was absent, so no P7 PostgreSQL tests, migration or schema-drift
check ran. No normal service or feature flag was changed. Runtime/model installation,
local inference, any real-source transmission, normal migrations, real test execution and
deployment each remain subject to their respective separate approvals and required security
review. Patch execution remains blocked by the existing sandbox isolation gate.

## Step P7.1 — official Ollama and model artifact verification (2026-11-14)

The host was macOS 27.2.1 on Apple M6 with 16 GiB unified memory. Before installation,
the home volume had approximately 29.8 GiB available; the post-pull checks reported
approximately 24.5–25.1 GiB available as APFS free space changed. No existing Ollama app,
executable, default `~/.ollama` configuration,
model store, process or listener on port 11434 was found in the checked locations. The
existing default home configuration remained untouched.

The official [Ollama 0.40.16 release](https://github.com/ollama/ollama/releases/tag/v0.40.16)
disk image was **229,996,388 bytes**, SHA-256
`b48d74a2d8c6a0592c816a4f85643d8d8608ad592abafbe95c04128a73c398c6`, matching both the
release metadata and the official checksum file. The checksum file itself had SHA-256
`99d2505da1bfa40d582e295825d232763823667b495bd73e2145e94671c28eb9`; no separate
checksum-file signature was verified. The app and its CLI passed deep/strict macOS code
signature checks. The signer was **Developer ID Application: Infra Technologies, Inc
(3MU9H2V9Y9)**, with a stapled notarization ticket; Gatekeeper accepted the app as
**Notarized Developer ID** both before and after copying. Inside the managed execution
sandbox, the initial signature check reported an invalid signature with the authority
unavailable, and Gatekeeper reported a signing-subsystem error. The same checks passed
when macOS signing services were accessible, without bypassing Gatekeeper. The owner-only installation and
retained disk image are under `~/Library/Application Support/RepoPilot/toolchains/ollama-p71`;
the installed app used 709,908 KiB according to `du -sk`.

The single approved model, `qwen2.5-coder:7b`, was pulled using `/api/pull`. Its official
registry manifest was independently retrieved and hashed to
`dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`; the local model
listing reported the same full digest and **4,683,087,561 bytes**, GGUF, Q4_K_M and 7.6B
parameters. Every referenced object was independently rehashed:

| Object | Bytes | SHA-256 |
| --- | ---: | --- |
| Model weights | 4,683,074,048 | `60e05f2100071479f596b964f89f510f057ce397ea22f2833a0cfe029bfc2463` |
| Config | 487 | `d9bb33f2786931fea42f50936a2424818aa2f14500638af2f01861eb2c8fb446` |
| System text | 68 | `66b9ea09bd5b7099cbb4fc820f31b575c0366fa439b08245566692c6784e281e` |
| Template | 1,615 | `1e65450c30670713aa47fe23e8b9662bdf4065e81cc8e3cbfaa98924fcc0d320` |
| License | 11,343 | `832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e` |

Ollama 0.40 stored the 858-byte registry manifest as a blob and a versioned alias pointing
to it. The 1,021-byte legacy manifest is a wrapper with an extra reference to that same
registry manifest; its own SHA-256 is
`4aaba1ee422af93aad53ecbdfc8a159770cf254a9950b7a4304cf9ee3555ef31`. The first
filesystem check assumed the legacy file was the raw registry manifest and stopped; a
separate check verified the wrapper, alias target and raw manifest bytes. This was a storage
layout difference, not a discrepancy between the registry digest and the locally reported
model digest. The model store contains **4,683,093,640 regular-file bytes**; its allocated
space was **4,683,116,544 bytes** when measured. A private sanitized inventory and official
registry manifest are retained in the installation directory. Registry SHA-256 establishes
object identity but is not an independent publisher signature for the model.

To enforce the **7 GiB** transfer cap, the new daemon ran in a verified macOS sandbox that
allowed outbound connections only to a byte-metered loopback HTTPS tunnel. The tunnel
allowed the official registry and its independently confirmed exact CDN hostname only;
TLS was not intercepted. The first pull attempt stopped after **11,613** metered bytes
because the CDN was not initially allowlisted. A direct registry response confirmed that
exact CDN redirect before the pull resumed. Across both attempts the tunnel measured
**4,689,552,585 bytes**, including TLS/protocol overhead and any retries. The installer body
was **229,996,388 bytes** and three recorded metadata bodies totaled **38,778 bytes**: the
measured subtotal was **4,919,587,751 bytes**, below the **7,516,192,768-byte** cap. Some
small direct-request headers and IP-level overhead were not measured; 16 MiB was reserved
for unmetered overhead rather than presenting the subtotal as an exact NIC byte count.

The daemon used a separate private home and model directory, `OLLAMA_HOST=127.0.0.1:11434`,
`OLLAMA_NO_CLOUD=1`, and a private `server.json` with `disable_ollama_cloud: true`. Server
logs and `/api/status` reported cloud disabled. The owned daemon ran as UID 501 (`roshan`);
`lsof` showed only `127.0.0.1:11434` as its listener. For a later metadata-only check it
was restarted with **all daemon egress denied**; RepoPilot's actual `check_readiness()`
passed without changing feature flags. The status response is self-reported and does not
authenticate a future process listening on the same port. The daemon automatically generated
a private local key in its isolated home with mode 0600; no account sign-in occurred.

Only `/api/status`, `/api/version`, `/api/tags`, `/api/ps`, `/api/show` and the approved
`/api/pull` were called. The server logs contained no chat, generate or embedding API routes,
and `/api/ps` reported no loaded model after the pull and metadata checks. This is evidence
for the performed operations, not proof about unrelated processes. Both owned Ollama servers
and the metering proxy were stopped; no port 11434 listener or Ollama login item was found
afterward. No RepoPilot service, normal database or feature flag was changed. No inference,
issue/source transmission, patch job or repository test ran. A separately approved synthetic
inference test and an independently reviewed daemon/egress boundary are required before
any model-generated patch or real-source use.

## Step P7.2 — local synthetic inference (2026-11-14)

**Result: incomplete.** The verified Ollama 0.40.16 and `qwen2.5-coder:7b` model
performed two local inference requests, but both returned `insufficient_evidence` and neither
produced a candidate diff. The actual RepoPilot adapter rejected the second result with
`local_model_insufficient_evidence`. No generated candidate passed the complete static
validation contract; patch execution and correctness remain unverified.

Before inference, the installed app's deep/strict signature and Gatekeeper assessment
passed. Its recorded app CDHash remained `baff23feb8d1ad84c951e7e21f16d51f59f943e7`,
and the retained installation image matched the P7.1 SHA-256. The local model manifest
matched `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`;
all five referenced model blobs were rehashed successfully. No artifact was downloaded.
The port was initially unoccupied. macOS reported 16 GiB physical memory, a 79% system
memory-free pressure metric, zero swap used and approximately 25.1 GiB free disk space.
The pressure metric is not a precise measurement of unused RAM.

The test started the recorded private executable with a private home and model directory,
`OLLAMA_HOST=127.0.0.1:11434` and `OLLAMA_NO_CLOUD=1`. Its private `server.json` also
disabled cloud. The daemon reported cloud disabled, and the independently inspected listener
belonged to the owned daemon PID and UID 501 at numeric loopback only. Read-only process
inspection matched the signed executable path. A macOS sandbox denied non-loopback network
connections for the test supervisor and daemon; a canary confirmed loopback connectivity and
denial of a reserved non-loopback connection. The client used direct loopback without proxy
variables; the actual provider also uses `trust_env=False` and disables redirects. The
daemon's local-only metadata is not by itself process authentication, and this temporary
boundary is not a production security review or a guarantee against a malicious local peer.

Two initial daemon starts ended before inference because the temporary harness could not
complete process inspection: macOS would not execute the setuid `/bin/ps` inside the
sandbox. Both were stopped and reaped, with zero model requests. The test-only supervisor
then used read-only `libproc` APIs for process identity and sampled RSS while preserving the
same network and listener checks. The successful preflight confirmed the exact model digest,
GGUF completion capability, cloud-disabled status and no model loaded before inference.

The first request was intended to supply this original synthetic source and issue. Its exact
outgoing request body was not retained, so the historical bytes received by the server or
model cannot be independently established:

```python
def add(a: int, b: int) -> int:
    return a - b
```

> The add function incorrectly subtracts the second argument. It should return the sum.

Its source SHA-256 was
`9445c47952abb8a7fc5d4a905d55b5be05771df1d69362ec597f9a50f7ede40d`. The direct
non-streaming `/api/chat` call used the existing JSON schema, temperature zero, an 8,192-token
context and a 1,024-token generation limit. It completed in **12.356 seconds**, with 620
prompt tokens and 241 generated tokens. The response was schema-valid but abstained,
claiming the implementation was missing. Replaying that unchanged response through the
existing provider validation logic returned `local_model_insufficient_evidence`; no diff was
available for validation. The replay was local validation only, not another inference call.

The second request used the actual RepoPilot Ollama provider and a separate original fixture:

```python
def subtract(a: int, b: int) -> int:
    return a + b
```

> The subtract function incorrectly adds the second argument. It should return the first argument minus the second.

Its source SHA-256 was
`d95d69ddc17091cc1064e45765706616a84f7558bba4b57dc1b968d3b3bc8b73`. The test used the
existing adapter, intended to send the synthetic repository, snapshot, file, evidence and
citation identities and bounded source snippet, with its unchanged 2,048-token generation limit and 30-second
deadline. It completed in **9.409 seconds**, with 627 prompt tokens and 256 generated tokens.
The response was schema-valid but again claimed the implementation was absent and abstained;
the provider returned `local_model_insufficient_evidence` before any candidate diff could be
validated. The retained response and stated test setup are observable, but the original
request bodies and the model's internal input are not retained. The reason for its abstention
is not established. No response was repaired or retried.

The model loaded successfully, and both requests completed while the daemon remained alive.
Sampled peak combined daemon/runner RSS was **5,284,970,496 bytes** for the first request and
**5,331,992,576 bytes** for the second. The lowest sampled system memory-free pressure metric
was 43%, and observed swap use remained zero. RSS is sampled, can double-count shared pages
and may omit some GPU/unified-memory use; it is not a hard memory limit. The monitor did not
trigger. The server had one loaded model before shutdown, then exited normally with status
zero; the owned daemon and observed runner were reaped, and port 11434 had no listener after
cleanup. No model remained loaded by that stopped server. The private, owner-only record is
`~/Library/Application Support/RepoPilot/toolchains/ollama-p71/p72-20261114T034624Z-3ce02867`;
its response files contain only the synthetic test material.

With all network access denied, the focused Ollama-provider, provider-contract,
patch-validation and proposal suite reported **143 passed, 0 failed, 0 skipped and 1
deselected**. The deselected case requires PostgreSQL concurrency. A pytest `cache_dir`
warning resulted from disabling the cache provider. Tests using an in-memory SQLite fixture
do not establish PostgreSQL behavior. From `apps/api`, the selected test command was:

```sh
env -i PATH=/usr/bin:/bin HOME=/nonexistent PYTHONDONTWRITEBYTECODE=1 \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 sandbox-exec -p '(version 1)(allow default)(deny network*)' \
  ./.venv/bin/python -I -B -m pytest -q -p no:cacheprovider \
  tests/test_ollama_patch_provider.py tests/test_patch_provider_contract.py \
  tests/test_patch_validation.py tests/test_patch_proposals.py -k 'not postgres'
```

Ruff and `git diff --check` passed. No normal database,
application service or feature flag was changed. No real repository or issue was supplied,
and no generated code, patch fixture or external test was executed. Patch execution remains
blocked by the existing sandbox gate; further local inference and any real-source use need
separate authorization.

## Step P7.3A — offline abstention investigation (2026-11-14)

**Result: cause unresolved.** The P7.2 private directory retains both synthetic response
envelopes, a summary and the daemon log, but no outgoing HTTP request body. The log reports
`OLLAMA_DEBUG_LOG_REQUESTS:false`, so it cannot independently establish the exact bytes
received by the daemon or the prompt ultimately presented to the model. The historical
synthetic fixture hashes and response identities are recorded; other per-request UUIDs were
not preserved in the response, so a byte-for-byte historical request cannot be reconstructed.
The previous P7.2 statements above have been qualified accordingly.
Read-only SHA-256 checks during this investigation identified `first-response.json` as
`670168d35652e32378fb866a38ad9f90009d090e23ddabde73611835461e667c`,
`second-response.json` as `3efee668c244a9f87e4c13a2094d4dd27bc6e310fc21f809b033e63ca1ea8065`,
`summary.json` as `17902f829572be0ffe882038a3f9bf1e1a135163dedd41562e3d215fd5fa187a`,
and `server.log` as `481b972f01045b9cc6b028c51ffe00b21b3283298e3e9173b19ebb3884e1320b`.
These hashes record this read; they do not retroactively authenticate the original request.

Both retained responses decode as the existing `_LocalDraft` schema, have `done: true` and
`done_reason: stop`, and contain `status: insufficient_evidence` with an empty `diff`. The
first reports 620 prompt and 241 generated tokens; the second reports 627 prompt and 256
generated tokens. The daemon log reports `truncated = 0` for both. There is no retained
provider error in either response; RepoPilot subsequently maps the second abstention to
`local_model_insufficient_evidence`. The model's explanations claim that the function
implementations were missing, but that claim does not establish what it actually received.
The token and truncation observations likewise do not prove that every intended input field
survived daemon-side processing.

An offline mocked-transport reconstruction traced the current path from synthetic
`PatchContext`, through `build_candidate_request` and the Ollama adapter, to the final JSON
HTTP request. For both P7.2 fixture texts and source hashes, the intercepted user message
contains the issue description, pinned synthetic identity, allowed path, file hash, evidence
and citation, line range and exact function implementation in `snippets[*].text`. Its
system message asks for a minimal diff for supplied evidence-backed files, treats source and
issue content as untrusted data, describes the narrow unified-diff headers, and permits
abstention. It does not explicitly identify `snippets[*].text` as the source-code field;
whether that presentation contributed to the model's answers is unverified. The system and
user messages are ordered correctly. The request sets `truncate` and `shift` to false;
current adapter limits include an 8,192-token context and 2,048 generated tokens. The first
P7.2 direct request was recorded as having used a 1,024-token generation limit. Source is
rejected by sensitive-input checks rather than silently redacted, and snippets outside the
evidence window are excluded. The exact historical serialized messages were not recovered.

At P7.3A the generated JSON schema was a flat strict object: all six fields (`status`, `diff`,
`rationale`, `uncertainty`, `evidence_ids`, `source_files`) are required, extra fields are
forbidden, and the status enum permits `candidate` or `insufficient_evidence`. It has no
discriminated union or default branch. Its shape rules permit an empty diff even when status
is `candidate`; a focused test confirms that the existing deterministic diff validator still
rejects such a candidate. Valid mocked candidate and abstention branches both remain
supported. No evidence establishes that this permissive shape, field ordering, JSON
presentation, instructions, schema processing or model behavior caused the abstentions.
No production prompt, schema, parser, endpoint or validation logic was changed speculatively.

The added synthetic regressions check both fixture payloads, evidence and source identities,
the UTF-8 request-byte limit, a mocked valid diff, missing-source fail-closed behavior, an
ambiguous-issue abstention, schema-valid empty-candidate rejection and worker recording of
an abstention without a patch. Existing tests cover wrong hashes, paths, evidence references,
proxy and redirect rejection, cancellation, and omission of unrelated source and credentials.
Missing source is rejected before the provider call; it is not converted into a fabricated
model response. A model abstention is stored by the worker as a sanitized failed outcome, not
as a successful fix. Static validation alone cannot establish semantic correctness.

With all networking denied, the selected suite reported **151 passed, 0 failed, 0 skipped,
1 deselected**. The deselected test requires PostgreSQL; some selected worker tests use an
in-memory SQLite fixture and do not establish PostgreSQL locking behavior. Pytest emitted one
`cache_dir` warning because the cache provider was disabled. Ruff and `git diff --check`
passed. No Ollama server, inference, Docker, PostgreSQL, real source, generated code or
external patch fixture was run. No normal service, feature flag, database or retained P7.2
evidence was changed.

For the next separately approved experiment, make one bounded synthetic request through the
actual local provider in the reviewed loopback-only environment, capturing the exact outbound
synthetic request bytes and response privately before checking the existing validators. This
would establish what the adapter sent in that new run, not what the model internally attended
to or what happened in P7.2. Further model inference, real-source use and patch execution
require their own approvals and security gates.

## Step P7.3B — one instrumented synthetic inference (2026-11-14)

**Result: incomplete.** Exactly one local inference request was sent through the actual
RepoPilot Ollama provider. The model returned `insufficient_evidence` and no candidate diff,
so model-generated patch validation and execution remain unverified. The previous P7.2
abstentions remain separate historical observations.

Before the request, the installed Ollama app and CLI passed macOS signature verification;
Gatekeeper accepted the app as a notarized Developer ID application signed by Infra
Technologies, Inc (3MU9H2V9Y9). The app's CDHash matched the P7.1/P7.2 record,
`baff23feb8d1ad84c951e7e21f16d51f59f943e7`. The runtime reported version 0.40.16. The
registry-manifest bytes and local model manifest matched
`dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`, and all five referenced
blobs were rehashed successfully. The model was `qwen2.5-coder:7b`, GGUF Q4_K_M. Port 11434
was unoccupied before startup; the private cloud-disabled configuration was unchanged.

The owned daemon ran as UID 501 from the verified private CLI, with its only 11434 listener
at `127.0.0.1:11434`. Its logs and status reported cloud disabled. A macOS sandbox restricted
the test supervisor and daemon to loopback networking; a canary confirmed loopback access and
denial of a reserved non-loopback connection. The client had no proxy environment and used
the existing provider's no-redirect, `trust_env=False` HTTP configuration. These measures
are evidence for this synthetic run, not a general guarantee that a local daemon or peer is
trustworthy for real source.

A test-only transport wrapped the real HTTP transport, without changing the prepared request,
and wrote the exact synthetic JSON body before delegation. It captured **3,161 bytes** at
`2026-11-14T16:48:18.181498+00:00`, SHA-256
`21b4da153461a540f4c5fd250ae5498e312cee27e1ea00ee7d1824be999dc32f`.
The controller verified the body contained the complete synthetic function, issue, file and
evidence identities, source SHA-256, existing patch instructions and current JSON schema.
It used the provider's unchanged system/user message order, temperature zero, 8,192-token
context, 2,048-token output limit, non-streaming response and 30-second provider deadline.
The wrapper allowed one chat request with HTTP retries disabled; the daemon log recorded one
`POST /api/chat`. A prior mock-only recorder check ran with all networking denied and did not
invoke a model.

The captured complete HTTP response had status **200**, contained **1,017 bytes**, and has
SHA-256 `7b6e4d7ba6153dd64c4e036941bd886526fd181a26f23154fd93326ddb9874f7`. Its response
envelope reported the expected model, `done: true`, `done_reason: stop`, 622 prompt tokens
and 251 generated tokens; the daemon log reported `truncated = 0`. The structured object was
schema-valid with `status: insufficient_evidence` and an empty diff. The existing provider
returned `local_model_insufficient_evidence`, an abstention rather than a transport failure.
The provider validated the input context, but no candidate existed for changed-file identity,
evidence or diff validation; no result was repaired, applied to a workspace or executed.

The model's unchanged response says it saw a function signature and one code line but lacked
the full implementation. The captured request contained the whole two-line synthetic file,
yet its file metadata supplied only path, file ID and hash, while its snippet metadata gave
start and end lines without a file-total or end-of-file marker. The instructions did not
explicitly declare the snippet complete. This is a concrete representational gap and a
plausible reason for caution by the model, but the model's explanation does not prove its
internal cause. No contradictory instruction or other causal defect was established.

The provider call took **10.741 seconds**. Peak sampled combined daemon/runner RSS was
**5,389,811,712 bytes** (about 5.02 GiB); the lowest sampled system memory-free pressure
metric was 53%, with zero observed swap. RSS sampling is not a hard limit and may double-count
shared pages or omit GPU/unified-memory use. The daemon had one loaded model before shutdown,
then exited with status zero; its owned runner was gone and port 11434 was closed. The
installed model was retained. The owner-only private record directory is
`~/Library/Application Support/RepoPilot/toolchains/ollama-p71/p73b-20261114T164816Z-6e02a9e5`;
its directory is mode 0700 and files are mode 0600. Full synthetic request and response bodies
are retained there, not in repository documentation.

The network-denied offline provider, generation-contract and static-validation selection
reported **124 passed, 0 failed, 0 skipped and 0 deselected**. Pytest emitted one `cache_dir`
warning because the cache provider was disabled. Ruff and `git diff --check` passed. No
normal application service, feature flag or database was changed. No real source, generated
code, PostgreSQL, Docker patch fixture or external test ran.

A possible next separately authorized experiment is to add and test trustworthy snippet
completeness metadata derived from the verified source, then perform one bounded synthetic
inference to evaluate it. This would not prove the P7.3B model's reasoning. Further model
calls, real-source transmission, patch execution and normal-service activation each require
their own authorization and security review.

## Step P7.4 — source coverage and one synthetic retest (2026-11-15)

**Result: incomplete.** A versioned source-coverage contract was added and tested, and
exactly one local synthetic request was sent through the existing Ollama provider. The
model returned `insufficient_evidence` with no diff. No model-generated candidate passed
static validation, and no generated code or patch was executed.

Each emitted snippet now includes `source-coverage-v1` metadata. `COMPLETE_FILE` requires
an internal pinned-file identity record that matches the source path, file and snapshot
IDs, commit, repository and tenant, SHA-256 and independently recorded full byte length;
the emitted snippet must cover all verified bytes. `BOUNDED_EXCERPT` requires the same
verified file record but covers only a proper subset. Without such a complete record the
classification is `UNKNOWN_COVERAGE`, with no claimed full-file hash, byte count, line count
or absolute byte offsets. Provided line ranges continue to derive from the existing evidence
and LF-based reconstruction. Verified byte ranges are zero-based and end-exclusive.
Coverage notices are separate from the source-text field. The prompt still permits
abstention and treats issue and source contents as untrusted data.

The pinned-file record is an internal trust input, not proof that arbitrary caller-supplied
metadata is authentic. It must originate from an authenticated pinned inventory. The
current `IndexedFile` schema retains a content hash but not an independently persisted
original byte length; therefore ordinary database-backed contexts do not construct such a
record and remain `UNKNOWN_COVERAGE`. This change does not claim a complete repository
inventory and makes no database or migration change. The synthetic fixture used a fixed,
separate record with the expected 49-byte length and SHA-256
`9445c47952abb8a7fc5d4a905d55b5be05771df1d69362ec597f9a50f7ede40d`.

Offline mocked-transport tests covered the complete fixture, a UTF-8 middle excerpt,
missing and incomplete identities, a final visible line without proof, mismatched snapshot,
file, path, hash and size, invalid line and byte ranges, unchanged evidence references,
revalidation inside the provider and the existing strict diff validator. A synthetic worker
case confirms the current database-backed path remains unknown. A mocked valid candidate
passed existing validation; this was not model inference. The final network-denied selected
suite reported **176 passed, 0 failed, 0 skipped and 1 deselected**. The deselected case
requires PostgreSQL; selected worker cases use an in-memory SQLite fixture and are not
PostgreSQL evidence. Pytest emitted one `cache_dir` warning because the cache provider was
disabled. Ruff and `git diff --check` passed. An initial standalone mock-request fingerprint
command failed because it omitted the synthetic test settings; after loading the test-only
configuration, it succeeded without contacting Ollama.

The final mocked request was **4,001 bytes**, SHA-256
`423ad6fde4f09064c7c1f5a3822d32a0b3bce7d0155fe54bdc211da9b0a5f88e`. Before the real call,
Ollama 0.40.16's app and CLI signatures, recorded app code hash and pinned model manifest
and all five referenced blobs were verified. The model digest was
`dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`. The private daemon
ran as the expected local user on `127.0.0.1:11434`, with cloud disabled and the reviewed
macOS sandbox denying non-loopback connections. The client disabled proxy routing and
redirects. A sandbox canary confirmed the network boundary. These checks do not establish
production isolation for real source or protection against every local threat.

A test-only recording transport captured the exact real request before passing the same
prepared request to the normal HTTP transport. Its bytes and SHA-256 matched the offline
mocked request; the body contained the synthetic issue, source, evidence identities and
verified `COMPLETE_FILE` notice. The request had the existing structured-output schema,
8,192-token context, 2,048-token output limit, temperature zero, non-streaming response and
30-second provider deadline. One chat request was allowed, with retries disabled. The server
log recorded one `/api/chat` call. A separate mocked recorder self-test made no model call.

The actual response was HTTP **200**, **928 bytes**, SHA-256
`88523fb2651fa10307ebb285e88434e3d7c8dc38eba8f3ac0e785de8cd545b58`. The response was
schema-valid, with `done: true`, `done_reason: stop`, 856 prompt tokens, 244 generated tokens
and `status: insufficient_evidence`; the server log reported `truncated = 0`. The provider
returned `local_model_insufficient_evidence`. Its input identity and evidence checks ran,
but there was no candidate on which to run changed-file, output-evidence or diff validation.
The model again claimed the code was absent, although the captured outgoing body contained
the complete synthetic file and explicit complete-file notice. This result does not prove
what the model internally attended to or establish the cause of this or earlier abstentions.
No response was repaired or retried.

The provider call took **10.135 seconds**. Peak sampled combined daemon/runner RSS was
**5,393,154,048 bytes** (about 5.02 GiB); the lowest sampled system memory-free pressure
metric was 43%, and observed swap remained zero. Sampling is not a hard memory limit and
may double-count shared pages or omit GPU/unified-memory use. The owned daemon exited with
status zero, its runner exited and port 11434 closed. The model was retained. The private
record directory is mode 0700 and its files mode 0600:
`~/Library/Application Support/RepoPilot/toolchains/ollama-p71/p74-20261115T034529Z-b773699e`.
Full synthetic request and response bodies are retained there, not in this documentation.

No real repository or issue was sent to the model. No normal database, Docker, PostgreSQL,
production service or feature flag was changed. Real-source use, a durable independently
verified size-provenance design for indexed files, further inference, patch execution and
normal-service activation require their own review and authorization.

## Step P7.5 — offline patch contract comparison (2026-11-15)

**Result: abstention cause unresolved.** The retained P7.2 responses and the P7.3B and
P7.4 synthetic request/response records were reviewed without modification. All four
actual calls returned `insufficient_evidence`; the P7.2 outgoing bodies were not retained.
The P7.3B and P7.4 request bodies contained the synthetic source, and P7.4 included the
verified complete-file notice. The model's explanations are observations, not proof of
its internal reasoning. No model server or inference was run in P7.5.

The current system instructions request a minimal evidence-backed candidate, treat issue
and source contents as untrusted data rather than commands, specify the supported unified
diff format, and permit abstention. They state that a proposal does not establish a fix;
they do not require a proven root cause or a tested fix before a proposal. No contradiction
was established. Missing source, ambiguous behavior, insufficient context, prompt presentation,
model behavior and structured-output grammar remain distinct possibilities; no offline
comparison establishes which, if any, caused the prior abstentions.

The model-facing schema is a flat strict object requiring `status`, `diff`, `rationale`,
`uncertainty`, `evidence_ids` and `source_files` for both statuses. It has no default branch
or discriminated union. It permits an empty candidate diff at the JSON-schema shape level;
the existing deterministic diff validator rejected it before publication. It also requires
empty or otherwise supplied diff, evidence and file-inventory fields for abstentions even
though the provider returns an abstention before validating a candidate. These are schema
limitations, not evidence that the model preferred abstention.

The production `_LocalDraft` structured parser now rejects a `candidate` with an empty diff
before calling the diff validator. Such a response already failed with the same sanitized
`local_provider_invalid_response` outcome. An `insufficient_evidence` response may still
carry an empty diff. The model-facing JSON schema and prompt are intentionally unchanged:
its candidate-empty shape gap remains visible, and no unverified conditional or union grammar
was introduced into the live request. Existing snapshot, source-hash, path, evidence, patch
size and unified-diff validators remain unchanged. No persisted or public API format changed.

A test-only alternative uses shorter task instructions and a discriminated candidate or
abstention schema. Candidates retain the nonempty diff, evidence IDs and exact source-file
identities; abstentions instead include a missing-evidence description. The alternative
abstention shape is incompatible with the current production parser, and existing six-field
abstentions are not accepted by the alternative schema. It is not registered or enabled;
a compatibility adapter and reviewed Ollama schema support would be required before using it.

Both complete requests were captured through HTTPX mocked transports with networking denied,
using the same original synthetic file, issue, file and evidence identities, coverage metadata,
roles, model tag and generation settings. The production request remained **4,001 bytes**,
SHA-256 `423ad6fde4f09064c7c1f5a3822d32a0b3bce7d0155fe54bdc211da9b0a5f88e`, exactly matching
P7.4. Its system message was 867 characters and its compact schema 1,061 bytes. The test-only
prompt-plus-schema alternative was **4,557 bytes**, SHA-256
`83580ba6cb2059dfac5736e506654f8dd1d32f461df1ba1007072375ecf989cb`; its system message was
614 characters and its compact schema 1,874 bytes. A shorter instruction therefore did not
make the whole serialized alternative smaller. A separate prompt-only mock variant retained
the current schema and user payload; it was **3,744 bytes**, SHA-256
`2617f22820604e2ebc093167d11693a98640cdf9fa5d64dde55e7e70d0b41e39`. These are byte counts,
not model token counts or evidence that any variant will improve actual generation.

Synthetic mocked tests exercised a valid minimal candidate through the actual existing
provider and static validators, explicit abstention, missing or mismatched source and snapshot,
unknown-coverage context, ambiguous and unrelated issues, unsupported operations, invalid
paths and evidence references, empty or oversized diffs, and alternative-schema compatibility.
The network-denied selected suite reported **192 passed, 0 failed, 0 skipped and 1 deselected**.
The deselected case requires PostgreSQL; selected worker cases use an in-memory SQLite fixture
and do not establish PostgreSQL behavior. Pytest emitted one `cache_dir` warning because the
cache provider was disabled. Ruff and `git diff --check` passed. No Docker, PostgreSQL, Ollama
inference, generated code, real repository data or normal application service was used.

A possible next experiment, subject to separate explicit approval, is one bounded synthetic
call using the prompt-only test variant with the same file, user data, model and schema as the
retained P7.4 request. Capturing its exact request and response would change the system prompt
only relative to that baseline; a single trial would still not establish general effectiveness
or prove the model's reasoning. Real-source handling, independently persisted file-size
provenance, patch execution isolation and production activation remain separate blocked gates.

## P8 — Local structured-edit generation (2026-11-15)

### Implementation and offline checks

P8 adds `app.modules.patches.source_edits`: it verifies a `CandidateRequest` by rebuilding
its `PatchContext`, binds each exact whole-line edit to an authorized file, verified source
hash, and cited evidence range, rejects ambiguity and overlaps, constructs a canonical
unified diff in memory, and invokes the existing `validate_patch`. It never opens a source
path or applies the generated change. The Ollama adapter accepts strict `candidate` /
`insufficient_evidence` output; the direct-diff strategy remains selectable with
`PATCH_LOCAL_MODEL_STRATEGY=direct_diff`.

The strategy default is `source_edits`, but generation stays off: defaults remain
`PATCH_GENERATION_PROVIDER=unavailable`, `PATCH_LOCAL_MODEL_ENABLED=false`, and
`PATCH_PROPOSALS_ENABLED=false`. No normal-service configuration was changed. Source edits
are converted into the pre-existing proposal `Candidate` and worker result contracts; no
database model or migration changed. The frontend files were not modified in P8.

Network-denied focused selection: **284 passed, 0 failed, 0 skipped, 3 deselected**. The
deselected PostgreSQL-specific tests were not run. Pytest emitted one warning because the
project's `cache_dir` option is unknown to the installed pytest configuration. Ruff passed
for the touched Python modules and tests. `git diff --check` passed. No PostgreSQL, Docker,
frontend, migration, normal service, or real-source test was run.

### One actual local synthetic inference

Exactly **one** request was sent to pinned local model `qwen2.5-coder:7b`, digest
`dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`, through the RepoPilot
Ollama adapter. Runtime Ollama 0.40.16 was signature-verified; model blobs and manifest
were checked against retained artifact records. The private daemon bound only to
`127.0.0.1:11434`, with cloud disabled, HTTP proxies disabled, redirects disabled, and a
macOS sandbox canary that allowed loopback while denying a non-loopback address. This is
bounded local-process evidence, not a production-grade execution sandbox.

The original synthetic file `src/arithmetic.py` was 49 bytes, SHA-256
`9445c47952abb8a7fc5d4a905d55b5be05771df1d69362ec597f9a50f7ede40d`, with complete-file
coverage verified by the synthetic fixture record. The request also contained the synthetic
addition issue and evidence reference E1. The exact pre-transmission JSON was 2,305 bytes,
SHA-256 `e8ebd29f3436bc65b14135b7993a8788a167e6d48bc4a9a40f900d30a1ab3a22`. The complete
actual response was retained unchanged (900 bytes; SHA-256
`729667e013ecdf6a1aec75b9eb7c9319f0cbe6d9a142411ba95605a5c439b052`). Owner-only records:
`/Users/roshan/Library/Application Support/RepoPilot/toolchains/ollama-p71/p8-20261115T060900Z-fe2ea1f6`.

The model returned one source edit replacing `    return a - b` with `    return a + b`
in the authorized file, citing E1. RepoPilot checked the source and evidence identities,
generated the deterministic one-line diff, and the existing static validator accepted it.
The accepted synthetic diff SHA-256 is
`8d74d6e35955c7e3c7068fc709b09b4d59b2b4efcd6f17076d9b032e159150e7`. Inference took 8.792
seconds; Ollama reported 306 prompt and 142 generated tokens. Peak sampled process-tree RSS
was 4,737,597,440 bytes (about 4.41 GiB); maximum observed swap was zero. RSS was sampled,
not a hard limit, and may not account for all GPU/unified-memory use. Memory pressure rose
after inference; no swapping or runtime instability was observed.

The private daemon exited successfully and its loopback listener and owned child processes
were confirmed absent. No patch was applied, executed, or tested. No GitHub source, issue,
database, hosted model, or normal service was contacted. Earlier abstentions remain
unexplained; this success establishes the new structured-edit path for this synthetic
example, not a general behavioral cause.

### Remaining gates

No PostgreSQL regression or migration was run in P8, and no claim is made about PostgreSQL
compatibility from SQLite-backed tests. Migration 0017 still requires reviewed disposable
PostgreSQL verification; the normal database was untouched. The sandboxed patch-test
executor remains blocked, so execution outcomes remain `VALIDATION_UNAVAILABLE`. Production
use still requires security review of model data handling, robust file-completeness
provenance, resource enforcement, service deployment, PostgreSQL verification, and explicit
approval to enable provider/proposal flags. Real repositories and generated-code execution
remain outside this verification.

## P9 — Trusted synthetic execution

The existing P4 registry binds two synthetic fixtures to repository
`repopilot-fixtures/patch-p4`, its fixed synthetic commit and snapshot, exact source and
patch hashes, and an immutable test script. The P8 candidate is a different fixture:
`src/arithmetic.py` with the accepted diff SHA-256
`8d74d6e35955c7e3c7068fc709b09b4d59b2b4efcd6f17076d9b032e159150e7`. Its private original
diff was rehashed and confirmed to be 133 bytes, with owner-only file and directory modes.
The P4 allowlist does not implicitly authorize this different source or diff.

Inert macOS `sandbox-exec` canaries denied a network socket connection, `os.fork`,
`os.posix_spawn`, and reading canonical `/private/etc/hosts` with `EPERM`. A first canary
denying literal `/etc/hosts` still allowed the read because the path resolves elsewhere;
the canonical path was then tested. These canaries used simple test profiles and do not
verify an adapter's complete policy. The managed tool sandbox rejected a nested
`sandbox-exec` call (exit 71); explicitly permitted tool execution was needed for canaries.
The native facility is macOS-specific and is not claimed to isolate hostile repository
code. The Docker adapter and its failed isolation gate remain unchanged.

The final restricted filesystem allowlist prevented the installed system Python from
starting (exit 134), including with `mach-lookup` denial removed. A broader denylist
started Python and denied network, spawn and a canonical host-file canary, but permits
other filesystem reads and does not establish that application secrets are inaccessible.
The exact disposable-workspace policy was not verified. Therefore no native executor was
enabled, no baseline or patched fixture ran, and no before/after result was produced. The
macOS canaries are not a sandbox for external code. No Docker containers, PostgreSQL,
normal services, or frontend files were touched.

`native_specs.py` provides a separate immutable P8 fixture registry and strict native
result validator for future work; it is not wired to the worker and launches nothing. Its
nine tests use synthetic or fabricated reports and do not prove execution. The combined
offline selection reported **123 passed, 0 failed, 0 skipped, 5 deselected**, with one
pytest `cache_dir` configuration warning. Deselected cases include actual Docker and
PostgreSQL paths. SQLite-based application contract tests do not establish PostgreSQL
locking or persistence. Ruff and `git diff --check` passed. P9 actual fixture executions:
**zero**. The normal Docker adapter and its fail-closed checks remain unchanged.

Future verification requires a reviewed native runtime and effective filesystem policy
that allow the fixed interpreter to start while denying secrets, network and child
creation; then run preflight on the exact policy, enforce or monitor resource limits,
validate cleanup, and integrate a separately validated native report with the worker.
Real-repository execution additionally requires a separately reviewed isolation boundary
and explicit authorization. PostgreSQL persistence and production activation remain
unverified.

## P9.1 — VM execution prerequisites

Read-only inventory found macOS 27.2.1, Apple M6 arm64, 16 GiB physical memory and roughly
23 GiB free disk space. Apple's Virtualization framework and Swift 6.4.2 are installed;
hardware hypervisor support was reported by the inventory. No `container`, Lima, QEMU,
Tart or Multipass launcher was found on PATH. No verified ARM64 guest image, kernel or
initramfs was found in the repository, RepoPilot's private toolchain directory, or the
bounded `/Users/Shared` inspection. These searches do not prove that no image exists
elsewhere. A read-only Swift query reported `VZVirtualMachine.isSupported=false` in the
managed tool environment; sandbox and entitlement effects were not isolated, so that is
not a host-wide availability claim.

No guest was started. Guest network, mounts, resource limits, serial channel, cleanup and
host credential isolation were therefore not empirically verified. No baseline or patched
fixture ran and no before/after comparison was produced. The intended trusted-fixture
policy calls for no host shares, credentials, network devices or host sockets, private
disposable storage, at most 2 GiB RAM, bounded CPU, time and output, and request-bound,
size-limited fixture and result transfer. Effective configuration inspection and guest
canaries are required; a requested configuration alone is insufficient.

The current non-executing VM contract cannot start or attest a VM. It requires an
independently provisioned, hash-verified ARM64 guest and a reviewed launcher with the
necessary Apple virtualization entitlement. Provisioning downloads or installation were
outside P9.1 authorization. The existing Docker and macOS isolation gates, worker behavior,
normal services, frontend and normal database were unchanged. PostgreSQL persistence,
real-repository execution and production activation remain unverified.

The VM contract pins the existing two synthetic fixture identities, constructs bounded
nonce-bound input containing the verified baseline, patched bytes and fixed test, and
checks size, duplicate JSON keys, nonce and request digest on an untrusted response.
This parser returns untrusted statuses only: it cannot attest a guest or create a
completed proposal result. Requested policy rejects nonempty networks, host shares and
sockets and fixes two CPUs, 2 GiB RAM, a ten-second timeout and 4 KiB output. None of
these requested controls has been enforced in a guest. No VM driver, guest image,
preflight, worker integration or resource cleanup implementation is present.

The focused offline selection reported **138 passed, 0 failed, 0 skipped, 5 deselected**
and one pytest `cache_dir` warning. This includes 15 VM contract cases and 9 native
registry cases; tests exercise locally prepared data and fabricated responses, not a VM.
The remaining selection exercises existing patch and authorization contracts, including
SQLite-backed cases. Actual Docker execution and PostgreSQL cases were deselected. Ruff
and `git diff --check` passed. Actual guest tests executed: **zero**. No temporary VM
resources were created, so no VM cleanup was required.

## P9 final — trusted host arithmetic demonstration

Under explicit narrow authorization, `evaluation/trusted_host_arithmetic.py` ran only the
fixed synthetic arithmetic source and `assert add(2, 3) == 5` in fresh temporary workspaces.
This is direct host execution, not a sandbox or an application worker provider. The runner
verifies exact bytes and hashes, uses the retained P8 patch, validates the diff, stages a
separate patched copy, and invokes the existing Python interpreter with `-I -S -B`, a
minimal environment, no shell, bounded output and a ten-second timeout. It verifies
workspace contents and cleanup. It does not accept real repositories or model commands.

Four actual child processes ran. The original source produced assertion failure, exit 1,
in 24 ms; the P8 patched source passed, exit 0, in 12 ms. Existing `compare` returned
`BASELINE_FAILED_PATCH_PASSED`. A separate unchanged-good control ran the exact same
assertion twice, passed with exit 0 in 11 and 10 ms, and returned `BOTH_PASSED`; that
control does not establish a repair. Both workspace pairs were removed. The test source
had no imports or file, process or network operations.

Original SHA-256: `9445c47952abb8a7fc5d4a905d55b5be05771df1d69362ec597f9a50f7ede40d`.
Patched SHA-256: `b414e3e8a1cc84d091471727544c353f60db59fc2bea10ee562ece77410915be`.
P8 diff SHA-256: `8d74d6e35955c7e3c7068fc709b09b4d59b2b4efcd6f17076d9b032e159150e7`.
Assertion SHA-256: `a6494aeead1e3538048fb31199d96215cf5d03ec0dd9a6462973f73d2c81aaff`.
The sanitized, owner-only execution record is retained at
`/Users/roshan/Library/Application Support/RepoPilot/toolchains/p9-final-39f65ce2a574/results.json`.

The genuine result has `sandbox_used=false`. The existing comparison and JSON serialization
represent it, but the application `verify_saved` completed-result path requires the Docker
sandbox-specific report. A test with this actual report confirmed rejection and a proposal
API 409. The unchanged frontend likewise requires `sandbox_used=true` for completed test
results. Consequently existing production service and frontend contracts do not accept this
host report; the full P9 final acceptance condition is incomplete. The runner is not wired
to application requests and does not weaken those checks.

Selected offline regression: **149 passed, 0 failed, 0 skipped, 6 deselected**, plus the
actual-report API contract test: **1 passed, 0 failed, 0 skipped**. The six deselections
include Docker and PostgreSQL cases and the separately run actual-report test. Both runs
issued one pytest `cache_dir` warning. Ruff and `git diff --check` passed. These tests
did not rerun fixture code. No PostgreSQL, Docker, model inference, real source, service
restart, application flag change, normal database or frontend modification occurred.
Host settings do not enforce filesystem or network isolation. Real repositories require a
separately reviewed execution boundary, authorization, and PostgreSQL verification.

## P10 — application integration and source provenance (2026-11-15)

### Changes

P10 preserves the existing dirty working tree and adds forward source provenance. New
complete-file metadata is created only by `collect_source` after the source tree size equals
the fetched raw blob size, UTF-8 decoding succeeds without normalization, and SHA-256 is
computed over those bytes. `publish_snapshot` reconstructs exact bytes from chunks and
rejects a claimed complete-file record if metadata, byte length or digest disagrees. This
preflight occurs before the old published snapshot is modified. Patch context checks the
persisted identity again before exposing a `PinnedFileIdentity`. Legacy indexed files remain
`UNKNOWN_COVERAGE`.

Forward migration `0018_source_provenance.py` adds nullable length/encoding/normalization
and a non-null coverage field with server default `UNKNOWN_COVERAGE`; no historical file is
upgraded based on chunks. `alembic heads` reports `0018` as head. The existing legacy
migration test applied the chain through `0018` to a temporary SQLite database and passed;
this does not verify PostgreSQL behavior or schema drift.

### Backend and API verification

Focused command covered source collection and persistence, source coverage, structured
edits, local provider contracts, static diff validation, proposal lifecycle, authenticated
API behavior, investigation evidence/jobs, tenant/auth checks and trusted-demo/report
contracts plus the SQLite legacy migration test and current migration-head guard. Result:
**295 passed, 0 failed, 5 skipped, 0 deselected**. Four skips require PostgreSQL row
locks/full-text search/locking; one requires disposable PostgreSQL. Application DB fixtures
used in-memory SQLite; this is not evidence for PostgreSQL locking, migrations, constraints,
transactions or concurrency. The retained P9 host report was read and validated by its
contract test; no fixture ran again.

A broader backend run, excluding `test_trusted_host_arithmetic.py` to avoid repeating the
P9 execution, reported **1,171 passed, 20 failed, 64 skipped, 3 errors** before the final
evaluation-harness revision allowlist fix. Failures were in optional multilingual parser
fixtures, the synthetic supervised-Go parser, a vector test lacking NumPy, and the evaluation
harness's stale `0017` revision allowlist (fixed afterward and covered by the focused
migration-head guard). Three publication-identity setup errors also require the optional
parser runtime. This broad result is not green; parser/vector dependencies were not installed
during P10, and the full suite was not rerun after the final harness-only fix.

Ruff passed on the changed Python implementation/test files. `git diff --check` passed.
The source migration graph has a single head at `0018`.

### Frontend verification

The previously verified private Node runtime was used: Node `24.18.0`, npm `11.16.0`,
within the declared Node range. Production build passed. TypeScript passed, ESLint passed,
and the frontend suite reported **94 passed, 0 failed, 0 skipped**. No frontend source was
changed for P10. A live browser run against the application was not performed, and no web,
API, worker, PostgreSQL, Redis or Docker service was restarted.

### PostgreSQL gate and service safety

The Docker client could not reach its configured Docker Desktop daemon; the selected socket
was absent. Read-only inspection also found no local `postgres`, `initdb`, `pg_ctl` or `psql`
binary. Therefore no disposable PostgreSQL instance/container could be safely created or
verified. Existing normal Compose container identities could not be enumerated while the
daemon was unavailable. No migration was applied, and no normal database or service was
connected to or changed. P10 PostgreSQL tests, migration 0018 upgrade, schema drift, row-lock
behavior, outbox transactionality and concurrency remain blocked.

### Product/security status

The authenticated investigation-to-proposal path and worker contracts are covered by
synthetic/offline tests with a deterministic or unavailable provider; P10 made no model
call. Proposal and local-model provider defaults remain disabled, multilingual flags remain
disabled, and production test completion still rejects any result with `sandbox_used=false`.
The P9 trusted host arithmetic record remains separate and is not a production validation.
Actual repository execution remains disabled pending the separate Linux KVM/Firecracker
architecture described in [patch validation](patch-validation.md#p10-execution-architecture-decision)
and its provisioning/security review.

P10 verdict: **application integration partially verified; PostgreSQL and production
execution gates remain open**. The immediate next operational action is to restore an
already approved disposable PostgreSQL runtime, then run migration 0018, schema-drift and
focused transaction/worker tests. Do not enable production patch proposals or execution
based on this report.

## P11 — disposable PostgreSQL integration (2026-11-15)

P11 supersedes the P10 PostgreSQL-blocked status for disposable integration coverage. A
private PostgreSQL 16.16 ARM64 runtime and pgvector 0.8.7 were provisioned without Docker,
sudo, service registration, or an automatic cluster. The server ran unprivileged against a
private P11 data directory and Unix socket, with TCP bound to numeric loopback and SCRAM
required. Passwordless TCP was rejected. All migration and test targets were checked against
the dedicated synthetic database marker; no normal database was accessed. See the concise
[P11 record](p11-postgresql-verification.md) for artifact identities and limitations.

The full chain reached Alembic `0018 (head)` on an empty disposable database; a fresh
`alembic check` showed no drift. The legacy migration path through 0018, schema-local
migration bookkeeping, source provenance schema, patch persistence and PostgreSQL worker
contracts passed. Final focused migration/drift/proposal selection: **31 passed**. Additional
actual PostgreSQL selections: pipeline **309 passed**, synthetic capture **50 passed**,
token counting **81 passed**, provider-count integration **54 passed**. The broad PostgreSQL
selection reported **1,200 passed, 1 failed, 6 skipped, 2 deselected**. Its one failure is
the vector foundation case requiring optional NumPy, unavailable in the verified offline
wheel cache; it was not skipped or hidden. A separate broad offline/SQLite selection had
**1,203 passed, 1 failed, 53 skipped, 2 deselected**, with the same NumPy limitation. These
selections are distinct and their counts are not additive.

P11 corrected UTC normalization for aware datetimes used in token-count binding hashes
and isolated Alembic version tables for migration tests. Ruff, offline lock consistency and
`git diff --check` passed. P11 executed no repository source, generated patch or model
inference. It did not rerun P8/P9 demonstrations. PostgreSQL-backed synthetic application
integration is verified; the product is not production ready. Real-repository execution,
live provider activation, production migration/release approval and the optional NumPy vector
check remain outstanding. The frontend and normal services were preserved.

## P12 — NumPy regression and backend completion (2026-11-16)

### NumPy root cause and correction

`test_coderank_cls_pooling_and_documented_graph_signature` failed with
`ModuleNotFoundError: numpy`. NumPy was not undeclared or incompatible: `pyproject.toml`
already lists it in the optional `local-embeddings` extra (`numpy>=2.3,<3`), and `uv.lock`
pins the compatible Python 3.14 ARM64 wheel to **2.5.4**. The P11 test venv contained only
the base/dev wheel set, not the optional inference extra; this unit test imported NumPy
directly while adjacent ONNX-runtime tests correctly skip when their optional runtimes are
absent.

P12 downloaded only the locked `numpy-2.5.4-cp314-cp314-macosx_14_0_arm64.whl` from the
configured Python package registry: **5,455,617 bytes**, SHA-256
`956555e0603a4d38019ae6925711cb9dc43195c076a928accf7ea5d50bddfe53`, matching `uv.lock`.
It was installed in the private disposable P12 Python 3.14.10 venv; `import numpy` reported
2.5.4 and package checks found no dependency conflict. No project dependency declaration
or lock pin changed. Vector-foundation tests on PostgreSQL: **13 passed, 2 skipped**; both
skips require the uninstalled optional ONNX Runtime/tokenizers stack.

### PostgreSQL and regression results

P12 created a new private PostgreSQL 16.16 cluster and a unique synthetic database, using
the retained P11 runtime and pgvector 0.8.7. The server was unprivileged, SCRAM-only for
TCP, bound to `127.0.0.1` and a private Unix socket; an unauthenticated TCP attempt failed.
The P12 target marker, database, role, port and data directory were checked before
migrations/tests. Existing test harnesses enforce different database/role name patterns, so
the same P12 database was renamed between the `5b2b`/`repopilot_fixture`, `5b1`/
`capture_fixture`, and fixed synthetic-capture identities. These were labels for one
disposable database in one cluster, not additional databases. No normal application
database was connected.

The empty database upgraded through Alembic **0018 (head)** and `alembic check` reported no
new upgrade operations. The identity-guarded legacy upgrade and schema-drift selection
reported **3 passed**; PostgreSQL synthetic capture reported **50 passed**. The final broad
PostgreSQL backend selection reported **1,201 passed, 0 failed, 0 errors, 5 skipped,
3 deselected**. It included auth/tenant, source provenance, indexing/retrieval, vector,
investigation, patch provider/edit/diff validation, proposal, outbox/worker and API tests.
The two ONNX/tokenizer integration cases skipped because those optional runtimes were not
installed; two supervised-parser broker cases skipped because the reviewed disposable
parser broker is not provisioned; one trusted-host-report presentation case skipped because
the prior P9 report was deliberately not loaded into this suite. The three deselections were
the two parameterized actual-fixture execution cases and the sandbox preflight case. The
separately completed P9 host fixture was not rerun.

An initial broad attempt used the migration harness's `5b1_checks` / `capture_fixture`
identity. Existing fake-provider PostgreSQL tests explicitly require the separate
`5b2b` / `repopilot_fixture` identity and failed closed with `approval_invalid`; the broad
run was repeated against that required disposable identity and completed with the passing
counts above. Dedicated migration/drift and capture suites then ran under their respective
marker-checked database identities on the same isolated P12 cluster. No test failures were
converted into skips.

The disposable cluster/data/socket/credentials were removed after verification. The
verified PostgreSQL runtime, private P12 venv and hash-verified NumPy wheel/manifest were
retained. `uv lock --check --offline`, Ruff, `uv pip check` and `git diff --check` passed. P12
made **zero model calls and zero source executions**. No frontend files or normal services
were modified. Production execution remains disabled; the Firecracker host and independent
security review are still required. See [P12 execution-host specification](p12-execution-host-prerequisite.md).


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

### P18 — proposal-only product verification

A disposable PostgreSQL/Redis/Celery-backed application, with a deterministic synthetic
provider and synthetic GitHub responses, generated a statically validated proposal. The
authenticated API exported the exact 133 UTF-8 bytes with SHA-256
`8d74d6e35955c7e3c7068fc709b09b4d59b2b4efcd6f17076d9b032e159150e7`; an
`approved_for_review` decision persisted and the same patch remained exportable. Live
requests rejected anonymous and cross-tenant access, wrong digest, source and snapshot
tampering, unknown full-file identity, an altered stored patch digest, unvalidated and
rejected proposals, invalid review input, missing proposals and invalid sessions. These
checks do not establish new inference or real GitHub behavior.

The final in-process backend selection passed 309 tests, with 3 skipped and no failures;
it included 15 export tests. The frontend suite passed 99 tests, with no failures or skips.
TypeScript, ESLint, the Node 24 production build, Ruff, offline lock verification and
`git diff --check` passed. The private frontend build warned about tracing symlinked
dependencies outside the copy; no packages were downloaded. The same focused contracts ran against the disposable PostgreSQL instance: 259 passed
in the main selection and 15 export tests passed separately, with no failures or skips.
WebKit rendered the live proposal and an intercepted browser download produced a Blob
with the canonical SHA-256; the OS save dialog and OS clipboard were not exercised. The
clipboard gesture and exact-byte handling were covered by a unit test. The three in-process
skips required PostgreSQL row locking or full-text search, and were covered in the
PostgreSQL selection. Pytest warned because its cache plugin was disabled.

Export requires current verified complete-file identity and the digest-bound canonical
diff. Legacy proposals can be inspected, but require a static recheck if the patch digest is
missing and verified reindexing if complete source identity is unavailable. Approval is
only for further human review; patch application, execution and testing remain manual.
No new inference or generated source execution occurred, no production flags or normal
services were changed, and production sandbox enforcement remains intact. See
[P18 proposal-only product](p18-proposal-only-product.md).

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

A disposable application investigation bound the verified upstream issue to the
pinned fork and persisted job-scoped partial-snapshot evidence in PostgreSQL. A
private mock-transport capture was prepared with no inference. Scoped patch and report
generation are fail-closed: durable exact-hash single-use approval and restoration of
the investigation identities remain unverified. The separate migration, regression
and real-data boundaries are recorded in [P19.1](p19-1-upstream-issue-and-partial-snapshot.md).

## P19.2 — durable approval work

The P19.2 internal ledger, guarded transport and checkpoint validation/restoration helper
were added without enabling scoped model calls. They are not an approval-ready invocation
path: shared authority binding, authenticated human approval, real worker integration,
independent daemon/egress checks and end-to-end restoration/replay verification remain
open. The prior request is unapproved; no inference or source execution occurred. See
[P19.2 durable inference approval](p19-2-durable-inference-approval.md).


### Commercial PR review development

See [commercial-mvp-development.md](commercial-mvp-development.md) for the limited
deterministic review scope, source identity checks, synthetic rule evaluation and release
gates. The reviewer is disabled by default. In this run the focused backend selection
passed 369 tests with one PostgreSQL-only row-lock test skipped; frontend unit/contract
tests passed 114. These are not evidence of AI review quality or production readiness.


### Public Python PR follow-up

The read-only analyzer verified four Python files of encode/httpx#3690 at pinned base and
head commits; its single narrow rule found nothing. A separate disposable PostgreSQL
application attempt failed after GitHub returned anonymous rate-limit responses. No live
end-to-end success is claimed. Per-client immutable-tree caching was added; 61 focused
source/PR tests passed. Details are in [commercial-mvp-development.md](commercial-mvp-development.md).


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

An opt-in installation-token path and migration 0021 rate-limit scheduling were
verified with mocked GitHub, disposable PostgreSQL and real Redis/Celery. A
fixture-backed desktop browser regression passed. Live GitHub installation access,
fork-head review, TypeScript safety and independent quality labels remain open. A
separate inference-evaluation harness test has a conflicting pre-existing 0020
allowlist expectation; it was not suppressed. Exact counts and limitations are in
[commercial-beta-foundation.md](commercial-beta-foundation.md).


## Commercial beta gate-closure follow-up

The synthetic evaluation harness now tests its reviewed 0020 schema rather than
assuming 0021 is allowed. PR workers reauthorize before logical GitHub source reads.
Disposable PostgreSQL/Redis/Celery and synthetic WebKit regressions passed; live
installation access and other gates remain open. Exact results and limitations:
[commercial-beta-gate-closure.md](commercial-beta-gate-closure.md).


## Commercial alpha follow-up

Migration 0022 and a synthetic public-fork review were verified with disposable
PostgreSQL, Redis/Celery and WebKit. No live GitHub installation, TypeScript
scanner or independent accuracy result is claimed. Details and exact counts are in
[commercial-alpha-product-milestone.md](commercial-alpha-product-milestone.md).


## TypeScript and real-fork follow-up

An opt-in macOS TypeScript review passed synthetic parser, database, broker and
desktop WebKit checks. The requested public fork metadata was retrieved read-only,
but no authenticated application review was performed. Exact results and safety
limits: [commercial-alpha-typescript-and-live-fork.md](commercial-alpha-typescript-and-live-fork.md).


## First developer pilot follow-up

[MOCKED-GITHUB] Public PR authorization now checks current read-only installation
permissions and GitHub clients ignore inherited proxy settings. Local negative tests
passed; no live installation was configured.

[REAL-BROWSER] A synthetic TypeScript review and feedback survived refresh, and
simulated revocation cleared displayed evidence. Exact evidence classes, counts,
remaining risks and setup guidance are in
[commercial-first-developer-pilot.md](commercial-first-developer-pilot.md).
