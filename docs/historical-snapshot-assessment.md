# Historical snapshot readability: forensic assessment

**Implementation prepared; application deployment and legacy recovery are not authorized.**
Revision `0014` adds publication and evidence-manifest tables without backfilling existing
rows. The existing `repopilot-local` database remains at `0013`; do not start the changed API
or workers against it until a separately approved migration and deployment plan is executed.

- **Current published snapshot:** the existing `published` flag selects the snapshot eligible
  for new investigations; a recorded security/integrity revocation also blocks its use.
- **Historically published snapshot:** a new publication record is created atomically when
  the indexer publishes. A superseded snapshot can be read only for a completed, authorized
  investigation whose original publication record predates the job and whose completion
  manifest validates. Replacement does not itself revoke it.
- **Partial snapshot:** the publication record binds the original file, chunk and skipped
  counts. A verified historical read may show evidence from the indexed subset; the dashboard
  prominently warns that relevant code may have been missed.
- **Revoked snapshot:** the publication record carries an explicit security/integrity
  revocation timestamp and reason. The internal revocation operation locks the repository's
  snapshot and publication; no public mutation endpoint was added. A revoked publication
  cannot be used for historical reads or new investigations.
- **Legacy snapshot:** no publication event or manifest is invented on upgrade. Legacy
  investigations may retain existing current-snapshot behavior, but their superseded source
  remains unavailable without separately authorized and independently substantiated recovery.

The worker inserts the manifest under its job, repository and snapshot fencing, in the same
transaction as evidence and completed status. `evidence-v1` is SHA-256 over deterministic
sorted-key JSON containing job/snapshot/owner/commit identity and the ordered evidence IDs,
ranks, query metadata, chunk fingerprints and creation timestamps. Historical reads check
the count, digest, ownership, timestamp, each saved source fingerprint and line range. Saved
reports still undergo their existing citation validator. This is an unkeyed integrity digest:
it assumes the publication and manifest records are protected from unauthorized database
writes; it is not proof against an attacker who can rewrite both source and metadata.

The following is the original read-only assessment, retained for context. This assessment
did not change the application database, publication flags, investigations, reports or
index jobs. No GitHub write, paid provider call or migration was performed.

## What happened

The running API's sanitized structured logs contain `index_job_queued` for job
`34d8ea4f-0e45-4e03-a9f2-406bc7aa3d4b`. The only application code that creates an
`IndexJob` is the authenticated, CSRF-checked `POST /v1/repositories/{id}/index` handler;
the web's **Reindex repository** action calls that endpoint. This establishes the index
request path, not who or what initiated the HTTP request. Request access logs are disabled,
and the event does not record a button click or a requester identity. No evidence supports
attributing the request to a specific person.

The dispatcher log records dispatch of that ID and the worker logs its claim, source
collection, publication and completion. The database recorded creation at 09:10:02 UTC,
after the earlier empty-queue preflight, and one worker attempt. Code inspection found no
webhook, issue outbox or automatic reconciliation path that creates an `IndexJob`. The
dispatcher consumes an existing pending job and is not by itself evidence that a restart
created one. These findings do not prove the absence of an independently authenticated
client; they establish the supported path and observed processing chain.

The worker publishes the collected snapshot transactionally after authorization, repository,
commit and lease checks. It deliberately marks the job `partial` if files were skipped;
`publish_snapshot` first clears the old current flag and then inserts the new current
snapshot in the same transaction. The new snapshot
`b11f8c40-2d4b-4ab3-a4d4-d053249f8bc8` has the same commit as the old snapshot; the old
snapshot `5d24f965-fb26-431b-80b4-14275467c07d` is no longer current. The old snapshot
also recorded **one skipped file**, so its source collection is partial. Skips can result
from selection or sensitive/undecodable source filtering; no retained record proves which
condition caused this particular skip.

Read-only queries found the old snapshot still contains 135 indexed file rows and 1,482
chunk rows, matching its metadata. The two completed jobs each retained 20 evidence rows;
the existing verifier recomputed all 40 stored chunk fingerprints successfully. The saved
mock report's references also passed `render_report_payload` citation validation. These
checks demonstrate retained rows and consistency with the stored fingerprints; they do not
independently verify every byte of the full snapshot against Git or prove that a deleted
trailing evidence row never existed. No source text or credentials were logged.

## Why the read fails

