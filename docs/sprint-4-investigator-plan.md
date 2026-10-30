# Sprint 4 proposal: AI GitHub issue investigator

Status: **planning only**. Phase C3 verified locally, with incomplete retrieval labels and no
measured real semantic quality. No paid provider, remote reindex, deployment or GitHub write
is authorized by this plan. Choose specific acceptance thresholds from reviewed cases before
comparing implementations; do not use fake embeddings as evidence of semantic quality.

## Checkpoint 1: issue context and authorization

Define a bounded, versioned investigation input from the existing stored issue and repository:
issue ID/number, title, body, state, source update time, repository identity, and selected
published snapshot commit. Preserve issue text as untrusted data. Recheck the authenticated
session, membership, active installation, enabled public repository and current GitHub
visibility when creating a job and again when applying results. Explicitly handle deleted,
changed, unavailable, or too-large issue content. Do not infer undocumented GitHub data or
fetch private content. Tests: authorization, tenant isolation, stale/removed issue, bounds,
revocation during work, and sanitization of logs.

## Checkpoint 2: durable job lifecycle

Design additive migrations and an authenticated, CSRF-protected create/status interface for
investigations, with tenant/repository/issue ownership enforced by foreign keys and predicates.
Use the existing outbox/dispatcher/Celery patterns, leases and lock order; make retries,
deduplication, stale claims, cancellation and terminal failures explicit. Capture issue version,
snapshot ID and commit, configuration and a reproducibility identifier. No source code executes
and no writes are sent to GitHub. Tests: PostgreSQL concurrency, crash/retry idempotency,
revocation, cross-tenant access, stale snapshots, failure recovery and bounded work.

## Checkpoint 3: retrieval and evidence boundaries

Extract bounded search queries from issue context using a deterministic component first; use
existing authorized keyword search and optionally hybrid only where compatible embeddings
exist. Capture selected chunk identifiers, snapshot, rank and provenance with strict limits.
Require all evidence to belong to the job's still-authorized published snapshot and commit;
fail closed on reindex, revocation or model incompatibility. Tests: search fallback, snapshot
fencing, duplicate evidence, citation range validity, truncation and tenant isolation. Measure
retrieval separately from reasoning using v1/v2 and new issue-to-code cases.

## Checkpoint 4: mocked investigation and structured report

Introduce an injected model protocol with a deterministic, local mock only. Define a versioned
schema for summary, ranked hypotheses, evidence references, rationale, confidence/uncertainty,
missing information and explicit no-supported-hypothesis outcomes. Every factual source
assertion must reference validated selected evidence; validate all citations and reject malformed,
unknown, cross-snapshot or fabricated references. Record the model/prompt/schema versions and
failure state without logging issue text, source snippets, credentials or model requests. Tests:
malformed output, no evidence, conflicting evidence, bogus citations, stable ordering, retries,
and report access control. Hypotheses are suggestions and must not be represented as verified
root causes without independent evidence.

## Checkpoint 5: prompt-injection and data protection

Treat issue text, repository source, comments and model output as hostile. Delimit content as
data; never grant it authority to change system instructions, invoke tools, execute commands,
fetch arbitrary URLs or access other tenants. Use bounded retrieval and output, a strict schema,
authorization rechecks and citation allowlists. Test adversarial issues and source files,
exfiltration requests, forged tool instructions, cross-repository references, output injection,
redaction and fail-closed behavior. Prompt wording alone is not a security boundary.

## Checkpoint 6: reproducible issue-to-code evaluation

Create separately versioned, human-reviewed issue cases pinned to actual commits with explicit
relevant evidence, accepted hypotheses, ambiguous and no-answer cases, and incomplete-label
limitations. Score retrieval recall and citation correctness separately from report grounding,
hypothesis ranking, unsupported claims and abstention; include per-case failures, latency and
security tests. Use disposable databases, fixture Git objects and mocked LLM responses. Avoid
training/tuning on held-out cases or inventing labels. Retain the existing v1/v2 results as
independent baselines rather than merging snapshots or datasets.

