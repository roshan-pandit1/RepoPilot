# Browser acceptance environment recovery assessment

**Read-only assessment, 2026-11-04.** No application services were started or stopped, no
database was migrated or restored, and no job, report or index was created. The combined
[browser checklist](browser-acceptance.md) remains blocked until a suitable environment and
existing examples are available. CIE-v1 is not yet verified by browser acceptance.

## What is available

| Source | Identity and findings |
| --- | --- |
| Docker `desktop-linux` context | Active and inspected. Docker `default` points to `/var/run/docker.sock`, where no daemon was reachable. Other contexts or machines are not ruled out. |
| Default Compose database | `repopilot-postgres-1`, volume `repopilot_postgres-data`, database `repopilot`: zero public tables and no `alembic_version` marker. It is not compatible with the current application. Its `postgres` maintenance database is also empty. |
| Isolated local database | `repopilot-local-postgres-1`, volume `repopilot-local_postgres-data`, database `repopilot`: revision **0013**, 35 public tables. It contains an enabled target repository `1435878031`, issue #1 and one published snapshot, but **zero investigations, zero mock reports and no active sessions**. Its `postgres` maintenance database is empty. |
| Isolated snapshot | Snapshot `5d24f965-fb26-431b-80b4-14275467c07d`, commit `1d26667b64527b41e67013bd00d326ab86ada8de`, 135 indexed files, 1,482 chunks and one skipped file. Current GitHub authorization and issue freshness were not checked. |
| Sprint 4F evaluation | `repopilot-4f-disposable-68ed7b3fd6171439` has the `4f-evaluation` label and a separate anonymous volume. It is a synthetic benchmark, **not** the normal application database and not a replacement for its historical jobs. |
| Other PostgreSQL volumes | Every other visible anonymous PostgreSQL volume is attached to a container labeled `5c1-checks` or `synthetic-restore-drill`. No unreferenced volumes were listed in the active Docker context. Nothing was deleted or attached elsewhere. |

Both application database inventories used `default_transaction_read_only=on` and returned
only schema markers, counts and the authorized repository's snapshot metadata. The isolated
database contains neither investigation `810a7792-7f48-45bf-8331-ad9aaaf416a4` nor parent
investigation `457d40bf-7e15-4e10-9a27-b8a0de9e513b`; it also contains zero evidence rows or
mock report/report-job records for those IDs. The default database has no application tables
to search. Historical records in `verification.md` associate mock report
`dbcbaa32-6330-475a-9da9-7bbb0f8e3305` with the latter investigation, but are not a database
backup and cannot establish present recoverability.

The formerly recorded `~/Library/Application Support/RepoPilot/backups` directory is absent
at that path. No matching RepoPilot dump was found in the searched Desktop, Documents,
Downloads, project tree or Spotlight queries. A broader home search encountered access errors,
so this is **not** an exhaustive search of the Mac, external backups, other Docker contexts or
other machines. The historical `repopilot-before-0009.dump`, if found, predates creation of
the 0009 mock report and the later `810a7792...` investigation; it cannot contain those later
records. A newer backup or another copy would need provenance and isolated restore verification.
Missing containers do not establish that data or volumes were deleted.

The running isolated API image lacks `code_intelligence.py`, and its web image lacks the CIE
proxy route. They predate the current CIE checkout. Database revision compatibility alone does
not establish that these images, GitHub credentials, active session or current issue are suitable
for acceptance. No image was rebuilt or restarted during this assessment.

## Shortest safe paths, prepared but not executed

1. **Recover existing examples if possible.** Locate a backup or another application database
   taken after both historical jobs and the mock report were created. First verify its identity,
   revision and contents using read-only inspection. Restoring it to a new isolated database,
   upgrading it to `0013` if required, and reconnecting services are separate actions requiring
   explicit approval. Never restore into or migrate the empty default database implicitly.
2. **Use the existing isolated `0013` environment if authorized.** It already has the target
   repository, issue and a published snapshot, so a new database and reindex are not inherently
   needed. Before any reconnection, review current source and image fingerprints, use separately
   named API/web images built from the checkout, keep worker/dispatcher processing disabled,
   confirm the database target and `0013` again, and start API/web without their Compose migration
   dependency (for example, a reviewed `--no-deps` procedure). Do not use `make dev`. The existing
   database has no target jobs or reports, so it cannot complete the checklist as it stands.
   There is no active session: GitHub sign-in creates OAuth/session records, so authentication
   itself is **not a strictly read-only database operation**. Current GitHub access and issue
   freshness must be revalidated; do not expose tokens or callback queries.
3. **Alternative fresh isolated demo plan.** Only after separate explicit approval, create a
   uniquely named project and new empty PostgreSQL/Redis volumes, confirm the target is empty,
   and apply migrations through `0013` there only. Use the verified personal-account public
   repository `1435878031` and authorized source data, or a separately prepared synthetic
   fixture clearly labeled as such. An empty database has no evidence or reports: creating
   or importing them, any reindex, and any live investigation or report require their own
   explicit authorization and security review. The existing shared demo authentication is
   rejected by investigation authorization, and the test-only fake GitHub client is not a
   ready-made authenticated browser demo. Do not claim this alternative works until verified.

The shortest path to the **historical** browser review is a newer verified backup or another
copy containing the requested records. If none is found, the existing isolated `0013`
database is the smallest prepared basis for a separately authorized new demonstration, but it
cannot currently satisfy the existing-job and report checks. CIE and Sprint 5C2 remain not yet
browser-verified. No setup, migration, new job, AI call, GitHub modification, or volume deletion
is authorized by or performed during this assessment.
