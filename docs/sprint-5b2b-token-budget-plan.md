# Request-bound input-token budget: implementation and test plan

Status: **fake-only counting foundation verified locally on disposable PostgreSQL**.
Run `e1593aaca7524a85` passed 309 selected tests without skips, the 33-case adversarial
fixture, Ruff, and migration `0012` drift checks; its 131-file source fingerprint matched the
then-current source. Sprint 5B2D subsequently added tests and extended the disposable runner;
new run `383e0af929ee80d2` passed **324 tests, zero skips**, the 33-case adversarial fixture,
Ruff and Alembic `0012` without drift. Its source fingerprint matched and exit status was 0.
Sprint 5B2E adds an external-count preflight and migration `0013`. Disposable PostgreSQL
run `8d8ccdd6c8a29bc9` passed **384 selected tests with zero skips**, 33/33 adversarial
checks, Ruff and Alembic `0013` without drift; its 133-file fingerprint matched before and
after, and its recorded exit status was 0. Both actual-pricing gates remain closed.
See [verification.md](verification.md) for the scope and evidence. Paid execution remains
blocked. No real token-count or generation request is authorized by this document.

## Finding

The current adapter caps the canonical request body at 8,192 bytes, including instructions
and output schema. The existing PostgreSQL ledger still reserves for 1,050,000 input and at
most 2,048 output tokens. Bytes are not an enforceable billed-token limit: provider framing,
schema and model processing can add tokens. The current full-window $5.815551 reservation
exceeds the $6 per-investigation cap under the documented two-*additional*-uplift stress
scenario. `require_verified_actual_pricing()` therefore continues to block actual approval
and live execution.