## Checkpoint 7: paid-provider gate, later and separately approved

Before any paid experiment, implement and test durable token and request accounting,
concurrency and retry limits, job and experiment spending ceilings, fail-closed reservations,
explicit provider enablement and account-side limits. Review disclosure of issue/source data,
provider retention, model configuration, and a small costed experiment. Require separate user
approval for any paid call. A mocked model cannot establish real reasoning quality, and fake
vectors cannot establish semantic relevance.

At each checkpoint, run the focused tests and full relevant backend/PostgreSQL checks against
a disposable database, verify migrations and document evidence and unresolved limitations.
Any user-facing interface should follow only after the backend contract and security tests are
verified, and should preserve existing frontend changes.

## Checkpoint 4A implementation status

The bounded, authenticated read-only issue-context endpoint is implemented using fresh GitHub
reads and shared per-operation request limits. The API returns untrusted text with explicit
truncation indicators and rechecks access before returning. Mocked security and truncation tests
pass locally; the user reported 138 passing PostgreSQL tests and no Alembic drift in a
dedicated disposable database. Live verification of one public issue and unauthenticated
rejection has since been reported by screenshots; the issue had no comments and was not
truncated. Checkpoint 4A is verified locally within those limits. Later
checkpoints, investigation jobs and model calls remain unimplemented.

## Checkpoint 4B implementation status

A mock-only durable investigation job, transactional outbox, dispatcher and leased Celery
worker are implemented with additive migration 0007. Status remains **NOT YET VERIFIED**:
The user reported 145 passing PostgreSQL tests and migration 0007 without drift in a
dedicated disposable database. Real Redis/Celery orchestration remains pending. The normal application database has not been migrated; a live issue #1 run there
requires separate approval. No source retrieval, AI model or report has been implemented.

### Checkpoint 4B local verification

The user reported a real local PostgreSQL/outbox/Redis/Celery mock job reaching completed,
with correlated dispatcher/worker logs, a processed outbox and an idempotent duplicate replay.
The disposable PostgreSQL suite passed 145 tests, and the correct job status rejected an
incognito request. **Checkpoint 4B is verified locally**; this verifies orchestration only,
not an AI investigation or production readiness. See `docs/verification.md` for evidence and
limitations. No work on checkpoint 4C is included.

## Checkpoint 4C implementation status

Snapshot-fenced keyword evidence is implemented as an additive migration and extension of the
existing job/worker. Legacy 4B jobs retain their mock operation. New jobs pin the published
snapshot, check issue version and access, use bounded deterministic queries and persist unique
fingerprinted chunk references transactionally. The authorized evidence API fails closed on
revocation, unpublished snapshots or changed chunk data. Six synthetic cases have reviewed
labels for the local checkpoint commit. The disposable PostgreSQL suite passed 171 tests;
a six-case direct-worker evaluation found labeled top-10 hits in two of three positive cases,
with zero locally checked citation/chunk mismatches. Real 4C Celery verification remains pending. The normal database remains at its pre-4C revision until separately
approved. **Checkpoint 4C is NOT YET VERIFIED.** No checkpoint 4D or AI reasoning is included.

### Checkpoint 4C live orchestration evidence

The user reported a real local 4C job completed with 20 persisted chunk references, a processed
outbox, dispatcher and Celery lifecycle logs, one worker attempt and an idempotent duplicate
replay. All 20 references matched local Git objects and unauthenticated evidence returned 401.
The issue is generic and establishes no relevance quality. GitHub-hosted citation resolution
still needs confirmation, so **checkpoint 4C remains NOT YET VERIFIED**.

### Checkpoint 4C final local verification

A user-provided GitHub screenshot confirmed one returned citation at commit `6349190` and
lines 74–147; all 20 persisted chunks were previously verified against local Git objects.
Together with the real local PostgreSQL/outbox/Redis/Celery run, duplicate replay and
authorization checks, **checkpoint 4C is verified locally**. The generic live issue does not
establish retrieval relevance, and the separate synthetic natural-language case missed its
label in the top 10. The earlier statement that 4D had not begun is superseded below.

