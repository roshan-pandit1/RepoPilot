# RepoPilot final project status

**REPOPILOT — FINAL BROWSER ACCEPTANCE INCOMPLETE.**

**Final Stage 3 is in progress.** On 2026-11-05 the isolated stack was brought back online,
the `0014` database and current partial snapshot were rechecked, and the user signed in.
The user authorized one new investigation and one mock report for the current snapshot. Two
new completed investigations were observed, despite the one-investigation limit; the first is
`213efc43-176c-478d-ab46-84ec187060f8` and the second is
`d4a174c6-e74e-4996-9d67-1b8194df1fc1`. One new mock report
`55caaefa-0264-42bd-ba76-95fd2c3ca8fa` was generated for the first job, with its citation
validated. CIE output, GitHub citation navigation, history reopening and mobile browser
acceptance remain pending. The two earlier superseded investigations remain fail-closed.
User-provided [history](screenshots/stage3-investigation-history.png),
[completed evidence](screenshots/stage3-completed-evidence.png) and
[mock report](screenshots/stage3-mock-report.png) screenshots record the demonstration.
See [verification](verification.md).

**REPOPILOT STAGE 2 — VERIFIED LOCALLY.** The authorized `repopilot-local` database is at
`0014`; API/web are healthy and the worker and dispatcher are running with the rebuilt image.
No legacy provenance or evidence manifests were backfilled. Stage 3 separately authorized
the current demonstration, which remains incomplete. See [verification](verification.md).

Stage 1 backup and isolated restore verification passed. Stage 2 subsequently rebuilt the
images, migrated the isolated database and restarted the application services. Subsequent
Stage 3 session and investigation writes are recorded above.

**Final browser acceptance remains blocked.** A later index superseded the existing jobs'
partial snapshot. Revision `0014` implements durable publication provenance and evidence
manifests for future investigations and is now applied to the isolated application database,
but it does not backfill or unlock the existing jobs. The current snapshot predates the
migration and lacks a publication record. See [the assessment](historical-snapshot-assessment.md).

**REPOPILOT — PLACEMENT-READY MVP IMPLEMENTATION COMPLETE.** The code and automated local
checks described below have passed. This is an implementation verdict, not a claim that the
latest dashboard has passed browser acceptance or that the application is ready for public
deployment. The isolated demo database is at the required revision.
The later opt-in CIE-v1 enhancement is **not yet verified**. Its disposable PostgreSQL
regressions passed, but browser acceptance remains outstanding; see [its record](code-intelligence-engine.md).

## Component assessment