OpenAI's [input-token counting guide](https://developers.openai.com/api/docs/guides/token-counting)
describes a count that includes formatting overhead and notes that schemas are difficult to
count locally. The [count API reference](https://developers.openai.com/api/reference/resources/responses/subresources/input_tokens/methods/count)
supports model, instructions, input and structured-output configuration. Its documented
response contains `object` and `input_tokens`; it does not provide a resolved model revision.
The current [model page](https://developers.openai.com/api/docs/models/gpt-5.6-terra) lists
`gpt-5.6-terra` under snapshots but does not identify a separate dated snapshot on that page.
The documentation reviewed on 2026-11-01 does not establish that a count for this exact
request is an immutable provider-enforced upper billing limit across a subsequent generation.

The count endpoint is a **separate external API request** that sends the selected input and
schema to the provider. It would add an invocation to any proposed one-generation-request
experiment. Its account-specific billing and retention terms have not been verified. Neither
the endpoint nor a model-list endpoint may be called under the current instructions.

## Smallest candidate approach

If a separately authorized count request is acceptable, extend the existing adapter and
approval/ledger workflow with a request-bound provider count. Do not reduce the reservation
or unblock actual execution until the following contract questions are resolved:

1. Confirm project access, count-endpoint fees and retention, the exact generation model and
   a stable model/tokenization identity across counting and generation. Confirm how the
   provider handles framing, hidden tokens and schema. If these cannot be bounded, keep the
   full-window reservation and fail closed under the existing $6 cap.
2. Build the count payload from the **same canonical generation request**, not from issue
   text alone. Include identical model, instructions, input and `text.format` schema, plus
   every token-affecting option supported by the count endpoint. The current generation
   body also contains `max_output_tokens`, `service_tier`, `store` and
   `prompt_cache_options`; the count reference does not list those as top-level count
   parameters. Verify the exact mapping and confirm with the provider that omitted
   generation-only fields cannot increase billed input. Reject unknown or unsupported
   token-affecting fields rather than silently dropping them. Never add tools, conversation
   history, external files or unrestricted source.
3. Bind both the **full generation-body hash** and the **count-projection hash** to the
   synthetic job, tenant, snapshot, source commit, model identity, account/project identity,
   schema, pricing policy and freshness window. Validate a bounded, non-negative integer
   count and the response shape; retain safe request IDs and hashes, not source, credentials
   or raw prompts. Treat a missing, malformed, stale, changed or unverifiable count as a
   hard stop. A caller-supplied number or bytes/4 estimate is not provider evidence.
4. Obtain a separately scoped one-use disclosure authorization for the count call and
   account for any possible count charge before sending it. Mark that call durably as sent
   before network I/O; do not hold a database transaction open over the call. A timeout or
   crash after the marker has an uncertain outcome and must not trigger an automatic retry.
   A count approval is not approval for generation. If a provider fee cannot be bounded,
   block the count call too.
5. Only after a verified count and documented upper-bound policy exist, derive a configured
   maximum input-token budget at least as large as the verified bound, with justified
   overhead. Recheck the exact generation request, tenant, access and approval immediately
   before reserving and sending. A measured count plus an arbitrary buffer is not by itself
   proof of a hard bound, and `max_output_tokens` limits output, not input. If the provider
   cannot guarantee the count-to-generation relationship or provide a hard input cap, retain
   the current full-context reservation and keep the experiment blocked.
6. Reuse the existing PostgreSQL ledger: under its job/experiment locks, reserve the
   **stress-adjusted** worst case for the verified input-token maximum and 2,048 output
   tokens, include any separately bounded count charge in the applicable caps, and reject
   either cap or concurrency exhaustion. Bind the approved policy and token bound to the
   reservation; keep approval consumption and the generation send marker atomic. Preserve
   full reservations on uncertain billing and never automatically repeat a possible send.
   Returned usage above the bound or an unexpected model/tier is a failure and discrepancy;
   it cannot retroactively prevent an external overcharge.

The existing approval and reservation tables each have a uniqueness constraint on the report
job. Additive migration `0012` introduces a separate tenant/job-bound **simulated-only** count
authorization and result. It does not add a billing ledger, create a real approval, or migrate
the application database. The existing generation ledger remains authoritative. Test migration
`0012` only in disposable databases unless the user separately approves an application migration.

## Implemented fake-only foundation

`app.evaluation.token_counting` projects the approved canonical generation body into the
documented `POST /v1/responses/input_tokens` shape: the exact model, instructions, input,
structured-output `text.format`, and disabled truncation. The projection rejects unknown or
unsupported features, including tools, conversation history, images and additional metadata.
`max_output_tokens`, service tier, storage and cache settings are generation-only in the
reviewed count-reference field list; they remain bound by the full generation-body hash. The
two endpoint payloads are intentionally different, and no provider guarantee about omitted
fields or the later billed input has been established. A real future count would disclose the
same synthetic issue, sanitized source excerpts and metadata described in the approval packet,
along with application instructions and schema, to an external provider.

The fake approval requires an explicit simulated disclosure acknowledgement, isolated test
configuration, the reviewed private request and manifest, a synthetic account and project,
and an expiry no later than 15 minutes or the session/experiment expiry. It persists hashes
and identifiers, not raw request text or credentials. Its binding includes the separate
generation and count-payload SHA-256 values, manifest and policy revision, model/provider,
fixture/commit, tenant, repository, investigation/job, snapshot, synthetic account/project,
input/output limits and expiry. Composite database keys enforce the job and tenant association.
Only `mode='simulated'` is permitted by the `0012` table. Checkpoint 5B2E adds a separate,
disabled external-count path and table as described below; it does not promote these records.

The count is marked `sent` under database locks before the fake transport runs. Success stores
a strictly shaped, nonnegative integer result; a timeout, invalid response or other uncertain
outcome retains an `uncertain` or interrupted `sent` state and cannot be automatically replayed.
A count exceeding the locally selected threshold is retained but rejected for generation
preflight. The adapter accepts only an injected `httpx.MockTransport`, disallows redirects,
limits response size and uses the existing Python network fence. The fence is a test control,
not an operating-system sandbox. The two synthetic organization/project headers are fixture
values; they do not establish a real credential's project identity.

When a simulated generation explicitly selects a fake count, preflight checks its identities,
expiry, threshold and current local access. The send-marker transaction rechecks the count,
the reconstructed request and access under locks before consuming the **separate** simulated
generation approval. The existing worker still validates the report, citations and access
before publication. An authorization change after the transaction and before network I/O
cannot be ruled out by holding locks across a network call; no real transport is enabled.
Counting alone neither creates nor consumes a generation approval, and it does not reserve,
refund, or reduce any amount in the generation ledger.

The default synthetic count threshold is 16,384 input tokens, a test parameter rather than a
verified provider maximum. The full-window ledger reservation remains **$5.815551** for
1,050,000 input and 2,048 output tokens. The count endpoint's actual account-specific price,
retention and any billable failure policy remain **unknown**; no claim is made that counting
is free or covered by the generation reservation. Future real counting requires its own
separate explicit disclosure/spending approval and a defensible count-fee reservation policy.
Future generation additionally requires stable model identity, proven count-to-generation
overhead and a provider-compatible hard bound or other justified conservative policy. The
reviewed Responses request documents an output-token limit, not a provider-enforced maximum
input-token parameter suitable for this body. An arbitrary local cushion cannot guarantee the
external invoice. The actual-pricing gate remains unconditionally blocked.

For scale only, an independently verified 16,384-token input bound and 2,048 output tokens
would produce a $0.130663 base reservation at the existing conservative rates and $0.158103
after two additional hypothetical 10% stress uplifts, rounded up. This excludes any unknown
count-endpoint or account-specific charges and is **not** a verified or authorized budget.
Local caps cannot guarantee the provider invoice or prevent all provider-side discrepancies.

## Sprint 5B2D: proposed fail-closed policy

**This section specifies a future policy; it does not enable or implement real counting or
reduced reservations.** The associated fake-transport regression is verified locally; this is
not verification of a real-provider spending ceiling. At checkpoint 5B2D, `execute_fake`
accepted a count only when explicitly supplied, `execute_live` had no count argument, and the
generation adapter did not set organization/project headers. Checkpoint 5B2E changes the live
preflight as described below; the actual-pricing gate still unconditionally blocks execution.

Before implementing a smaller reservation, require all of the following, with unknown or
ambiguous values treated as a hard stop:

1. Establish the exact organization, project, model identity, applicable standard-tier rate
   card, processing endpoint, cache treatment, additional fees, any fee stacking, and pricing
   freshness from an independent account-specific source. The prospective credential must be
   demonstrably tied to the same approved project for counting and generation. Public model
   availability is not project access. No raw credential or private identifier belongs in the
   approval packet, logs or tracked files.
2. Obtain separate explicit authorization and a bounded, durably accounted count-call charge
   **before** any count request. Bind that one-use authorization and resulting verified count
   to the tenant, job, investigation, snapshot, commit, fixture, exact model, project,
   pricing revision, expiry, disclosure manifest, canonical generation-body hash and
   deterministic count-projection hash. A count approval cannot authorize generation.
3. Require a nonexpired, noninvalidated, nonnegative integer provider count `C` from that
   operation. Select a separately approved maximum `B` only when the provider contract and
   independent review justify that `B` covers the eventual billed generation input, including
   model/framing/schema overhead and any approved allowance `delta`; require `C + delta <= B`.
   An arbitrary buffer, a byte count, a fake response, or the requested model alias by itself
   is not proof. If identity stability or the count-to-generation relationship cannot be
   justified, keep the full-window reservation and reject the real operation.
4. Require the exact reviewed canonical generation bytes and hash to match at the generation
   send marker. This binds model, instructions, issue/input, source excerpts and metadata,
   JSON schema, cache options, standard tier, `truncation='disabled'`, `store=false`, and
   `max_output_tokens=2048`. Reject unsupported or newly introduced request features rather
   than silently projecting them away. Revalidate current tenant/source authorization and
   the selected snapshot/commit; require a distinct unconsumed generation approval.
5. Before a possible generation send, have the existing PostgreSQL ledger atomically reserve
   the verified worst-case charge for `B` input tokens, the full output-token limit including
   reasoning and non-visible output, all applicable bounded fees and the approved stress
   policy. Account for the earlier count charge separately without double counting; enforce
   both experiment and investigation caps, one request and concurrency one. Round upward in
   integer microdollars. Lock in the established order; consume the generation approval and
   commit its send marker with the reservation. A timeout, crash after a send marker, unknown
   usage or mismatched billing metadata retains the applicable conservative reservation and
   triggers no automatic retry or refund.

The provider documentation does not establish a suitable request parameter that enforces
`B` as an input-token ceiling on this Responses request. Any eventual local check is therefore
a preflight control, not a provider-enforced invoice cap. Usage reconciliation after a response
cannot prevent an already-incurred discrepancy. Local/database administrators and provider-side
pricing or billing behavior remain outside the ledger's guarantees. The 5B2E count-record and
fee-accounting code still requires independent security review and disposable PostgreSQL tests.
Any real count, real generation, reduced reservation or application migration requires separate
explicit user approval; none is authorized now.

The offline placeholder template was reconstructed from commit
`30705da4c044192cab4ac207e253ab8e8a1bd100`: its canonical body is **3,816 bytes**, including
445 instruction bytes, a 1,215-byte schema and both sanitized evidence excerpts
(`apps/api/app/modules/github/security.py`, lines 6–8 and 1–5). It uses disabled truncation and
2,048 maximum output tokens. The placeholder SHA-256
`2448dd78bafd00dad82a7a4e39addafb6b0309d5bffa3e6174367119abff019c` is not an approval or a
fresh staged request. The 16,384-input-token threshold is a plausible **candidate for testing**,
with no evidence removed, but neither the actual count nor provider overhead has been measured.
Likewise, the output allowance includes reasoning but has not been shown sufficient for a real
structured report. A different input/output limit or request requires a new identity and review.

## Sprint 5B2E: separately authorized provider-count integration

**VERIFIED LOCALLY — FAKE-TRANSPORT INTEGRATION SCOPE.** Migration `0013` adds `investigation_provider_token_counts` without
changing the `0012` simulated table or existing data. The external-only record represents a
separate count authorization and progresses from `pending` to `sent`, then `verified` or
`uncertain`; it can be invalidated or consumed by a generation send marker. Expiry is also
checked at preflight. A simulated count cannot be promoted: count authorization rejects a
preexisting simulated count, and the actual-generation validator queries only the external
table and rejects coexisting simulated records. No external authorization or provider result
was created for this checkpoint. External count authorization and sending require a
dedicated PostgreSQL database; SQLite cannot satisfy the actual-mode durability gate.

The external count authorization is bound to the tenant, report job, investigation,
repository, snapshot, commit, fixture, model/provider, hashed organization/project, canonical
generation request, count projection, manifest, pricing and fee revisions, service tier,
cache TTL, input/output limits and expiry. The count sender consumes its separate one-use
authorization by committing `sent` before network I/O. It accepts no injected mock transport
for external provenance; the simulated adapter uses only `MockTransport` and shares the
bounded response parser. A timeout, crash or malformed response leaves an uncertain or sent
state, retains the count fee and cannot be automatically retried. The count fee is included in
the **existing** experiment and investigation ledger totals under the experiment lock; there
is no independent spending pool. No transaction remains open during provider I/O.

The live executor now requires the external count ID and matching server-side organization and
project. It rechecks the count, source access and exact generation bytes at the send marker;
the verified count, separate generation approval and generation reservation are consumed or
marked sent atomically. An ordinary worker cannot bypass the approval-bound model even with
an injected mock transport. The one-shot executor has a separate configuration gate that
requires the paid-background-worker switch to remain off. The count sender also requires
real generation and paid background workers to be off. The full-window **$5.815551** generation reservation is unchanged;
the external count's fee is separately reserved and counted against the same caps. The current
two-uplift stress check makes even the full-window reservation exceed the proposed $6 cap.

`require_verified_count_pricing()` and `require_verified_actual_pricing()` both unconditionally
fail; the external-count switch is false by default. Project model access, count fees, fee
stacking, exact provider identity and a defensible count-to-generation input bound remain
unverified. A separate explicit approval is needed for a future external count and another
for generation. A provider count is not a provider-enforced invoice limit. Unknown usage or
fees remain reserved pending a separately reviewed reconciliation; no automatic refund or
retry is performed. The historical staged experiment, IDs and disclosure hashes remain expired
and invalid; a fresh isolated review is required if later authorized.

The integration tests use synthetic, actual-shaped records in a disposable test database and
test-local replacements for pricing and HTTP transport; no configuration flag creates those
replacements. They exercise the actual count approval/send and generation-marker code with
`MockTransport`, including an uncertain fake count fee and rejected replay. These fixtures
are not actual provider counts, live approvals or evidence of provider billing. The first
disposable 5B2E host run passed 373 tests but predates the later executor gate, PostgreSQL
guard and expanded sender tests. The updated source passed the subsequent 384-test host run
recorded in [verification.md](verification.md#sprint-5b2e--provider-count-and-generation-preflight).

## Focused implementation tests

- **Projection and bounds:** fake count request includes the exact instructions, issue,
  evidence, structured schema and all supported token-affecting settings; mismatch or an
  unknown field fails before I/O. Test changed source, prompt, schema, model, snapshot,
  project, request/manifest hashes, token limit, stale count and expired approvals.
- **Malformed count and privacy:** fake missing, non-integer, negative, excessive, duplicate
  and malformed values; timeout, refusal, connection failure and unexpected response
  metadata. Assert no prompt, source, credential or cookie in logs or durable evidence.
- **Budget and concurrency:** on disposable PostgreSQL, race two count claims and two
  generation claims; prove one authorized count and at most one generation. Verify locked
  stress-adjusted reservations respect both caps, including a separately bounded count fee;
  unknown pricing, missing proof, exhausted budgets and cross-tenant/snapshot data fail closed.
- **Crash and replay:** simulate interruption before and after each send marker, lease expiry,
  duplicate delivery and changed limits. Never automatically resend an uncertain external
  request, publish a partial report or release uncertain charges.
- **Security and compatibility:** exercise existing adversarial fixtures, citation grounding,
  revocation, mock reports and historical jobs. Fake transports and a network fence must
  prevent live provider access in test mode. Verify migrations, drift and regression tests on
  a fresh disposable database; never use the normal application database for destructive tests.

Only after those changes and tests are reviewed should a new synthetic fixture, disclosure
manifest, IDs, hashes and expiry be prepared under an explicitly scoped authorization. Any
real count request and any later generation require distinct, explicit user approval. The
model's reasoning quality and actual provider billing would remain unmeasured until a real,
separately authorized experiment and human review.
