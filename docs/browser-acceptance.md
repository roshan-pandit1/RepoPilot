# Read-only browser acceptance: investigation dashboard and CIE-v1

## Final Stage 3 — in progress

**REPOPILOT — FINAL BROWSER ACCEPTANCE INCOMPLETE.** The remaining browser checks and the
additional investigation recorded below have not been resolved.

The user authorized one new investigation and one deterministic mock report for
`roshan-pandit1/RepoPilot` issue #1, plus the necessary GitHub session. On 2026-11-05 Docker
Desktop was started after its daemon was unavailable; existing restart policies brought the
isolated application containers up. Read-only preflight confirmed database `repopilot`, revision
`0014`, current snapshot `b11f8c40-2d4b-4ab3-a4d4-d053249f8bc8` at commit
`1d26667b64527b41e67013bd00d326ab86ada8de`, 135 files, 1,482 chunks and one skipped file.
API/web responded with HTTP 200, the worker reported zero active/reserved/scheduled tasks,
queues were empty, and offline provider settings were verified. At preflight there were two
existing investigations and one report; they are legacy records and must not be repaired.

The user completed GitHub sign-in; a read-only query confirmed an active session belonging to
the repository tenant. Chrome automation is blocked by its Apple Events setting and macOS
accessibility permissions, so the user is operating the browser. Two new completed investigations
were observed despite the single-investigation limit: first
`213efc43-176c-478d-ab46-84ec187060f8`, then `d4a174c6-e74e-4996-9d67-1b8194df1fc1`.
Each has one attempt and 20 evidence rows on the approved snapshot. User screenshot evidence
shows the latter completed and displaying the partial-snapshot warning. The first job's evidence
manifest validated, its outbox was processed, and all 20 source ranges and file hashes matched
the pinned local Git commit. The first job was selected for the remaining checks. The extra job
is an acceptance discrepancy and must not be concealed.
The [user-provided history screenshot](screenshots/stage3-investigation-history.png) shows
the signed-in dashboard, issue #1 and both new jobs before the report was generated. A later
[completed investigation screenshot](screenshots/stage3-completed-evidence.png) shows the
first job, its 20 results, the pinned commit and the partial-snapshot warning. A
[mock report screenshot](screenshots/stage3-mock-report.png) shows the required demonstration
label and uncertainty. A read-only database check confirmed exactly one new report,
`55caaefa-0264-42bd-ba76-95fd2c3ca8fa`, report job
`8157b294-b30a-4700-90d2-70284d20526e`, attached to the first investigation. Its provider is
`mock` / `deterministic-v1`; the application revalidated its one citation against the 20
verified evidence items. The screenshot does not by itself establish reopening from history.
Stage 3 CIE output, actual GitHub citation navigation, history reopening and mobile acceptance
remain unverified. Do not submit another investigation or generate another report.

| Browser check | Evidence and status |
| --- | --- |
| GitHub sign-in, authorized repository and issue #1 | Shown in the history screenshot. |
| Completed investigation, 20 evidence results and partial warning | Shown for the first job in the evidence screenshot. |
| Deterministic mock report and warning | Shown; one new persisted report and its citation were independently validated. |
| CIE result or abstention for the first job | Pending; the rule-based panel is visible, but a result has not been shown. |
| Open a GitHub citation at the pinned commit and line range | Pending; stored source ranges and hashes matched the pinned local commit. |
| History filtering and reopening, refresh, keyboard and copy controls | Pending browser confirmation. |
| Approximately 390px mobile layout | Pending browser confirmation. |

The screenshots preserve the user's original browser capture, including browser chrome and tab
titles. Review them before sharing publicly; no cookies or credential values are shown.

The sections below record the earlier demonstration and must not be read as an instruction to
use or repair the superseded legacy jobs.

The current demo uses the current snapshot. The separately approved backup, isolated restore,
migration to `0014` and restart passed. Stage 3 approval covered one new investigation and one
mock report; no further investigations or reports are authorized. See the
[final execution plan](final-demo-execution-plan.md). The old demo jobs are not to be repaired
or used as substitutes for a new eligible job.

**Current blocker:** the old snapshot is no longer current and its jobs lack the original
durable publication and evidence-manifest records. The additive correction was applied at
`0014` but deliberately does not unlock these legacy jobs. See the
[assessment](historical-snapshot-assessment.md).
Do not create replacement jobs, reports or indexes to work around it.

## Previous authorized local demonstration — partial evidence

On 2026-11-04, the user authorized **one** new investigation and **one** deterministic
mock report for repository `1435878031`, issue #1, in `repopilot-local`, as well as the
necessary GitHub OAuth/session and processing writes. The isolated stack is already running
with healthy API and web containers and the CIE module and proxy present. The database is
was then at `0013` and its published snapshot matched the approved ID and commit. No browser action
was performed by the agent. User screenshots and a read-only database query show one
completed investigation `c96bdb12-ef45-4221-beec-4223f60063d3` for issue #1, with one
worker attempt and 20 persisted evidence rows on the approved snapshot. Later user screenshots
and a read-only query show a second completed investigation
`7fb9fb0b-f9ec-46d6-9d14-1311de6ffa68` with the same snapshot and 20 evidence rows. The
screenshots show GitHub connected, the issue, history, source rendering, the no-report state
and a clearly labeled mock report. Its persisted report ID is
`aedcc03e-1dc4-4656-af5e-032253cd6c94`, report-job ID
`34c6cb7f-2009-401d-b1b6-fc9102094b1a`, attached to the second investigation. At the latest
read-only check, there were two investigations and one report. Subsequent screenshots show
the second investigation reopened by its investigation ID and CIE returning a labeled
abstention: insufficient matching evidence, with source-budget, unparseable-chunk and
unsupported-identifier limitations. Actual GitHub citation navigation and mobile checks remain
outstanding.

