# Code Intelligence Engine v1 — design

**CODE INTELLIGENCE ENGINE v1 NOT YET VERIFIED.** CIE is opt-in, deterministic
analysis of a completed investigation's already-retrieved source evidence. It is not AI,
does not execute or import repository code, and does not establish a root cause.

The existing index stores line-addressed chunks rather than original files. For v1 the graph
is therefore built only from fingerprint-verified evidence chunks belonging to the same
authorized published snapshot, not from arbitrary paths mentioned in an issue. Parseable
chunks provide file/module and definition nodes, `DEFINES`, `MEMBER_OF`, `IMPORTS` and
conservatively resolved direct `CALLS` relationships. Syntax fragments, dynamic dispatch,
ambiguous names and imports that cannot be proven are not presented as resolved calls. A
missing relationship is not evidence that no relationship exists.

Issue signals use bounded text and strict traceback, path, exception and identifier patterns;
arbitrary prose is not an exact symbol. Historical jobs do not store issue text, so an opt-in
operation obtains current issue context using the injected GitHub client and must reject a
changed issue. Repository and session authorization, current snapshot publication, ownership,
commit and evidence fingerprints are rechecked using existing contracts. Findings may cite
only existing verified evidence. Source code and issue text remain untrusted data.

Candidate scoring starts from the existing `terms-v2` ordering and protects its first four
leaders. Direct matches and short graph relationships are recorded separately; deterministic
tie-breaking retains original rank. Candidate expansion cannot introduce uncited source. The
baseline remains production ranking until comparable evaluation supports a change. Explicit
traceback and symbol observations are hypotheses, with an abstention when no supported evidence
exists. `RULE-BASED ANALYSIS — POSSIBLE CAUSES, NOT VERIFIED` is separate from mock reports.

## Implementation and bounds

The authenticated read-only `GET /v1/repositories/{repository_id}/investigations/{job_id}/code-intelligence`
is invoked explicitly from the workspace. It first checks access and the completed job, fetches
fresh issue context through the injected GitHub client outside locks, and rejects a different
issue ID or update timestamp. It then fences session, installation, repository and snapshot
revocation using the existing read locks and verifies all persisted evidence fingerprints.
Known-sensitive chunks are withheld before analysis. Citation links are reconstructed from the
verified evidence; the frontend independently requires each finding citation to match displayed
evidence. This operation creates no job and does not change existing reports or ranking.

The in-memory graph is scoped by the authorized job's tenant, repository, snapshot and commit.
Each node contains an evidence chunk ID, path and inclusive line range; nodes describe file,
module, class, function and method, including async definitions. Edges record `DEFINES`,
`MEMBER_OF`, `IMPORTS_UNRESOLVED`, `IMPORTS_POTENTIAL`, `CALLS_STATIC`, `CALLS_AMBIGUOUS`
and `CALLS_UNKNOWN`. Static resolution is limited to names within a parsed chunk; potential
import links require an exact unique module-path match. These are syntactic observations,
not proof of runtime dispatch, import availability or reachability. Relative and dynamic
imports are not resolved. No file is loaded based on an issue path, and no repository code is
imported or executed.

Limits are 20 evidence chunks/files, 8,192 UTF-8 bytes per chunk, 65,536 bytes total,
500 graph nodes, 1,000 edges, 40 signals, one relationship hop and 10 findings. A per-API-process
semaphore permits one analysis at a time. The application analyzer runs in a spawned process;
the parent's two-second wait starts after `process.start()` returns and includes remaining child
bootstrap, scheduling and analysis. A 0.5-second soft budget is also checked between parsing
units. The `process.start()` call, cleanup, GitHub authorization and database work are outside
that wait. Bounds are not an OS memory
quota. Parsing is proportional to bounded source size plus graph walks; repeated AST walks can
be superlinear in the number of definitions, so the byte/node/edge caps matter.

