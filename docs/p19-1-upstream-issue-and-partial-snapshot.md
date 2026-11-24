# P19.1: Upstream issue and pinned partial snapshot

## Application contracts

A direct public parent issue can be associated with an authorized fork as the
investigation target. The association stores the parent repository identity, issue
identity, canonical URL, title, body SHA-256, update time, relationship and
verification time separately from the target repository. The application checks the
parent relationship and issue identity against GitHub; the supplied IDs and hash
narrow the accepted result and do not define the parent. The investigation worker
rechecks the origin before and after evidence retrieval. Same-repository jobs retain
their existing representation.

Migration `0019` introduces nullable origin identity and an origin association bound
by composite investigation, repository, tenant and issue keys. Active-job uniqueness
distinguishes origin repository IDs. Partial inventory records carry a canonical
manifest and digest and are linked to one investigation using tenant/repository-bound
foreign keys. Legacy snapshots remain `UNKNOWN_INVENTORY`. A partial inventory is
never the repository-wide published snapshot. Its scope and manifest are checked
against reconstructed file bytes and existing publication revocation before use.
Repository inventory completeness and file completeness are independent: the partial
inventory here contains two individually complete, hash-verified files.

The authenticated API exposes issue origin and inventory metadata, and the frontend
can present an upstream issue against the fork without treating the upstream issue
as fork-owned. Patch and report generation for an upstream or partial job are
currently fail-closed. That restriction is deliberate: a single-use exact-request
approval, transport enforcement and durable job/evidence re-establishment have not
yet been implemented. The existing static validators and production sandbox
requirements have not been relaxed.

## Daytona investigation

