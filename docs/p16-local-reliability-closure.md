# P16 — Local reliability and security closure (2026-11-16)

## Isolated environment and implementation

The P16 stack used PostgreSQL 16.16/pgvector 0.8.7 on loopback port 51474, Redis 7.4.11
on 16416, API on 3616, Next.js on 3615, a real dispatcher and real Celery 5.6.3 solo
workers on a dedicated queue. The cluster identity was checked before any database write;
Alembic reached 0018 and schema drift check passed. GitHub, source and generation inputs
were original synthetic fixtures. There were no Ollama calls, external repository source
transmissions or generated-code executions.

The existing patch lease was fixed at 120 seconds. P16 added `PATCH_WORKER_LEASE_SECONDS`,
default 120, with a validation rule that requires exactly 120 outside `APP_ENV=test` and
permits only 1–120 seconds in test. P16 used five seconds; no database timestamp was
rewritten. An automated settings test checks the default and rejects short production or
development values and out-of-range test values. Its initial test run had one failure due
to inherited demo authentication in the test fixture; explicitly disabling demo auth in
that test corrected the fixture, and the focused rerun passed five cases.

The patch panel now distinguishes `local_model_insufficient_evidence`, `provider_timeout`
and provider-unavailable outcomes in its copy. A focused frontend regression was added;
styles and layout were not redesigned.

## Natural expiry and stale completion

Two real Redis/Celery worker races ran through the real dispatcher and PostgreSQL. Worker A
claimed and paused after generating a candidate but before its final source check. Its
five-second test lease expired through elapsed time; worker B then acquired a different
lease and completed the same proposal. In the second race the database clock at B's claim
was checked against A's recorded expiry. Worker B's final proposal was `static_validated`,
unreviewed, with a processed outbox. Releasing A's late success in the first race and late
error in the second left the observed status, review, diff, error, outbox state and attempt
count unchanged. Celery logs recorded task receipt by both workers. These tests exercise the
short test configuration and two solo worker processes; they do not establish all production
broker failures or multiprocess behavior.

## Live security and application results

Two independent synthetic users and tenants were enrolled through the isolated API. User A
could not read User B's proposal, review it or read its evidence: each returned 404, and B's
review remained unreviewed. Anonymous evidence and invalid-session review returned 401;
missing CSRF returned 403. Tampering only the synthetic indexed file hash or snapshot commit
made an authorized proposal read return 409; the original values were restored. A repeated
request ID returned the same proposal (202). A rejected review could not be approved later
(409). A synthetic in-flight browser cancellation persisted as failed/rejected with
`reviewer_cancelled`, no diff and a processed outbox after the worker resumed.

Through actual HTTP and Celery delivery, fixture abstention, timeout, internal exception,
invalid source edit and invalid evidence reference each ended in a persisted failed proposal
with processed outbox and no diff. Their error codes respectively were
`local_model_insufficient_evidence`, `provider_timeout`, `worker_failed`,
`validation_failed` and `invalid_evidence_reference`. Synthetic session and token values
were not found in checked error responses. These fixture failures do not verify a live model.

The API has no client completion endpoint: a fabricated unsandboxed report to `/complete`
returned 404. Sending a fabricated body to the existing `/test-validation` request returned
202 as a request to validate, not as an accepted completion; with synthetic execution disabled,
the worker persisted `VALIDATION_UNAVAILABLE`, `sandbox_used=false` and no tests. Production
sandbox checks and defaults were unchanged. This does not substitute for a real isolated
repository execution environment.

## Readiness and WebKit

With workers available the API returned `/health` 200 and `/ready` 200; without a worker,
`/health` remained 200 and `/ready` returned 503; with Redis stopped those were 200 and 503.
An idle worker returned to ready after restart, with one initial 503 before a later 200.
A paused solo worker caused readiness 503; this is a bounded control-probe limitation,
not proof all workers are unhealthy. When the dispatcher was stopped while a worker was
responsive, readiness still returned 200. Readiness does not probe dispatcher progress. P16
therefore added `dispatcher: not_checked` to its successful readiness response; the frontend
health proxy continues to consume the HTTP status only. This is not a full pipeline health
or production-readiness signal.

Measured WebKit viewports 1440×900 and 375×812 showed the real persisted abstention,
timeout, generic failure and static candidate states. The browser used controlled request
interception for its failed-detail and failed-review tests: requests were redirected to real
404 responses, the list response was delayed to exercise the concurrent error race, and a
synthetic fetch rejection simulated a temporary API outage. Loading, visible errors and Retry
recovery passed. These are browser-contract checks, not proof of a real process outage and
recovery. A mobile test with the worker stopped showed worker-unavailable and queued states,
then canceled the proposal. A separate desktop test canceled a proposal while the worker was
paused at the completion boundary. An invalid session showed sign-in; the second tenant's
mobile browser received 404 for the first tenant's evidence without source disclosure.

## Tests, release status and cleanup

The focused PostgreSQL selection reported **246 passed, 0 failed, 0 skipped** with one pytest
warning caused by disabling the cache plugin while `cache_dir` remains configured. It included
source, authorization, patch, lease, readiness and API contract tests; those in-process tests
are distinct from the live broker and HTTP observations. Frontend Node 24: **96 passed, 0
failed**, TypeScript and ESLint passed, production build passed with 27 tracing warnings
because the private build used symlinked existing node_modules. Ruff, offline uv lock check
and `git diff --check` passed.

| Area | Status |
| --- | --- |
| Source provenance, static validation, PostgreSQL persistence | VERIFIED ON SYNTHETIC DATA ONLY |
| AI generation | VERIFIED ON SYNTHETIC DATA ONLY in P8; P16 provider was a fixture |
| Redis/Celery delivery, natural lease recovery, superseded-worker fencing | VERIFIED ON SYNTHETIC DATA ONLY for the stated solo-worker cases |
| Cancellation and API security | VERIFIED ON SYNTHETIC DATA ONLY for the stated live cases; not exhaustive |
| Frontend review and failure states | VERIFIED ON SYNTHETIC DATA ONLY; network-failure cases used interception |
| Readiness and monitoring | PARTIALLY VERIFIED; dispatcher and queue progress not checked |
| Real GitHub ingestion and real-source inference | BLOCKED; not exercised in P16 |
| Production patch execution | BLOCKED pending independently reviewed isolation |
| Deployment and production migration | BLOCKED pending operational approval and review |

P16 workers, dispatcher, API, web, Redis and PostgreSQL were stopped. Their loopback listeners
closed; disposable database storage, credentials, fixture source and temporary browser files
were removed. Verified runtime executables and sanitized PostgreSQL log were retained. Normal
services were not restarted or modified. Automated unit/regression tests cover the lease
configuration and existing fencing, but the P16 two-worker harness was temporary and is not
a permanent CI test. Actual browser recovery from a stopped API and dispatcher-progress
monitoring remain unverified. Production activation and untrusted repository execution remain
blocked.
