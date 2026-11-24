# P19 real-issue investigation: Stage A blocked

## Public read-only evidence

On 2026-11-18, anonymous GitHub API retrieval verified that the public fork
`roshan-pandit1/daytona` has parent `daytonaio/daytona`, default branch `main`, and
that its then-current main head was the requested commit
`a5b13df553f214ce2849741b4914b24fad576e01`. The separately retrieved upstream
issue is [daytonaio/daytona#2421](https://github.com/daytonaio/daytona/issues/2421).
The exact UTF-8 issue body was 241 bytes; its SHA-256 was
`5b64385923ec0a15aaaf0abe3e43a88f53f8120c464183f4125f2d4e787dbdb5`.
The upstream fix PR was not fetched or used. The issue reports SDK 0.27.1 and a
string-valued `createdAt`; that is a report, not an observed runtime result.

Two complete allowlisted UTF-8 files at the pinned commit were independently checked
against GitHub Contents API byte length and Git blob SHA-1, and against a second raw
response. Their original bytes were not normalized.

| Path | Bytes | SHA-256 | Git blob SHA-1 |
| --- | ---: | --- | --- |
| `libs/sdk-typescript/src/Snapshot.ts` | 11452 | `a0dc733aba6e704c4979b4ede50703b43e237fa239a0de14e4e9de176932ac59` | `70324e1606ff91fb108299b50b081a4275f857ba` |
| `libs/api-client/src/models/snapshot-dto.ts` | 2817 | `4bd91368df003087d64d1358bc747ff857e4606c1d306a62ae8304e2929347ab` | `37dbaa0ac9bf09963b33cbed1c35d386ff7f1ad2` |

The existing bounded text-only fallback reconstructed both files byte-for-byte, in
line windows 1–120, 121–240, 241–308 for the first file and 1–120, 121–152 for
the second. This was an offline text chunking check, not a persisted application
index, parser-backed retrieval, or application evidence manifest.

## Static observations and limitations

The SDK file documents date fields at lines 38–40 and defines its public `Snapshot`
type in terms of the API-client DTO at line 42. The DTO declares `createdAt` and
`updatedAt` as `Date` at lines 112 and 118, and `lastUsedAt` as `Date | null` at
line 124. In the SDK service, `list` (101–108), `get` (124–126), and `activate`
(269–270) use TypeScript assertions on returned data rather than conversion in those
methods. Whether lower-level client deserialization changes the values, the actual
API response shape, and runtime behavior remain unverified. No repository source was
executed and no root cause or fix is claimed.

## Mandatory application gate

The normal investigation route binds the issue URL to the authorized source
repository (`apps/api/app/modules/investigation/routes.py`, lines 110–126). The
investigation worker and patch worker later re-fetch the issue under that same
repository identity (`apps/api/app/workers/tasks.py`, lines 640–651;
`apps/api/app/modules/patches/worker.py`, lines 106 and 155). The issue in this pilot
belongs to the upstream repository, while the source belongs to the fork. Pretending
that it is a fork-hosted issue would misstate ownership and bypass this boundary.
The snapshot planner also resolves the default branch and requires a complete
recursive tree; it does not admit a pinned, explicitly partial file inventory as such.

No application investigation, evidence IDs, serialized inference request, or approval
hash was fabricated. The private raw evidence and metadata are held in owner-only
storage, but are not an inference-ready checkpoint. Fixing the application gate
requires a separately represented and verified issue origin, corresponding authorization,
worker rechecks, identity and uniqueness handling, and a truthful pinned partial
inventory with regression and migration coverage as needed.

## Verification and status

Focused in-process synthetic tests passed 214, with one PostgreSQL row-lock test
skipped and no failures. Ruff, offline lock verification, and `git diff --check`
passed. No PostgreSQL or Redis instance was started in this stage. No Ollama process,
inference, hosted AI call, generated patch, review, export, GitHub write, repository
script or repository test was run. No normal service or database was modified. The
upstream PR remains excluded; the approved local model is not yet reverified for a
future inference. Stage A is blocked and no inference authorization is requested.

## P19.1 continuation

P19.1 added an explicit direct-parent issue association and job-scoped pinned partial
inventory. A disposable PostgreSQL-backed application investigation produced genuine
Daytona evidence and a private mock-transport request capture. This supersedes P19's
statement that no application investigation was created; it does not authorize or
perform inference. The exact-hash single-use approval path and restoration of durable
identities remain unverified, so the captured hash is not yet approval-ready. See
[P19.1 verification](p19-1-upstream-issue-and-partial-snapshot.md).

## P19.2 — durable approval work

The P19.2 internal ledger, guarded transport and checkpoint validation/restoration helper
were added without enabling scoped model calls. They are not an approval-ready invocation
path: shared authority binding, authenticated human approval, real worker integration,
independent daemon/egress checks and end-to-end restoration/replay verification remain
open. The prior request is unapproved; no inference or source execution occurred. See
[P19.2 durable inference approval](p19-2-durable-inference-approval.md).