Exact traceback frame/range, explicit path or identifier, named exception in a `raise` or
handler, and import-name alignment produce rule-based observations. A traceback outside all
evidence ranges abstains unless another independent signal matches. For example, an issue
mentioning `function process_sync` can produce a high-uncertainty finding for an existing
`process_sync` evidence chunk; an unrelated issue with no explicit match produces an
abstention. Every finding includes an existing citation, observed signals, a diagnostic check
and limitations. It does not claim to have reproduced a bug or found a fix.

The candidate reranker protects the first four existing results, scores bounded direct matches
and at most one point for one-hop potential/static relationships, and uses original rank and ID
for deterministic ties. The candidate order and contributions are returned for inspection only;
they are not written to evidence or substituted for `terms-v2`. No schema migration or new
service was added.

## Evaluation

On 2026-11-04, the read-only paired replay `6f4f95ac2ccd1965` used the already approved
fixture `68ed7b3fd6171439`, snapshot `95751038-f44e-4715-b4bd-932e446f457b`, the unchanged
dataset and commit `30705da4c044192cab4ac207e253ab8e8a1bd100`. Current `terms-v2` direct
retrieval measured Recall@1/3/5/10 **0.3750/0.5000/0.5625/0.7188**, MRR **0.5177** and
nDCG@10 **0.5469**; p50/p95 was **83.847/115.989 ms**, with **298/298** citations checked
against committed Git source. The same-run `terms-v1` baseline checked **226/226** citations.
[The comparison](../apps/api/evaluation/5c1-comparison-production-v2-6f4f95ac2ccd1965.md)
contains all cases. New jobs still pin `terms-v2`; CIE does not alter persisted order.

Offline CIE replay `b53ff5ae7a3a87d7` then consumed that new `terms-v2` artifact and pinned
Git blobs. Its retrieval metrics were unchanged, all candidate positions stayed the same,
and it produced findings for **4/19** cases with **15/19** abstentions. Analysis-only p50/p95
was **13.347/30.143 ms**, one bounded-process sample was **282.719 ms**, and one in-process
`tracemalloc` peak was **2,605,337 bytes**. The CIE step did not query PostgreSQL or measure
end-to-end latency, child-process RSS or diagnosis accuracy. See the
[machine-readable result](../apps/api/evaluation/cie-v1-offline-b53ff5ae7a3a87d7.json) and
[per-case comparison](../apps/api/evaluation/cie-v1-offline-b53ff5ae7a3a87d7.md). The source
and baseline hashes match the files used in this run. This synthetic, incomplete, in-sample
evaluation is not a held-out quality test.

Offline run `17a92df198280e40`, before the later child-error handling fix, applied CIE to the previously verified 5C1 `terms-v2` evidence
and read the same pinned local Git blobs. It used the unchanged dataset and recorded snapshot,
but **did not query PostgreSQL again**. Each citation path, commit and range was rechecked
against Git; the earlier run checked the database chunks against those blobs. The baseline's
direct-retrieval p50/p95 **82.396/124.066 ms** is inherited, not a new CIE retrieval timing.

| Metric | terms-v2 | Offline CIE candidate |
| --- | ---: | ---: |
| Recall@1 / @3 / @5 / @10 | 0.3750 / 0.5000 / 0.5625 / 0.7188 | 0.3750 / 0.5000 / 0.5625 / 0.7188 |
| MRR | 0.5177 | 0.5177 |
| nDCG@10 | 0.5469 | 0.5469 |

No candidate positions changed in this replay. Findings appeared in **4/19** cases; **15/19**
abstained. Analysis-only p50/p95 was **14.384/35.263 ms**. One sample including a spawned
process took **292.446 ms**; one in-process `tracemalloc` sample peaked at **2,604,961 bytes**
of traced Python allocations, excluding existing input and child-process RSS. These are small
single-run measurements, not end-to-end, load or memory-limit measurements. The benchmark is
synthetic, incompletely labeled, in-sample and not a root-cause accuracy evaluation. No
independent held-out set was added. Retain `terms-v2` as production order: CIE showed no
relevance gain and adds analysis work. The [machine-readable report](../apps/api/evaluation/cie-v1-offline-17a92df198280e40.json)
and [per-case comparison](../apps/api/evaluation/cie-v1-offline-17a92df198280e40.md) contain
the run, provenance and labeled ranks.