The later screenshots also showed an index running. A subsequent read-only database check
found index job `34d8ea4f-0e45-4e03-a9f2-406bc7aa3d4b` completed with `partial` status,
and a new published snapshot `b11f8c40-2d4b-4ab3-a4d4-d053249f8bc8` at the same commit.
The original snapshot `5d24f965-fb26-431b-80b4-14275467c07d` is now unpublished. Existing
investigation/report read routes require the job's snapshot to be published, so further
reloads of the existing jobs are expected to be rejected. Reindexing was outside the demo
scope; no reindex was initiated by the assistant. Do not reindex or create more jobs as a
workaround. The CIE screenshot was captured before this state was checked.

1. Open `http://localhost:3000`, sign in to the account that can access the existing
   installation, choose the existing repository, and select issue #1. Stop if access fails;
   do not enroll, sync or reindex.
2. Both observed investigations have completed; **do not submit another**. Select **Refresh
   evidence and report** if needed to recheck access after the tab was inactive.
3. Confirm persisted evidence and the neutral missing-report state. Open a citation and
   verify its commit `1d26667b64527b41e67013bd00d326ab86ada8de` and inclusive line range.
4. Select **Analyze existing evidence**. Record the rule-based warning, findings or valid
   abstention, evidence links and limitations. An issue change can cause a conflict.
5. The single mock report has already been generated and its warning observed. **Do not
   generate another report.**
6. Refresh, reopen that job from history, and check desktop/mobile layout, focus and navigation.
   Capture redacted screenshots of status/history, evidence, CIE, mock report and mobile view.
   Do not expose credentials, cookies, callback URLs, private text or sensitive source.

Record each result and the investigation and report IDs only after observing them. Where the
UI does not show an ID, obtain it through a read-only database query rather than guessing.
The detailed checks below apply to the resulting persisted job; cases requiring additional or
historical jobs remain blocked unless suitable existing data is available. **Not yet passed.**

The prior authorization produced the records described above and does not authorize another
investigation or report. New demo writes require a separate approval. The checks below apply
after any separately authorized setup and remain read-only afterwards.

**Status: partially performed; not yet accepted.** This checklist covers the remaining Sprint 5C2 and CIE-v1
browser acceptance together. The default Compose application database inspected on 2026-11-04
has no public tables or Alembic revision and is not compatible with the current application.
Do not run `make dev` or migrations against it as part of this checklist. Use an already
running, compatible local stack with an authorized repository and previously persisted jobs;
if those prerequisites are unavailable, record the check as blocked. Finding or restoring an
appropriate database is a separate operator decision.
See [Stage 2 verification](verification.md) for the current `0014` isolated database and rebuilt
images; the older recovery assessment is historical.

After completing the one explicitly authorized investigation and report above, use existing
data only. Do **not** click **Investigate issue**, **Generate report**, enrollment, sync or
index controls again. CIE's **Analyze existing evidence**
action is a read-only analysis of a completed job, but it rechecks GitHub access and reads the
current issue. It needs GitHub connectivity and returns unavailable if the issue changed.

1. Open the dashboard as the authorized user. Confirm the repository loads and issue #1 is
   visible if it exists in that repository; do not fabricate it if absent.
2. Inspect history. Check available status filters and pagination, then reopen an existing
   completed investigation. Confirm the issue, job ID and status agree with history.
3. Inspect the existing evidence, including the expected 20 results if that job has 20. Check
   rank, path, symbol, line range, navigation and copy controls. Open a citation and confirm its
   GitHub URL identifies the pinned commit and exact inclusive lines.
4. Open an existing report and check **MOCK REPORT — DEMONSTRATION ONLY**, uncertainty,
   supporting evidence and limitations. Open a different existing job without a report and
   confirm its neutral empty state. If a historical mock-orchestration job is present, check
   its explanation that no snapshot or source evidence was produced.
5. On an existing completed evidence job, select **Analyze existing evidence**. Check
   **RULE-BASED ANALYSIS — POSSIBLE CAUSES, NOT VERIFIED**, its cited observations or explicit
   abstention, diagnostic checks and limitations. Confirm each citation matches existing
   evidence and the pinned commit. The analysis does not establish a root cause.
6. Refresh and navigate away and back. Where practical, switch jobs or hide the tab during
   analysis and confirm stale results do not reappear. Check error handling without changing
   live authorization or creating work.
7. At desktop, tablet and mobile widths, check keyboard focus, status announcements, long
   paths and horizontal code scrolling. Test clipboard controls with browser permission.

Record the date, environment, job types and pass/fail or blocked result for each applicable
step. Capture redacted screenshots of history, completed evidence, an existing mock report,
CIE findings or abstention, and mobile layout. Never include session cookies, credentials,
private issue text or sensitive source. A screenshot or a successful local check is not a
public deployment or real-model diagnosis claim.
