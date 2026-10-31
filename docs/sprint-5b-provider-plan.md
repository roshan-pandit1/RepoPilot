# Sprint 5B1: real-provider foundation

**Status: VERIFIED LOCALLY for the mock-transport foundation.** The user reported 317
passing tests in the selected disposable PostgreSQL suite, including the gated actual-mode
fake-transport and reservation race tests, as well as a successful 0010 upgrade and drift
check. No real inference, external token-counting endpoint, paid embedding call,
normal-database migration, or live report request has been executed. Actual provider behavior
and real-model reasoning remain unverified.

## Provider and configuration

The existing report outbox and lease-fenced worker remain the orchestration path. An existing
job is not reopened or reprocessed. New report jobs choose a provider from server configuration
when the job is created, and real selection is persisted against the job and tenant.
Client-supplied provider fields do not select a provider.

Defaults are `INVESTIGATION_PROVIDER=mock`, `INVESTIGATION_REAL_ENABLED=false`,
`INVESTIGATION_PAID_BACKGROUND_ENABLED=false`, an empty
`INVESTIGATION_EXPERIMENT_ID`, and an empty `INVESTIGATION_OPENAI_API_KEY`.
All of the provider selection, real-generation gate, paid-background gate, credentials,
and a canonical UUID identifying an enabled eligible tenant experiment must be present
before a real operation can proceed. An API key alone does not enable generation. Credentials
are server-side `SecretStr` values and must not be stored in the experiment or printed.
Experiments are administrator-managed database records, not a browser-controlled API.
There is currently no experiment-management UI or automated billing reconciliation.

The only supported paid model is `gpt-5.6-terra`; the mock remains
`deterministic-v1`. The adapter sends a Responses API request with application-controlled
instructions separate from the untrusted bounded input, strict JSON-schema output,
`store: false`, truncation disabled and no tools. The response and request are byte-bounded,
network timeouts are finite, redirects and environment proxies are disabled, and the adapter
performs no automatic retries. Provider errors are reduced to safe error codes. The existing
server validator checks every proposed chunk, snapshot, commit and inclusive line range against
persisted authorized evidence. An empty-evidence request must return no hypotheses and must
state missing evidence. Output is reviewed again on read, with citations reconstructed from
the application's evidence rather than accepted from the model.

The API and dashboard distinguish mock from real reports. The mock label remains
**MOCK REPORT — DEMONSTRATION ONLY**. Real reports are labeled for human review and are
not presented as verified diagnoses.

## Durable budget and failure behavior

Migration `0010` adds tenant-bound experiment, provider-selection, usage-reservation and real
report tables; it does not alter existing mock reports. Money is recorded as integer
millionths of a USD. A PostgreSQL transaction locks the report job and experiment and reserves
capacity before any network call. It checks the experiment and per-investigation limits and
active concurrency and a maximum request count under the experiment row lock. Actual mode refuses non-PostgreSQL storage.
Simulated and actual reservations are distinct, and simulated execution requires an injected
`httpx.MockTransport`; it cannot use the network.

Only one reservation can exist per report job. The current model's documented context window
is used as the conservative input bound: **1,050,000 tokens**, despite the much smaller
48,000-byte request limit. This avoids treating an approximate local tokenizer as an enforced
input-token limit. Output is at most **2,048 tokens**, including reasoning tokens. Other
configured input limits, output limits, model identities, or pricing assumptions fail closed.
The reservation stores the model, token bounds and rate policy so later reconciliation
does not silently use a changed process configuration.

Published pricing reviewed on 2026-10-30 is $2/million input tokens and $12/million output
tokens for this model. For a conservative reservation, RepoPilot applies the documented
long-context multipliers (2× input and 1.5× output), a 1.25× input cache-write factor,
and an additional 10% regional allowance, with no caching discount. This gives
5.5 microdollars/input token and 19.8 microdollars/output token. One maximum reservation is
therefore **$5.815551**: `1,050,000 × $0.0000055 + 2,048 × $0.0000198`, rounded up
to the next microdollar. This deliberately over-reserves and is not an estimate of average use.
It does not guarantee protection from provider price changes, other fees or billing discrepancies.
An experiment requires a recorded pricing review less than 24 hours old and an expiry no more
than 24 hours after that review. An operator must actually review provider terms; a timestamp
is not proof that this happened.