To reproduce the offline replay from the repository root:

```sh
cd apps/api
../../.venv/bin/python -m app.evaluation.code_intelligence_replay
```

For a new read-only production retrieval replay on the retained, previously approved fixture,
first run `bash apps/api/evaluation/run-5c1-baseline.sh paired 68ed7b3fd6171439` from the
repository root, then pass its actual newly generated `evaluation/5c1-production-v2-<run>.json`
path to `python -m app.evaluation.code_intelligence_replay --baseline ...` from `apps/api`.
That command needs the retained fixture; it does not create or reindex one. The CIE step still
uses saved evidence plus verified local Git blobs, rather than rereading database chunks.

## Verification and outstanding work

Host PostgreSQL run `9b4a749619a3f267` failed three CIE tests: **596 passed, 3 failed**.
The saved log's line 58 shows pipe EOF was converted to `AnalysisTimeout`, rather than the
deadline expiring. The runner had invoked `pytest.main()` from a shell heredoc. A reproduction
of that harness on macOS showed the spawned child attempting to reload the nonexistent
`apps/api/<stdin>` as its main module and exiting before analysis; direct `python -m pytest`
passed the same tests. The host runner suppresses captured child output, so the traceback was
established by the reproduction, not visible in the original log. The API correctly returned
503 when its child could not return a result.

The runner now invokes `app.evaluation.disposable_regression` as a guarded importable module,
preserving its PostgreSQL target checks, no-skip requirements and network fence. CIE still
uses the same `spawn` method and two-second wait. A child exception or premature exit is now
reported separately as `AnalysisProcessError`, without returning or logging exception details;
the route returns a safe 503 for both error and timeout. Cleanup closes pipes and reaps the
child, using termination and then kill if needed. The three failed tests passed four consecutive
times with the fenced module harness using SQLite. Focused CIE/evidence tests passed **48 with
one PostgreSQL-only skip**. A five-sample synthetic timing probe while the full suite was running
measured spawn-to-child-ready p50/max **35.892/39.092 ms** and analysis p50/max
**0.144/0.166 ms**; this is a small local sample, not a scheduling guarantee or proof of the
original host's timings.

The corrected host-style disposable PostgreSQL run `b5b1c925a167ec16` passed **606 tests**
with no skips, **33/33** adversarial fixture cases, Ruff and Alembic `0013` with no drift.
Its source fingerprints matched, and the script exited 0; see the
[retained log](../apps/api/evaluation/5c1-checks-b5b1c925a167ec16.log). Tests exercise normal
analysis, empty and invalid evidence, sensitive source, authorization and issue changes,
child exception, abrupt exit, no result, a synchronized blocked child, deadlines and repeated
child cleanup. No normal application database was migrated. The timeout and child cleanup
change did not alter AST ranking logic, but the earlier offline evaluation predates this change.

Focused tests cover non-execution, explicit signals, traceback ranges, ambiguity, dynamic and
circular imports, path traversal, limits, timeout, current-issue change, source tampering,
wrong commit, unpublished snapshot, revocation and unauthorized access. The fresh direct
retrieval and offline CIE replay above do not replace end-to-end CIE browser verification.
Browser acceptance for this feature and the
earlier 5C2 dashboard remains outstanding. No paid API, real model, external token count, new
live job, normal database migration or reindex was performed.

On the Mac host, start Docker Desktop and, from the repository root, run
`bash apps/api/evaluation/run-5c1-checks.sh` for the disposable PostgreSQL suite and its 33-case
adversarial fixture. It creates and retains a new disposable container and excludes the
separately approval-gated source-snapshot test; it never migrates the normal database. Review
the final log and exit status. Complete browser acceptance separately using existing data.

Use the [consolidated dashboard and CIE-v1 browser checklist](browser-acceptance.md) with
previously persisted jobs; it records missing prerequisites as blocked.
