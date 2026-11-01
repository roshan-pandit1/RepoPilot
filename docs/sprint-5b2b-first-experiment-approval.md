# Sprint 5B2B: first real-model experiment — draft approval packet

**Sprint 5B2E: VERIFIED LOCALLY — FAKE-TRANSPORT INTEGRATION SCOPE; real counting and generation remain BLOCKED.** Migration
`0013` adds an external-only count authorization distinct from the simulated table and
generation approval. Live preflight now requires the exact external count and organization/
project binding, but both actual-pricing gates fail unconditionally and the count switch is
off by default. The retained full-window reservation is unchanged. No external approval,
count request, real generation or application-database migration was performed. The updated
disposable PostgreSQL run `8d8ccdd6c8a29bc9` passed 384 selected tests with zero skips,
33/33 adversarial checks, Ruff, Alembic `0013` without drift and exit status 0; its 133-file
fingerprint matched the source at that checkpoint, before later retrieval changes. The first 373-test 5B2E host run predates the
subsequent one-shot gate, PostgreSQL guard and expanded sender tests.
The one-shot path requires paid background workers to remain off; count and generation use
separate settings and approvals. Prior staged identities and hashes are invalid.

**Sprint 5B2D: real execution remains BLOCKED.** The proposed mandatory real-count and
reduced-reservation policy was a specification at that checkpoint. The 5B2E live preflight
now requires an external count, while the fake executor retains its optional simulated path.
The full-window reservation remains $5.815551 and the actual-pricing gate remains closed.
Fresh PostgreSQL verification of the added 5B2D
fake-transport tests passed in run `383e0af929ee80d2`; the historical 2C host fingerprint
predates those tests and runner changes.
The [policy and proof obligations](sprint-5b2b-token-budget-plan.md#sprint-5b2d-proposed-fail-closed-policy)
must be met before requesting either a real count or a generation approval.

The 5B2D SQLite backend suite reported **477 passed, 22 skipped**; its focused new policy
cases reported **14 passed, 1 PostgreSQL-only skip**. The **33/33** adversarial fixture,
Ruff, shell syntax and `git diff --check` passed. The extended disposable host runner
`apps/api/evaluation/run-5b2c-checks.sh` subsequently reported **324 passed, zero skips**,
including the new concurrent counted-generation case, **33/33** adversarial checks, Ruff,
Alembic `0012` without drift and exit status 0. Its 131-file source fingerprint matched the
independently recomputed fingerprint. Its name reflects the earlier checkpoint; its required
cases now include 5B2D. See the retained [host log](../apps/api/evaluation/5b2c-383e0af929ee80d2.log).

**CHECKPOINT 2C VERIFIED LOCALLY — FAKE-TOKEN-COUNT SCOPE.** The
new count authorization is simulated and distinct from generation approval. No real count or
generation request, paid approval, fresh staged experiment or application database migration
is authorized. The count API's account-specific fees and retention, model/project access and
a guaranteed count-to-generation input bound remain unknown, so the paid experiment remains
**BLOCKED** and its full-window $5.815551 generation reservation is unchanged. See the
[token-budget plan](sprint-5b2b-token-budget-plan.md).
Local backend regression: **463 passed, 21 skipped** on SQLite; the focused count suite had
**65 passed, 1 PostgreSQL-only skip**. The adversarial fixture passed **33/33**, Ruff and
shell syntax passed, and a disposable SQLite migration reached `0012` without drift.
Disposable PostgreSQL run `e1593aaca7524a85` subsequently passed **309 tests with no skips**,
including the runner-guarded approval and reservation races, **33/33** adversarial checks,
Ruff, and Alembic `0012` with no drift. The before/after 131-file source fingerprint matched
the independently recomputed source, and the retained log records exit status 0. This verifies
fake transport and database mechanics, not real provider behavior or provider billing.

**CHECKPOINT 2B: BLOCKED.** Account-specific pricing and model access are unverified, and
the former full-context reservation exceeds the $6 cap under the two-*additional*-uplift
stress policy. Actual approval recording and live execution are blocked in code. The
historical staged run below is invalidated by the changed request-limit and manifest policy,
even before its expiry; none of its IDs, hashes or old commands authorizes a request. No
paid request or approval is authorized by this document.

**SPRINT 5B2B CHECKPOINT 1 VERIFIED LOCALLY — DRY-RUN AND FAKE-TRANSPORT SCOPE.** The
real-model experiment remains **NOT YET VERIFIED**, and this packet does not authorize it.
Checkpoint 2 has additional source-screening, usage-validation and provider-correlation changes;
the checkpoint 1 host run is historical evidence and does not verify those later changes.
The current disposable PostgreSQL run and staged request identity are recorded below. Account
model availability and billing terms still require confirmation before any paid approval.
The isolated approval-bound executor passed a 376-test disposable PostgreSQL host suite,
including fake execution, approval and budget races. The existing 5B2A evaluation runner
is still fake-only. Independent security review and a positive actual-mode approval path
remain untested. Tests include an isolated actual-mode ledger simulation using fake transport;
no paid request, live-provider enablement, live paid experiment or live job was authorized or
created here.

Checkpoint 2B local verification: **394 SQLite tests passed, 20 PostgreSQL-dependent tests
skipped**, the adversarial fixture passed **33/33**, Ruff, shell syntax and `git diff --check`
passed. The user then ran fake-only PostgreSQL pricing regression `845d50be264c481f` on a
new, confirmed-empty disposable database: **239 tests passed with no skips**, security checks
passed **33/33**, Ruff passed, and Alembic **0011** had no drift. The host runner's success
marker requires its named pricing, approval and concurrency tests. Its before/after 128-file
fingerprint `0defb35e5ff2f5fbea6381b5316927ebcf5fea56a0d370256bd35b78eef5b685` matched
the independently recomputed source before checkpoint 2C; docs and installed dependencies are
outside its scope. The user reported exit status 0; the retained
[log](../apps/api/evaluation/5b2b-pricing-845d50be264c481f.log) contains the success marker
but does not independently record the numeric shell status. **The PostgreSQL pricing-regression
blocker is RESOLVED** for that source. No token-count endpoint was called.

## Proposed operation

| Item | Proposed restriction |
| --- | --- |
| Provider and model | OpenAI Responses API, `gpt-5.6-terra`; verify account availability, exact model identity and pricing immediately before any approval. |
| Request | At most **one** provider request, maximum concurrency **one**, zero automatic retries, no tools, browsing, shell or GitHub writes. Use structured output, `service_tier=default`, 30-minute prompt-cache policy and `store: false`. |
| Fixture | Synthetic `signature_exact` from `apps/api/evaluation/issue-report-v1.json`, dataset SHA-256 `416cbf9e46b9399cf78d118f581a882d16cf512da439d352d3af29674c447bf6`, source commit `30705da4c044192cab4ac207e253ab8e8a1bd100`. The reviewed label is `apps/api/app/modules/github/security.py`, `valid_signature`, inclusive lines 6–8. |
| Environment | A new, uniquely named disposable PostgreSQL database; additive Alembic `0013` passed disposable PostgreSQL upgrade and drift verification in run `8d8ccdd6c8a29bc9`. Synthetic GitHub data and source snapshot only. No normal application database migration, live investigation, live GitHub issue or repository reindex. |
| Budget | Local experiment ceiling **$10**, per-investigation ceiling **$6**; the retained full-window ledger reservation is **$5.815551** before additional stress, which fails the new stress gate. |
| Token bounds | The ledger still reserves the full **1,050,000**-token input context window and at most **2,048** output tokens, including reasoning tokens. The adapter now limits the complete canonical serialized request to **8,192 bytes**, including instructions and output schema. Bytes are not a verified input-token bound. |
| Failure | No automatic retry after a request could have been sent. Timeout, interruption, unknown usage or incompatible billing metadata retains the reservation pending explicit reconciliation. |

These are local controls under stated assumptions, not a provider-side invoice guarantee.
The $10 ceiling is scoped to this experiment, not the provider account as a whole. The
approval is an operator-managed database record with hashes, not a cryptographic signature
or a separate multi-user approval service; an administrator with database or code access can
alter these controls. Account-level usage limits and independent access review remain needed.
The previous 5B2A run used a partial snapshot and fake transport; its run, snapshot, request
hash and synthetic job IDs are not approval for a future request. The checkpoint 2 request
authorizes an isolated synthetic preparation without paid approval or a provider call. The
resulting identifiers and outbound projection must still be reviewed before seeking separate
authorization for the single paid request.

## Historical staged synthetic identity — not reusable

Run `b3fa0088237c0c7a` used the fresh disposable container
`repopilot-5b2b-readiness-b3fa0088237c0c7a` and database
`repopilot_5b2b_b3fa0088237c0c7a` at revision `0011`. The source commit is
`30705da4c044192cab4ac207e253ab8e8a1bd100`, synthetic repository ID `902`, tenant ID `1`,
and issue ID/number `990`/`5`.

| Field | Actual staged value |
| --- | --- |
| Snapshot | `afa6679c-4822-44c2-bfd9-3ac635068945` |
| Investigation | `98678679-7c39-4cca-9ae2-f516542e350a` |
| Report job | `91fa2b4b-6695-4a12-bad9-63118cd36ae1` |
| Simulated experiment | `e707c7d9-203c-45df-92f6-9722316eb317` |
| Evidence row / chunk, rank 1 | `00cb929f-6008-4218-8e0f-ee24e7bbfca5` / `62584d6c-554b-45d6-a646-030cc8c222c1` |
| Evidence row / chunk, rank 2 | `73edb9c9-e1be-4693-ac6f-65d511461543` / `f5b2039a-d923-4b00-a432-d5e0dae1f9a2` |
| Exact canonical request SHA-256 | `9211ff97ef966d0d648d3d175a1808116c576e7cd80adee746fed82a8a2700b5` |
| Exact manifest SHA-256 | `87f82f93e7338fe567cd43270b163dc268ad2e47326da8968f78977da5a46b0b` |
| Private review directory | `/var/folders/_c/0_0hnx511fv_xrhvjwxw5c840000gn/T/repopilot-5b2b-b3fa0088237c0c7a-l8mxzzg3` |
| Experiment / session expiry, UTC | `2026-11-01T03:20:26.146556+00:00` / `2026-11-01T03:25:25.939400+00:00` |

The staging artifact records one completed synthetic parent, one queued synthetic report
job, **zero approvals, zero reservations and zero reports**. There is no paid approval ID.
The exact private files were independently re-read, reconstructed from committed source and
rehashed; their permissions and the associated 128-file source fingerprint matched. The
sanitized [run artifact](../apps/api/evaluation/5b2b-readiness-b3fa0088237c0c7a.json) and
[host log](../apps/api/evaluation/5b2b-readiness-b3fa0088237c0c7a.log) retain the results.
At `2026-11-01T02:41:06Z` this experiment had not yet reached its recorded expiry; it was
expired when checked after `03:23Z`. It is also **invalid for future approval** because the
code, byte limit and manifest policy have changed. It must not be revived or replayed. A later separately scoped
verification must create and review a fresh synthetic run, snapshot, investigation, report
job, experiment, evidence IDs, request and manifest hashes, pricing evidence and expiry.
Retain the historical artifacts; do not extend the old record or silently reuse any IDs.

The historical sanitized [disclosure template](../apps/api/evaluation/5b2b-disclosure-template.json)
contains **placeholder** snapshot, evidence, experiment and job IDs. Its request SHA-256 is
`2448dd78bafd00dad82a7a4e39addafb6b0309d5bffa3e6174367119abff019c`; the manifest
SHA-256 is `f8b62ef29ded70fa0177b02ebc1a0269358b211fb839fb81f418f4bf9ef2af1c`.
Neither hash authorizes a real request. The template describes the synthetic issue title and
body, source excerpts from `apps/api/app/modules/github/security.py` lines 6–8 and 1–5,
commit-pinned citations, synthetic identifiers, application-controlled instructions and the
strict output schema. The adapter sends the default tier, 30-minute cache policy, 2,048
output-token limit, `store: false` and disabled truncation; it supplies no tools or optional
API metadata field. Reasoning effort is not explicitly set and is provider-dependent. The
template request was 3,816 bytes. The staged request was independently rehashed at 3,826
bytes, including 445 instruction bytes and a 1,215-byte canonical schema. A bytes/4 heuristic
is **not** a verified token count or billing bound. The ledger reserves the entire input window.

## Pricing and reservation review

On **2026-11-01**, OpenAI's [GPT-5.6 Terra model page](https://developers.openai.com/api/docs/models/gpt-5.6-terra)
listed standard pricing of $2 per million input tokens and $12 per million output tokens,
with 2× input and 1.5× output for requests exceeding 272,000 input tokens. Its
[prompt-caching guide](https://developers.openai.com/api/docs/guides/prompt-caching)
describes the 1.25× input rate for 30-minute cache writes; its
[pricing page](https://developers.openai.com/api/docs/pricing) describes a 10% uplift for
eligible regional processing endpoints. The reservation conservatively assumes all input is
a 30-minute cache write, long-context pricing applies, and a further 10% allowance applies:

```text
1,050,000 × $2 / 1,000,000 × 2 × 1.25 × 1.10 = $5.7750000
    2,048 × $12 / 1,000,000 × 1.5 × 1.10     = $0.0405504
Total rounded up to the next microdollar       = $5.815551
```

The bound deliberately counts the full input window plus output. It assumes the exact model,
standard tier, 30-minute cache policy and no extra provider fees. Recheck current pricing,
model alias behavior, account and project configuration, provider terms and the ledger's
policy immediately before approval; fail closed if the charge cannot be bounded. The
experiment's pricing review and expiry must satisfy the ledger's 24-hour rules. The local
ledger cannot guarantee the provider's invoice or prevent later billing discrepancies.
The pricing page also lists a 10% FedRAMP endpoint uplift effective November 1. The proposed
adapter uses the standard Responses endpoint, and this reservation includes only one 10%
allowance; do not assume it covers combined or other additional fees. Verify the actual
account, endpoint and any stacking before approval, and block execution if they cannot be
bounded by the reviewed reservation. The 1.25× 30-minute cache-write rate is the **total**
input rate for those tokens, not an additional 1.25× fee on top of an ordinary input charge.
These official pages were rechecked for 5B2D on **2026-11-01**. They do not confirm the
project's effective prices, count-endpoint fees, applicability or stacking of regional and
FedRAMP uplifts, or a hard provider invoice ceiling. Both are listed as 10% uplifts under
their stated conditions; the public material reviewed does not settle whether they combine.

The previous packet ambiguously treated the rounded $5.815551 ledger reservation as if it
had not already included one 10% allowance. Using that ledger amount as the stress **base**,
the corrected hypothetical calculations are:

```text
Base ledger reservation                    $5.815551
One additional 10% uplift                 $6.3971061    (ceil: $6.397107)
Two additional compounded 10% uplifts    $7.03681671   (ceil: $7.036817)
Largest whole-microdollar base under $6   $4.958677    (6 / 1.21 rounded down)
```

These are stress scenarios, not a claim that additional fees actually apply or stack. Public
documentation lists a 10% regional endpoint uplift and, from November 1, a 10% FedRAMP
endpoint uplift, but it does not establish this project's account terms or whether these fees
can combine. The adapter uses the standard endpoint. The actual account, endpoint, custom
contract and any other fees must be checked privately. If they cannot be bounded, **pricing
approval remains BLOCKED**. Do not raise the cap or claim the stress value is a provider
invoice without a revised policy and separate authorization.

An illustrative future limit of **16,384 verified input tokens** and 2,048 output tokens,
using the existing conservative long-context/cache rates and the already included allowance,
would reserve **$0.130663**; applying two *additional* 10% stress uplifts gives **$0.158103**
rounded up. This is a planning calculation only: no verified 16,384-token limit exists, the
ledger has **not** been reduced, and no request may use this number. The 8,192-byte body
limit alone cannot prove a token cap because provider formatting, schema and hidden-token
accounting are not bounded by that byte count. OpenAI's
[token-counting guide](https://developers.openai.com/api/docs/guides/token-counting) explains
that local counts can miss schema and formatting tokens. Its input-token count endpoint would
be a separate external disclosure/request and was not called or authorized here. A future
reduction needs a verified, request-bound token upper bound and uncertainty policy, durable
ledger implementation, and renewed disposable PostgreSQL tests.
The [token-counting guide](https://developers.openai.com/api/docs/guides/token-counting)
states that the output limit includes non-visible generated tokens. No provider token-count
request has been made.

The [published pricing page](https://developers.openai.com/api/docs/pricing) states that the
Responses API is not separately priced apart from the selected model's charges. Some tools
have separate fees, but this request supplies no tools. Actual project contracts, taxes,
region, account configuration and any other charges are not established by public rates.
Reasoning tokens count toward the 2,048-token output limit and are charged as output; this
limit may still produce an incomplete structured report. Public model documentation does not
confirm access for any particular project.

## Approval and execution audit

| Boundary | Reviewed control and remaining limit |
| --- | --- |
| Approval identity | The stored one-use record is bound to experiment, job, tenant, snapshot, fixture, commit, provider/model, canonical request hash and manifest hash. A reviewed request is reconstructed from the pinned fixture and current synthetic job. The positive paid-approval path was not run in this checkpoint. |
| Replay and concurrency | The report job and experiment are locked, then the approval row is locked; consuming the approval and marking its reservation sent occur in the same PostgreSQL transaction. Fake-transport PostgreSQL race tests are required for the current code. A database administrator can alter records or code, so this is not independent multi-party authorization. |
| Budget and crash | Reservation precedes the send marker; one request and one concurrent reservation are allowed. An uncertain response retains the full amount. A crash before the marker is distinguishable from a potentially billed post-marker failure; no automatic paid retry is allowed. |
| Configuration | API key presence alone does not enable the provider. Dashboard requests cannot instantiate the approval-bound live adapter, and fake mode uses `MockTransport` plus a Python network fence. The fence is not an OS sandbox. Real flags must never be configured on normal background services. |
| Authorization and citations | The worker rechecks its session, installation, repository, tenant, issue and snapshot, and validates citations against persisted evidence before publication. The final experiment uses a synthetic GitHub client; it does not prove current live GitHub authorization. A revocation can race an external network send even when rechecked immediately before it. |
| Data and tools | The request contains only the pinned synthetic issue and sanitized selected source, with no model tools, shell or GitHub write integration. Source filtering and prompt-injection resistance remain imperfect. Do not treat the model's statements as authorization or verified diagnoses. |
| Observability | The ledger and safe provider events record request correlation and conservative accounting. A provider request ID with an unfamiliar format is omitted, and rejected raw claims are not logged. Any independently verified invoice amount must be recorded separately. |

The operator must compare the generated private files and hashes with the sanitized artifact
from the same disposable run, check its source fingerprint and expiry, and confirm no
approval or reservation exists before requesting paid authorization.

## Information leaving the machine

Before any request, inspect the exact sanitized input, structured instructions, evidence
metadata and commit-pinned citations. The template contains a synthetic issue title and body
and sanitized chunks from the committed source file at lines 6–8 and 1–5. It records 34 title
bytes, 84 body bytes and source excerpt sizes of 249 and 51 bytes; actual persisted evidence
may differ and must be reviewed. The committed file contains a signature-verification
function and imports; the review found no credential values or unrelated private information
in that file. Its function parameter is not a credential value. Source literals and sensitive
identifiers are redacted; these checks cannot establish that all possible secrets are absent.
No credentials, cookies or environment variables should be included in the request. The
[redacted source-disclosure review](sprint-5b2b-disclosure-review.md) lists hashes of the
original committed ranges and sanitized excerpts. Review
the exact generated request and repository disclosure requirements before future approval.
`store: false` is not a promise of zero retention; review the provider's current
[data controls](https://developers.openai.com/api/docs/guides/your-data) and account policy.

## Commands and separate approval actions

The following local command is offline and makes no database or provider request:

```bash
cd "/Volumes/Samsung SSD/Project/RepoPilot/apps/api"
../../.venv/bin/python -m app.evaluation.experiment_executor --dry-run
```

It creates a fresh private temporary directory and prints its path and hashes. `request.json`
contains the exact canonical request bytes, including the full sanitized instructions, input
and schema; `manifest.json` contains hashes and disclosure metadata. The directory is mode
`0700` and the files are mode `0600`. Do not paste their contents into logs or chat. The
template uses placeholders, and a later run must prepare and review its own request.

For the current fake-only token-count PostgreSQL regression, use the following host command.
It does not stage a new experiment or invoke OpenAI:

```bash
cd "/Volumes/Samsung SSD/Project/RepoPilot"
bash apps/api/evaluation/run-5b2c-checks.sh
```

It creates and retains a uniquely named disposable container, database and log. Tests create
and remove their own fixture tables inside that database; only that disposable database is
upgraded to the current head `0012`. Its combined API/test/migration/dataset fingerprint must remain unchanged
during the run. The Python socket fence and offline Git settings are not an operating-system
sandbox against arbitrary native code or subprocesses.

Only after a separately approved, explicitly scoped future verification, the existing
`apps/api/evaluation/run-5b2b-readiness.sh` can prepare a fresh simulated experiment and
private review after its own disposable tests. Do not run it merely to refresh an expiring
record. Its generated snapshot, investigation, report job, experiment, evidence IDs,
request and manifest hashes, source fingerprint, limits and expiry all need fresh review.
The actual-pricing gate remains blocked even if the synthetic setup is prepared.

## Account and project review — private, no API calls

**Pricing approval: BLOCKED.** An authorized account administrator should privately review
the following in the OpenAI API Platform UI. Do not paste API keys, organization secrets,
card details, credential screenshots or account identifiers into this repository or chat.
Record only pass / fail / unknown, the review date, and a nonsensitive reference for follow-up.

1. Select the intended organization and project. Confirm the intended credential belongs to
   that project without displaying its secret. The 5B2E live generation and count paths bind
   explicit organization and project headers to the reviewed hashes; fake tests use synthetic
   identifiers only. An ambiguous legacy credential or default organization is insufficient.
2. Check that `gpt-5.6-terra` is permitted for that project and that the effective project role
   and credential have model-capability request and Responses API permissions. Public model
   documentation is not evidence of project access. If the UI cannot establish access, ask an
   administrator or OpenAI support. Do not call a model-list or generation endpoint.
3. Review model-specific organization and project rate limits and shared limits. Confirm the
   project has appropriate billing setup, credit and spend headroom; a spend alert is not the
   same as a provider-enforced hard spend limit. Do not change billing settings in this review.
4. Verify standard processing, the actual endpoint and whether regional or FedRAMP charges
   apply. Check custom contract prices, taxes and other relevant fees, and whether any uplifts
   stack. Get billing/support confirmation if terms are unclear. The local ledger is not an
   invoice guarantee.
5. Review data retention and whether disclosure of the exact synthetic issue, two sanitized
   source excerpts, public repository links, schema and metadata is permitted. The 30-minute
   cache-write rate is total input pricing for those tokens. No provider call is authorized by
   this checklist.
6. Mark all unknown items BLOCKED. Separately obtain a verified, request-bound upper token
   limit covering instructions, structured schema and provider overhead. The OpenAI input-token
   endpoint itself is an external API request and disclosure; it requires separate explicit
   authorization, a pricing review and a no-retry policy before it could be considered.
7. Ask the account administrator or OpenAI support whether the count endpoint is billable for
   this project, including failed or timed-out calls; determine a bounded fee and retention
   policy. Verify whether the same canonical model/input/schema projection and account can be
   relied on for the later generation count and how a model alias or hidden framing can change.
   Record only the date, a nonsecret reference and pass/fail/unknown. No response from support
   or estimate constitutes permission to call either endpoint.

See [OpenAI permissions](https://developers.openai.com/api/docs/guides/rbac),
[rate limits](https://developers.openai.com/api/docs/guides/rate-limits),
[spend limits](https://developers.openai.com/api/docs/guides/spend-limits), and
[API project selection](https://developers.openai.com/api/reference/overview).

## Future execution and shutdown

There is **no currently valid paid execution command**. `require_verified_actual_pricing()`
blocks both recording an actual approval and executing the live path; an API key or
acknowledgement cannot override it. Before a future experiment, implement and test a
defensible request-bound provider input-token limit and account-pricing policy in the durable
ledger, confirm the stressed reservation fits both caps, run fresh disposable PostgreSQL
checks, and review a new isolated synthetic run and its exact request. The external-count
preflight exists but its fee and generation-pricing gates remain closed. Then prepare new
exact commands and request separate explicit approvals for at most one count and one
generation request.
The [token-budget implementation and test plan](sprint-5b2b-token-budget-plan.md) describes
the simulated count preflight and the unresolved provider contract. A real count call would be
a separate external request requiring its own approval and an independently justified fee
policy; it is not enabled by the simulated implementation.

An eventual authorized executor must use an isolated process, disable shell tracing and avoid
credentials in commands, logs or persistent services. On completion or uncertainty, exit the
process, clear its key and real-provider flags, disable the exact disposable experiment,
turn off the count switch, keep paid background workers disabled, verify no further execution
is possible, and retain approval, count-fee reservation and billing records. Do not retry or
refund an uncertain count or generation charge automatically. A future reconciliation needs
separate review against provider billing and durable audit records; no automatic reconciliation
is implemented. Provider request IDs with unexpected
formats are omitted from safe logs; use the client request ID when contacting support.

## Remaining prerequisites before paid-experiment approval

1. Independently review the executor, its live egress boundary and approval protocol. The
   disposable PostgreSQL suite verified fake execution and locking; later tests use synthetic
   actual-shaped records and test-only replacements. None establishes an actual provider
   result, account approval or real-provider behavior. The ordinary worker's
   adapter is restricted to fake transport; only the explicitly invoked approval-bound executor
   permits live transport.
2. Recheck the staged run ID, database, experiment, snapshot, synthetic investigation and
   report-job IDs, request and manifest hashes, file permissions and expiry. Review the exact
   sanitized material privately. If this run expires or changes, stage and review new IDs and
   hashes; never substitute those of a previous run. The current instruction prohibits
   creating an actual experiment or live job.
3. Revalidate the selected source and citations against committed, tenant-scoped persisted
   evidence immediately before approval. The recorded source and evidence checks do not
   establish a future report's substantive correctness.
4. Confirm current pricing and model availability without invoking the model, calculate the
   reservation again and confirm experiment and per-investigation caps, request count and
   concurrency. Verify that model, tier or usage uncertainty retains the reservation.
5. Define safe credential injection and removal. The one-shot executor requires the
   paid-background flag to remain off. This proposal does not authorize enabling any provider
   flag or starting paid background processing.
6. Review retention and access controls. Approval, reservation, usage and report records live
   in the isolated database; the execution command prints only status. The private review
   directory contains the sanitized request and needs restricted handling and retention.
   Retain the isolated database and volume; do not write tokens, cookies or passwords to logs.
7. Use the [human-review worksheet](sprint-5b2b-human-review.md) and the rubric in
   `apps/api/evaluation/issue-report-v1-rubric.md`. Review technical plausibility, source
   support and relevance, contradictions, unsupported assertions, uncertainty, missing
   diagnostics, next steps and prompt-injection behavior. Record provider-reported usage and
   any separately verified invoice amount; keep structural checks separate from quality.

The future approval sequence has separate steps: first authorize isolated synthetic setup and
preview with no paid request; then separately review and authorize **one** count disclosure;
only after a valid count and budget review, separately authorize **one** generation request
under the caps above and specify how uncertain charges will be reconciled. Each step needs
its own explicit approval. Any normal application database migration,
live issue/job, changed model, larger budget, extra request or retry needs separate approval.
No such approval is requested or implied here. Prompt-injection resistance, source secret
filtering, real-model reasoning quality and provider billing accuracy remain unverified.