| Component | Classification | Evidence or remaining work |
| --- | --- | --- |
| Signed webhook ingestion, tenant authorization and durable processing | Verified | Automated checks on isolated PostgreSQL, including authorization and retry regressions; historical local webhook smoke evidence is in [verification](verification.md). |
| Commit-pinned indexing, lexical evidence and citation checks | Verified | Fresh pinned replay `6f4f95ac2ccd1965` checked 524 baseline/candidate citations; `terms-v2` Recall@10 was 0.7188 on 16 scored cases. Labels are incomplete and selection used the same set. |
| Deterministic mock report and server citation validation | Verified | Disposable workflow and adversarial checks; output is **MOCK REPORT — DEMONSTRATION ONLY**, not verified AI diagnosis. |
| Investigation history, reopening, evidence UI and report presentation | Implemented but awaiting manual verification | Automated frontend and backend checks passed. The [5C2 browser checklist](sprint-5c2-dashboard.md#read-only-browser-acceptance-on-the-mac) remains open. |
| CIE-v1 rule-based source observations | Implemented but awaiting manual verification | Disposable PostgreSQL tests and offline replay passed; browser acceptance remains outstanding. `terms-v2` remains the production order. |
| Local configuration and Compose definition | Implemented but awaiting browser verification | On 2026-11-04 `repopilot-local` was migrated to `0014`; the approved repository, issue and published snapshot remain, and the rebuilt API/web are healthy. The default database remains empty and incompatible. |
| PostgreSQL backup/restore tool path | Verified | An isolated synthetic PostgreSQL 16/pgvector custom-format dump was restored to a separate empty database; row count and vector values matched. This is not an application-backup restore. |
| Actual application-backup recovery | Partially verified | The Stage 1 application backup was restored to an isolated database with matching metadata; roles, grants, encryption keys and a full application recovery remain unverified. See [verification](verification.md). |
| Public deployment, monitoring, backup policy and recovery objectives | Deferred | No deployment is authorized or claimed; public production readiness is not established. |
| Real-model generation and paid token counting | Deferred | Adapter foundation exists but real execution is disabled by default. No paid request or diagnosis-quality evaluation was performed. |
| Organization enrollment, private repositories, GitHub writes, production AI diagnosis | Not implemented | Current enrollment is limited to verified personal-account public repositories; these features are outside the local MVP. |

## Final automated checks

- CIE follow-up: **606 PostgreSQL tests passed with no skips**, **33/33** adversarial cases,
  Ruff and Alembic `0013`/no drift in disposable run `b5b1c925a167ec16`; its fingerprint
  matches the current backend source. The fresh retrieval and offline CIE comparison are in
  [the CIE record](code-intelligence-engine.md#evaluation).
- Backend: **587 passed**, **33/33** adversarial fixture cases, Ruff and Alembic `0013` with
  no drift, on a freshly created disposable PostgreSQL database. The test runner excludes the
  separately gated committed-source test; the separately authorized 5C1 fixture was already
  evaluated. [Run log](../apps/api/evaluation/5c1-checks-44627f6c0aa305e1.log).
- Frontend: **58 passed**, TypeScript, ESLint and production build with Node 24.11.1 and the
  existing installed dependencies. Rendering tests do not establish browser fetch transitions.
- Compose configuration validation and mock settings without an OpenAI key passed.
- Synthetic dump/restore passed in retained container `repopilot-restore-drill-c1acd8ebf541f8b3`;
  its synthetic archive is in `/private/tmp`. No normal application database was changed.
- `git diff --check` passed. No paid model, external token count, live investigation, report or
  indexing job was run in this finalization pass.

To rerun on a Mac host, from the repository root, after making sure Docker and the locally
installed pgvector image are available:

```sh
bash apps/api/evaluation/run-5c1-checks.sh
git diff --check
cd apps/web
npm test
npm run typecheck
npm run lint
npm run build
```

The backend script creates and retains a separate empty database and container; it never
targets the normal application database. `TEST_DATABASE_URL` must never name a real database:
test fixtures drop tables. Frontend commands require Node 22–24 and installed dependencies;
`npm ci` can install the lockfile dependencies if needed.

## Final acceptance checklist

- [x] Pinned retrieval benchmark and commit-pinned citation verification recorded.
- [x] Disposable PostgreSQL, adversarial, frontend and build checks passed.
- [x] Mock-mode settings work without an OpenAI key; real execution remains disabled by default.
- [x] Synthetic isolated backup/restore drill completed.
- [x] Identify and read-only verify the compatible isolated `repopilot-local` database; the
      empty default database remains incompatible and must not be migrated implicitly.
- [ ] Complete the [consolidated browser acceptance](browser-acceptance.md), including the
      Stage 3 demonstration. Two investigations were created although only one was authorized;
      both completed with 20 evidence rows. The first has a validated mock report, and the
      user-provided screenshots show the history, evidence and report. CIE output for this job,
      citation navigation, reopening from history and mobile checks remain outstanding. The
      earlier legacy jobs remain inaccessible after their snapshot was superseded. See
      [browser acceptance](browser-acceptance.md).
- [ ] Independently restore an authorized application backup before relying on recovery.
- [ ] Obtain separate approval and complete deployment-specific security, operations and recovery
      review before any public deployment.

For a safe local demonstration, use existing authorized data and verify the stack is running
the reviewed code with a compatible database. Do not start Compose's migration service against
an existing database without separate authorization. The [demo guide](portfolio-guide.md)
uses existing investigations and reports and does not require paid AI.
