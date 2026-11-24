# P17 — Local verification and execution-host handoff (2026-11-16)

## Pre-acceptance source integrity

The isolated P17 stack used PostgreSQL 16.16/pgvector 0.8.7, Redis 7.4.11, a real Celery
worker and an authenticated FastAPI service. The fresh database and broker were restricted
to loopback and checked against a private random marker before use; migrations reached 0018
and schema drift was clean. GitHub, source and generation provider boundaries were synthetic.
No real source was transmitted to a model and no patch was executed.

A valid synthetic proposal first reached `static_validated` with a processed outbox and one
provider invocation. For each of five cases, a proposal was queued while the context was
valid, then only the synthetic recorded state was tampered before delivery. A second fresh
proposal request returned HTTP 409. The already queued proposal was delivered through real
Redis/Celery and produced no diff, a processed outbox and **zero provider calls**:

| Tampering | Durable state / code |
| --- | --- |
| Source bytes | `stale` / `issue_or_snapshot_changed` |
| Recorded SHA-256 | `stale` / `issue_or_snapshot_changed` |
| Snapshot commit | `stale` / `issue_or_snapshot_changed` |
| Complete-file byte length | `failed` / `source_identity_or_size` |
| Evidence chunk range | `stale` / `issue_or_snapshot_changed` |

The original synthetic records were restored after each case. A duplicate task was submitted
for each terminal result and the state remained unchanged over the bounded observation; the
individual replay receipts were not independently correlated. An attempt to attach a chunk
from the other synthetic tenant was rejected by the PostgreSQL foreign key, and cross-tenant
HTTP evidence access returned 404 without source disclosure. The foreign evidence never entered
the worker because the ownership constraint prevented persistence. An unaffected candidate
after the cases again reached `static_validated` with one provider invocation.

Inspection found that a `COMPLETE_FILE` record with inconsistent recorded length, encoding
or normalization could silently fall back to unknown coverage. `assemble_context` now fails
closed for that contradictory claim; historical `UNKNOWN_COVERAGE` records retain their
existing semantics. In-process tests cover byte-length tampering both before provider invocation
(zero calls) and during generation (the provider saw the original valid synthetic context, but
no candidate was accepted afterward). The latter timing is not claimed as a live P17 test.

The first live run safely rejected source/evidence tampering but recorded an inaccurate
`authorization_or_github_unavailable` error. The patch worker now converts a 409 from its
snapshot/evidence lookup to `stale` / `issue_or_snapshot_changed`, while retaining the existing
authorization handling for other failures. The corrected real-worker scenarios were rerun.

## Opt-in two-worker regression

`apps/api/tests/test_p17_celery_race.py` and `apps/api/evaluation/p17_celery_race_support.py`
retain the real-worker regression. The test starts the actual dispatcher and two Celery solo
workers, uses a five-second lease only in `APP_ENV=test`, waits for natural expiry using
PostgreSQL clock evidence, and verifies that a new lease holder's accepted result survives
both an older worker's late success and late error. It uses a unique queue, bounded waits and
logs, and process-group and owned-queue cleanup. The production lease remains 120 seconds.

Run only against an independently provisioned disposable PostgreSQL database and Redis broker.
The guarded test requires numeric loopback endpoints, authenticated Redis, a dedicated
`p17_admin` role and `repopilot_p17_<16 lowercase hex>` database on a nondefault port, and a
64-character lowercase-hex marker. The database comment must be `p17:<marker>` and Redis DB 0
must contain the matching `p17:disposable-marker` key. Provision those markers only on resources
created for this test. The test fixture creates and drops application tables in that database;
**never use an application database or shared broker**. Supply credentials through a private
CI secret mechanism or owner-only environment file. With those prerequisites already set:

```sh
cd apps/api
P17_ENABLE_CELERY_RACE=1 python -m pytest -q tests/test_p17_celery_race.py
```

The environment must also explicitly contain `P17_DATABASE_URL`, `P17_REDIS_URL` and
`P17_MARKER`. An opted-in run without those variables was intentionally checked and produced
one expected setup error explicitly reporting the missing prerequisites (one test deselected).
The harness verifies the target identities and markers before selecting the destructive standard fixture. Without opt-in the real test is reported as skipped; with opt-in,
missing or mismatched prerequisites fail rather than becoming a pass. The final guarded run
reported **2 passed** (guard test plus real two-worker race). The first run reported one pass
and one failure because a synthetic authentication fixture was not imported; that harness bug
was corrected and the complete race was rerun successfully against the final worker code.

## Dispatcher and browser scope