## Checkpoint 4D implementation status

An explicit report request for an already completed 4C job creates a separate leased report
task and transactional outbox event. The worker assembles a bounded issue/evidence projection,
uses only an injected deterministic in-process mock, validates all proposed references against
the job's published snapshot and verified chunk fingerprints, and atomically publishes a
structured report. Authorized reads reconstruct citations from persisted evidence and fail
closed on revoked access or changed source. Legacy 4B/4C jobs are not silently reprocessed.
Reports are labeled mock-only, and unsupported or absent evidence is explicit. No real model
or paid call is enabled.

The local non-PostgreSQL suite and synthetic mock mechanics tests pass, while PostgreSQL-only
tests, the 0009 PostgreSQL drift check, and a real Redis/Celery report run remain pending. The
normal application database has not been migrated for 4D, and no report task has been created
there. A fresh disposable PostgreSQL script is prepared; a normal-database migration and one
explicit report task require separate user approval after disposable checks. Redaction is
best-effort, and this mock cannot establish prompt-injection resistance or diagnostic quality
for any future real model. **Checkpoint 4D is NOT YET VERIFIED.**

### Checkpoint 4D final local verification

**Checkpoint 4D is verified locally**, superseding the pending status above. The user supplied
real local report-task, outbox, dispatcher and Celery evidence: one persisted mock report,
one worker attempt despite repeated deliveries, and one validated reference to the fenced
4C snapshot. Authorized report access succeeded and an unauthenticated request returned 401.
The host disposable runner reached its success marker, which its fail-closed script emits only
after PostgreSQL tests, Ruff and Alembic checks pass; the test-count line was not visible in
the supplied screenshot. The application reported 0009 at head without drift, and the backup
archive was read without an independent test restore. See `docs/verification.md` for the
evidence and limits. The mock is not real AI reasoning and does not establish diagnostic
quality or production prompt-injection resistance.

## Checkpoint 4E implementation status

The mock report request now uses a fixed application-owned instruction object and a separate
bounded untrusted issue/source object. Server-side output and evidence validation rejects
explicit role/tool instructions, unsafe control characters and invalid or cross-snapshot
references. A separately versioned synthetic adversarial dataset covers input and model-output
attacks; dedicated workflow tests exercise tenant and snapshot isolation, revocation, retries,
duplicate delivery, and safe output/log behavior. These checks do not prove a real model would
resist prompt injection. Secret redaction and output patterns remain incomplete.

The user reported 269 passing tests with no skips, Ruff passing and Alembic 0009 without drift
in a new dedicated disposable PostgreSQL database. The 33-case mock security evaluation also
passed. No live 4E job, real provider or unrelated frontend change was used. **Checkpoint 4E
passes locally within this mock-only scope.**

## Checkpoint 4F preparation status

`issue-report-v1` contains 19 synthetic issues, including the earlier natural-language
webhook-signature failure; 16 cases have 23 source-location labels checked against Git commit
`30705da4c044192cab4ac207e253ab8e8a1bd100` and the current source-selection/chunking rules.
The remaining three cases have no scored relevance judgment. The benchmark records incomplete
labels rather than treating unlabelled results as irrelevant. A rubric defines a future
independent human review but no substantive root-cause accuracy has been measured.

The user supplied host output showing 283 passing PostgreSQL tests, the 33-case adversarial
fixture, Ruff and Alembic 0009 without drift in the separate disposable checks procedure.
The user approved and ran the committed-source evaluation in a separate disposable database.
**Checkpoint 4F is VERIFIED LOCALLY** for synthetic keyword retrieval and deterministic mock
report mechanics. Its 16 scored cases have 12 labeled top-10 hits; 19/19 reports passed schema
and provenance checks. This does not measure real AI reasoning or diagnostic accuracy. See
`docs/verification.md` for complete metrics, security checks and the separation between the
committed source and evaluator working tree.