The worker marks a reservation `sent` under a valid lease before leaving the transaction.
A stale worker cannot send from a reservation that a new lease took over. After a response
with valid usage, the ledger records token counts and conservatively accounted cost; it does
not claim an actual provider invoice amount. The report's cost field remains null unless
actual cost is known. Timeouts, missing usage, malformed envelopes, and crashes after the
send marker retain the full reservation. A response identifying a model other than the
configured alias also retains the full reservation, since its billing policy is not known.
They are not automatically refunded or retried.
Uncertain reservations also occupy concurrency capacity; operator investigation and a
separately approved reconciliation process are needed before releasing funds. No automatic
manual-reconciliation tool is provided here.

A crash before the send marker can transfer the unused reservation to a new valid lease.
A crash after sending or after accounting but before report publication does not replay the
model call; the operation may require manual resolution. Duplicate deliveries cannot publish
two reports through the lease-fenced worker. Authorization and evidence are rechecked before
the call and before publication, without keeping a database transaction open during network
requests. Revocation after a call prevents publication but does not erase its accounting.
Revocation racing with an in-flight provider request cannot recall already transmitted data
or prevent the provider from finishing and billing that request.

## Security limits

GitHub issues, comments, labels, paths and source are untrusted. Inputs have explicit
character and evidence budgets; source literals and comments are omitted where the sanitizer
can parse them, and known runtime secrets are checked. This is best-effort filtering, not a
complete secret scanner. The provider receives no filesystem, shell, repository-write, network
or tool capability. Strict output format and citation validation limit structurally invalid
answers; neither can prove that natural-language claims are true or that a real model will
resist prompt injection. A valid citation does not prove that it supports the claim. Human
review remains necessary. `store: false` is not a guarantee of zero provider retention;
review the provider's current data controls and the repository's disclosure requirements.

## Proposed experiment — not authorized or executed

Candidate: one Responses API request to `gpt-5.6-terra` using the existing synthetic
`signature_exact` fixture in `apps/api/evaluation/issue-report-v1.json`, grounded to commit
`30705da4c044192cab4ac207e253ab8e8a1bd100`. Use a disposable evaluation environment and
review the input projection before transmission. Set a $10 experiment cap, a $6
per-investigation cap, concurrency one, maximum request count one, the full documented input-window reservation and
2,048 output tokens; the current per-request reservation is $5.815551. Send at most one
request; no automatic retry after a potentially billed request. A timeout or unknown usage
ends the experiment with the reservation held. The previously missed `signature_natural`
case is a possible later experiment requiring its own request and approval.

Before asking to run this experiment: complete disposable PostgreSQL and migration checks,
review the model's current availability, data-handling terms and pricing, check whether the
model alias and its context/pricing can be safely pinned or otherwise bounded, inspect the
selected sanitized source, and build/review an isolated real-provider evaluation harness.
The current 4F runner is mock-only and is not a real-model experiment runner. Obtain explicit
approval for any normal-database migration, creation of an actual experiment, credentials,
provider enablement and the specific paid request. No approval to create an experiment or
invoke the provider is implied by this plan.

For human review, use `apps/api/evaluation/issue-report-v1-rubric.md`: assess technical
plausibility, cited support, contradictions, missing diagnostics, next steps and uncertainty.
Do not call a mock result evidence of real diagnostic accuracy.

Provider references reviewed: [Responses structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses),
[GPT-5.6 Terra model and pricing](https://developers.openai.com/api/docs/models/gpt-5.6-terra),
[token counting](https://developers.openai.com/api/docs/guides/token-counting), and
[API data controls](https://developers.openai.com/api/docs/guides/your-data).