Outbox attempts and retry deadlines advance even if publishing fails. Neither those fields nor
an empty queue prove that a particular dispatcher has successfully published work. No existing
attributable, bounded dispatcher-progress signal can establish health without introducing a new
cross-process protocol, so readiness continues to report `dispatcher: not_checked` and does not
claim operational or stale dispatcher status. `/health` remains API liveness. `/ready` now returns
sanitized `dependency` values `configuration`, `database`, `broker` or `worker` with 503, and
`dispatcher: not_checked`; it does not expose exception details. Live P17 checks showed health
200/readiness 200 with worker available and dispatcher stopped, health 200/readiness 503 with
`worker` after worker stop, and health 200/readiness 503 with `broker` after broker stop.

P16's browser network interruption and review/detail failures used interception and remain
browser-contract evidence; P17 did not repeat those scenarios or change the frontend. A real
frontend recovery test across an actual API outage remains unverified.

## Verification

The final PostgreSQL-backed selection reported **259 passed, 0 failed, 0 skipped**, with one
pytest warning due to disabling its cache plugin. Its first run had **258 passed, 1 failed**:
an existing mocked-provider source-change test still expected the old `failed` classification.
Its safety assertion remained intact and its expected status was updated to `stale` with the
new error code; the full selection then passed. The opt-in real-worker selection passed **2**;
without opt-in its guard unit test passed and the real-worker test was **skipped** explicitly.
The 17 readiness tests passed in-process. Ruff, offline uv lock verification and `git diff
--check` passed. No frontend files changed during P17, so its P16 frontend checks were not rerun.

## Execution-host handoff

The selected direction is a dedicated Linux KVM worker pool with one Firecracker microVM per
job, as specified in [P12 execution-host prerequisite](p12-execution-host-prerequisite.md).
No host, guest, Firecracker binary or production runner was provisioned or tested in P17.

Before implementation, the infrastructure owner must provide a dedicated, hardened Linux
x86_64 or arm64 host with a verified usable `/dev/kvm`, a supported host kernel, scoped runner
identity, maintained microcode and a patching/incident-response owner. Pin and verify the
Firecracker and jailer release, guest kernel and immutable root image against independently
verified checksums/signatures, and keep a software inventory. Apply jailer, seccomp, separate
namespaces and per-job host cgroups. Give the guest no network interface, NAT, DNS or host
service sockets; separately restrict host-runner egress. No home, project, Docker socket,
credential, SSH agent, cloud identity or arbitrary host filesystem mount may enter the guest.

Authenticate the application-to-runner channel with scoped service identity. Bind each job to
its tenant, investigation, lease, nonce, snapshot/commit, source and patch hashes, test-spec
identity, expiry and resource policy. Transfer only bounded verified artifacts via a reviewed
input disk or restricted protocol. Bind and authenticate the returned envelope to those values,
the guest/kernel/runtime identities, outcomes and cleanup status using a host-held key unavailable
to the guest. Fail closed on missing attestation, identity mismatch, timeout, cancellation,
resource-limit failure or cleanup failure; never map an unsandboxed report to production success.

Initial limits require review and measurement: at most 2 vCPU, 2 GiB RAM, 512 MiB per-job
scratch, 64 guest processes, 60 seconds wall time and 1 MiB captured output. Use disposable
per-job storage and a host watchdog; cancellation must kill the owned VM/cgroup, invalidate
its lease and verify resource deletion. Record bounded, sanitized audit events for authorization,
image identity, limits, outcomes and cleanup, with monitoring, alerts and retention policy.

An independent security review must test guest egress/IPv6, host files, credentials, service
sockets, device access, isolation escape, concurrent tenants, replay, stale leases, malformed
or oversized responses, resource exhaustion, crash, cancellation and cleanup failures. Start
with synthetic-only acceptance, then require separate approval for any real-repository pilot.
Roll out disabled, canary only after review, and retain a kill switch and rollback to
`VALIDATION_UNAVAILABLE`. Budget approval must cover the dedicated KVM-capable host, storage,
monitoring, image maintenance and on-call capacity; no provider, price or paid deployment was
selected. Existing source identity, patch validation, outbox and lease-fencing code can be
reused; a production Firecracker driver, authenticated transfer, guest image, attestation,
isolation acceptance and operations remain unimplemented or unverified.

P17 API/worker, broker and database were stopped. Disposable P17 storage, credentials,
sockets and fixture scripts were removed; sanitized verification evidence and existing runtime
executables were retained. Normal services and frontend were not restarted or modified. The
next action is an explicit execution-host provisioning and independent security decision, not
production activation of the existing synthetic test paths.