Status, evidence, report and CIE routes compare the job's tenant, repository, snapshot and
commit with the *currently* published snapshot. On replacement, status reports
`snapshot_unavailable`, and evidence/report/CIE return a conflict rather than serving the
old source. Current user membership and session, enabled repository, active installation,
remote GitHub repository visibility, job owner and tenant predicates remain required; the
report/snippet paths also fence local revocation with locks. Evidence read checks row
ownership, snapshot binding, ranks, fingerprint and line lengths; report read revalidates
stored references and rebuilds GitHub URLs. Citation construction validates commit, path and
line ranges. These controls must remain in place.

Keeping completed investigations readable after a later index is a sound reliability goal,
but **the current schema cannot safely distinguish a superseded previously published
snapshot from one that was never published or was deliberately made unavailable**. The
`published` Boolean holds only the current state; `IndexJob` has no snapshot ID foreign key
or durable publication event. The transaction that completes an investigation verifies a
published snapshot, and the earlier read-only observation and screenshots establish what was
observed for this particular snapshot; those facts are not a general durable, queryable
publication/revocation history for every legacy row. Evidence fingerprints detect edits to
present rows, but no immutable expected evidence count or set digest proves a complete set
if rows are removed. Simply dropping `published` checks, trusting matching commit/counts or
matching an index-job timestamp, or treating every completed job as a publication record
would weaken the requested never-published and incomplete-evidence protections.

## Original proposal and legacy restrictions

The paragraphs in this section describe the proposal that preceded the implementation above.

After separate approval for an additive schema change in disposable PostgreSQL, record a
durable, tenant/repository/snapshot-bound publication event atomically when a validated
snapshot is published. Represent a superseded snapshot separately from one explicitly
revoked or invalidated, and preserve the existing single current-snapshot rule for new
investigations. Record an immutable evidence count and set digest when an investigation
commits, so a later missing evidence row fails closed. The precise authority, constraints,
locking and revocation semantics must be reviewed and tested before any application database
migration.

A historical read could then require a completed, owner-bound investigation, a matching
trusted publication record and pinned commit, no revocation, a complete evidence manifest,
all current session/GitHub/tenant/repository checks, verified source fingerprints and
unchanged report-citation validation. New investigations, indexing and retrieval must continue
to use the current published snapshot only. Legacy snapshots without independently provable
publication and manifest provenance must remain unavailable. Restoring access to existing
legacy jobs may additionally require a separately reviewed and explicitly authorized
privileged backfill, based on trustworthy retained evidence; never infer provenance solely
from an ID, matching commit or a completed job.

The user subsequently authorized conditional partial historical reads when publication and
the original evidence manifest are independently recorded and verified. This does not unlock
the two legacy jobs: their original durable records are absent, and no backfill is authorized.

For a future demonstration, use the existing job and avoid **Reindex repository**, index
API requests, enrollment/sync/index controls and automatic clients that can submit index
requests. Check pending work before starting; leave normal dispatcher and worker security
behavior intact. A fresh current snapshot alone cannot make old job IDs safe to read.

## Verification and remaining work

The final correction passed **103 focused PostgreSQL tests**, including actual concurrent
duplicate delivery and legacy migration tests, in disposable container
`repopilot-historical-check-642ff6d15020631e`. Alembic reached **0014** with no drift. The
adversarial fixture passed **33/33**; frontend tests passed **61**, TypeScript and targeted
ESLint passed, and Ruff and `git diff --check` passed. These checks used disposable or
network-isolated environments; no application database was migrated, and browser acceptance
of the new implementation is still pending.

Before the implementation, existing focused investigation, report, authorization and index workflow tests passed
**82/82** against a new empty disposable PostgreSQL database in retained container
`repopilot-historical-check-c434486675e02e04`. The same files on in-memory SQLite had
**74 passed, 8 skipped**; SQLite does not establish PostgreSQL locking behavior. Ruff and
`git diff --check` passed. These are regressions for the **existing fail-closed behavior**,
not proof of a historical-read fix. At that earlier assessment, no application code, schema
or application database had been changed and no historical-read implementation was tested.

Approval is still needed for an application-database migration, service deployment and any
separately reviewed privileged legacy-data remediation. The user's earlier screenshot demonstrates a CIE abstention before
the snapshot became non-current. GitHub citation navigation, history reopening after the
change and mobile acceptance remain unverified.