The disposable application investigation used the public direct-parent relationship
`roshan-pandit1/daytona` (GitHub ID `1179763383`) → `daytonaio/daytona` (GitHub ID
`753490180`) and [upstream issue 2421](https://github.com/daytonaio/daytona/issues/2421)
(stable issue ID `3423227753`). The target commit remained
`a5b13df553f214ce2849741b4914b24fad576e01`. Fresh anonymous GitHub relationship, issue
and tree metadata were used with synthetic application authentication and the previously
verified private file bytes. The actual application endpoint, investigation worker,
PostgreSQL retrieval and evidence persistence ran; no real-source provider task was
created. This was a disposable integration, not a normal production session.

The job was `b8e7bdaa-7226-43c7-9948-bd35bc392c30`; its scoped snapshot was
`361e5e01-7b24-40c0-a254-7091787c9dee`, manifest SHA-256
`9fec360ce4c57b6f00c67f452b2fead263ad3e40ede1ddd1bbe6a5c7e9cd140c`. Its included
files, both independently verified `COMPLETE_FILE`, were:

| Path | Bytes | Original SHA-256 |
| --- | ---: | --- |
| `libs/sdk-typescript/src/Snapshot.ts` | 11452 | `a0dc733aba6e704c4979b4ede50703b43e237fa239a0de14e4e9de176932ac59` |
| `libs/api-client/src/models/snapshot-dto.ts` | 2817 | `4bd91368df003087d64d1358bc747ff857e4606c1d306a62ae8304e2929347ab` |

Persisted evidence references were: `890b84c1-512b-4353-b9b5-a635905eb9dd`
(DTO lines 1–120); `a9145d8e-0aea-4869-933e-9567e82b2c69` (SDK lines 1–120);
`1577487b-1883-4350-bb58-31ad4ae53b77` (SDK 121–240);
`9a292725-2408-437b-adeb-dddd215cf413` (SDK 241–308); and
`e46713a6-3708-47b9-8c0e-9f9d5a468314` (DTO 121–152). RepoPilot used bounded
text-only chunks; no TypeScript parser-backed analysis is claimed. The issue body
SHA-256 was `5b64385923ec0a15aaaf0abe3e43a88f53f8120c464183f4125f2d4e787dbdb5`.

The issue reports that `createdAt` was a string on SDK 0.27.1. The pinned DTO declares
`createdAt` and `updatedAt` as `Date`, and `lastUsedAt` as `Date | null`; SDK list,
get and activate paths assert returned values as `Snapshot`. These observations do
not establish the lower-level deserializer, actual API response or runtime behavior,
and the reported package version is not established as identical to this commit.
The upstream fix PR was not used. No code was executed.

## Private captured request and blocking gate

The existing source-edit provider was run only against an injected mock HTTP transport
to capture the serialized request that would be sent to `/api/chat`. The 19,534-byte
request has SHA-256 `5aee04451c945003f14c474dacca4995b5e66c68157247172714702858f5ce02`.
The five model-facing snippets are `BOUNDED_EXCERPT`, padded around evidence and
containing 14,827 source bytes including overlap. The complete raw files are larger
than the distinct snippets; classification of an excerpt is not classification of
the entire inventory. The requested model was `qwen2.5-coder:7b`, digest
`dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`; the existing
Ollama client reported 0.40.16 and its local model manifest/blobs were checked offline.

The owner-only checkpoint is under
`~/Library/Application Support/RepoPilot/p19-evidence/p191-frozen`. Its request is
a mock-transport capture, not an approved or transmitted call. The database-backed
identities have not yet been proven restorable after removal of the disposable
database, and no durable, atomic single-use approval and byte-for-byte transport
enforcement exist. Therefore this hash is informative only, not an inference-ready
approval packet. Do not queue an upstream or partial generation job or infer before
those gates are implemented and verified and the user separately approves the exact
then-valid request.

## Verification and limits

The final expanded in-process selection passed 420 tests, with 9 PostgreSQL-only
skips and no failures. A separate report-worker security selection passed 83 tests,
with 5 PostgreSQL-only skips. The final isolated PostgreSQL 16.16/pgvector 0.8.7
selection passed 272 tests with no failures or skips, including 8 dedicated
identity/constraint tests. Fresh and 0018→0019 migration chains and schema drift checks
passed; the upgrade preserved a legacy same-repository job
and snapshot. Frontend checks passed 107 tests, TypeScript, ESLint and a Node 24
production build; the temporary build warned that 27 traced dependency files were
outside its symlinked root. These are distinct test runs, not additive counts.

No Ollama inference, hosted inference, generated or real source execution, GitHub
write, normal-service activation, or normal database migration occurred. Automated
real-repository patch execution is still blocked. Current status remains **specific
real-issue application gate blocked** pending safe approval consumption and durable
re-establishment.

## P19.1 files

- Migration and domain: `apps/api/alembic/versions/0019_upstream_partial_snapshots.py`,
  `apps/api/app/domain/models.py`, and `apps/api/app/evaluation/provider_harness.py`.
- Backend: `apps/api/app/modules/github/issue_context_client.py`, `source_client.py` and
  `upstream_issue.py`; `apps/api/app/modules/ingestion/code_collect.py`,
  `code_persistence.py` and `partial_snapshot.py`;
  `apps/api/app/modules/investigation/retrieval.py`, `routes.py`, `report_routes.py` and
  `report_worker.py`; `apps/api/app/modules/patches/routes.py` and `worker.py`; and
  `apps/api/app/workers/tasks.py`.
- Backend tests: `tests/test_investigation_evidence.py`, `test_investigation_reports.py`,
  `test_p191_partial_scope.py`, `test_p191_postgres_constraints.py`,
  `test_partial_snapshot.py`, `test_provider_harness.py`,
  `test_upstream_generation_guard.py`, `test_upstream_issue.py` and
  `test_upstream_partial_investigation.py`, all under `apps/api`.
- Frontend: `apps/web/components/investigation-workspace.tsx`,
  `apps/web/lib/investigation-client.ts`, the
  `apps/web/app/api/investigations/[repository]/jobs/[job]/upstream-context/route.ts`
  proxy, and `apps/web/tests/investigation-proxy.test.mjs` and
  `investigation-workspace.test.mjs`.
- Documentation: this record, `docs/p19-real-issue-verification.md`,
  `docs/verification.md`, `docs/repopilot-2-assessment.md` and
  `docs/patch-workflow-verification.md`.

The identified disposable PostgreSQL cluster was stopped; its disposable data and
credentials were removed. The private checkpoint is unapproved and must not be transmitted as an inference request without the remaining
re-establishment and one-shot enforcement work.

## P19.2 — durable approval work

The P19.2 internal ledger, guarded transport and checkpoint validation/restoration helper
were added without enabling scoped model calls. They are not an approval-ready invocation
path: shared authority binding, authenticated human approval, real worker integration,
independent daemon/egress checks and end-to-end restoration/replay verification remain
open. The prior request is unapproved; no inference or source execution occurred. See
[P19.2 durable inference approval](p19-2-durable-inference-approval.md).
