# P19.2: Durable inference approval — verification incomplete

## Scope and current result

The real-repository request remains **unapproved**. Scoped upstream and partial-snapshot
patch and report generation remain fail-closed. No model response, candidate patch or fix
exists from P19.2. No Daytona source or generated patch was executed, no real Ollama call
was sent, and no GitHub write or normal-service database migration was performed.

## Checkpoint and restoration

The owner-only P19.1 capture remains at
`~/Library/Application Support/RepoPilot/p19-evidence/p191-frozen`. Its 19,534-byte
mock-transport request still matches SHA-256
`5aee04451c945003f14c474dacca4995b5e66c68157247172714702858f5ce02`. It is not
authorization. The old checkpoint lacks persisted query/rank/timestamp/manifest records
needed to reconstruct the original evidence rows faithfully. The internal
`checkpoint_restore.py` checks separately supplied expected identities, owner-only
permissions, source and issue fingerprints, file and manifest identities, evidence
ranges/fingerprints, and exact old adapter bytes through a mock transport. Its restoration
helper submits through the existing authenticated upstream-investigation API rather than
inserting trusted rows. A recreated investigation gets new IDs; those IDs change the
outbound request, so the old request hash must not inherit an approval.

A clean-database integration used the real application endpoint, investigation worker,
and PostgreSQL keyword retrieval with fresh anonymous GitHub metadata and synthetic
application authentication. An initial disposable database was populated and fully
dropped; a separate newly migrated database then recreated the investigation using the
verified private checkpoint and allowed paths. The restored job is
`060dfc7d-bc68-4201-b89b-6b053d5a6251`, snapshot
`395e21b6-8a1c-46fb-bf7e-18b32018d741`, and partial inventory manifest SHA-256
`9fec360ce4c57b6f00c67f452b2fead263ad3e40ede1ddd1bbe6a5c7e9cd140c`.
Five application-created evidence references covered:

| Evidence ID | File and inclusive lines |
| --- | --- |
| `c452dcee-df43-446a-948d-fe3d3a1b49a8` | `libs/api-client/src/models/snapshot-dto.ts`, 1–120 |
| `e9a21067-ad1f-49c6-9a9a-643383a35bc8` | `libs/sdk-typescript/src/Snapshot.ts`, 1–120 |
| `f826ac3e-b140-4307-96d6-d7c6975e0e95` | `libs/sdk-typescript/src/Snapshot.ts`, 121–240 |
| `8af0b00f-4adc-498f-9eb0-9374bfbadd11` | `libs/sdk-typescript/src/Snapshot.ts`, 241–308 |
| `acd606ce-29dc-4b91-bba1-d57d7c182727` | `libs/api-client/src/models/snapshot-dto.ts`, 121–152 |

The adapter's no-send mock transport captured a new 19,534-byte body with SHA-256
`ff2404dae95aa452e13d14235c36195faa2fb61a884b53e12d1b13e56cfd84e0`. Fresh UUIDs
changed the wire bytes; the old hash and any hypothetical approval are not transferable.
The new owner-only checkpoint is under
`~/Library/Application Support/RepoPilot/p19-evidence/p192-restored-fbbf1d63aa20`.
It is unapproved and not an invocation-ready authorization. After database cleanup,
`load_restored_checkpoint` validated the restored checkpoint locally using a separately
verified predecessor and independently supplied expected new IDs and hash; it rechecked
all five evidence references and reproduced the exact mock-transport body. This local
validation does not establish that another fresh database can be rehydrated from the new
checkpoint, nor that any of its database IDs still exist. The checkpoint loader's synthetic
suite passed 11 tests. The rehydration used synthetic authentication and a disposable
database. A future run must create legitimate current records again and freeze a
correspondingly new request unless exact identity restoration is implemented and verified.
No source was transmitted to an inference provider.

## Internal ledger and transport work

`inference_ledger.py` implements a single-host SQLite prototype for cooperating processes.
It validates a versioned metadata identity, uses an owner-controlled private directory and
file, checks file permissions and links, and uses `BEGIN IMMEDIATE`, synchronous FULL and
macOS `fullfsync` for a claim committed before a send. Missing ledger files fail closed on
normal open; explicit creation uses a new directory. A claimed attempt is never released
for a timeout, crash or ambiguous result. Available states include awaiting approval,
approved, claimed, success, abstention, failure, unknown outcome and invalidation.

The internal `guarded_transport.py` checks the bound request bytes and identity before
claiming and forwards those same bytes only after the committed claim. Its tests use mock
HTTP metadata and a mock transport. A two-process race against one ledger and child exits
after claim before or after a synthetic send were exercised; these establish neither
exactly-once inference nor power-loss guarantees. No approval is fabricated: the internal
confirmation string is a programming guard, not proof of human identity, and there is no
normal API route that approves a real request.

## Open safety boundaries

The experimental components are not registered as a production provider or connected to
the normal patch worker. A single fixed authority is not enforced across every worker: two
separately created authorities could each claim the same request. Same-user file replacement
or rollback is outside the prototype's protection. The transport trusts injected resolver and
inner transport implementations; production revalidation against restored PostgreSQL state,
an independently authenticated Ollama daemon and verified egress controls are not integrated.
There is no authenticated human-approval entry point and no genuine Celery duplicate-delivery
or crash test of this gate. Local filesystem checks and SQLite synchronization are not a
security boundary against a malicious process running as the same macOS user.

Consequently, the captured hash is informational only and no inference approval is
requested. Complete and verify the fixed authority, authenticated human approval, actual
worker integration, post-cleanup identity handling and real broker/crash tests before asking the user to
approve a newly frozen exact request. A future approval can authorize **at most one outbound
attempt**. A process crash after claim can leave the outcome unknown and must never cause
automatic retry.

## Verification so far

The expanded in-process backend selection passed 461 tests, with 9 PostgreSQL-specific
skips and no failures; these include synthetic ledger, guarded-transport and checkpoint
tests, not new model inference. A separate focused safety selection passed 67 synthetic
tests with no failures or skips. The restoration used actual disposable PostgreSQL; it
was an integration run, not a claim that real Celery delivery or replay was exercised.
The frontend was unchanged in P19.2. Ruff, offline lock verification and `git diff --check`
passed. The owned PostgreSQL process was stopped; its data, credentials and socket were
removed. The private restored checkpoint remained owner-only and its request hash matched
after service cleanup. No durable real-request approval ledger was initialized or approved.

## P19.2 files

- `apps/api/app/modules/patches/inference_ledger.py` — internal SQLite authority prototype.
- `apps/api/app/modules/patches/guarded_transport.py` — internal exact-byte, mock-tested transport.
- `apps/api/app/modules/patches/checkpoint_restore.py` — private capture verification and restoration helpers.
- `apps/api/tests/test_p192_ledger.py`, `test_p192_guarded_transport.py`, and
  `test_p192_checkpoint_restore.py` — synthetic tests.
- This record and updates to `docs/p19-real-issue-verification.md`,
  `docs/p19-1-upstream-issue-and-partial-snapshot.md`, `docs/verification.md`, and
  `docs/repopilot-2-assessment.md`.

**REPOPILOT 2.0 — DURABLE INFERENCE SAFETY GATE STILL BLOCKED**
