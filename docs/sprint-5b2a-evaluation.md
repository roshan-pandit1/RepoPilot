# Sprint 5B2A: isolated fake-provider evaluation

The evaluation runs only against a newly created, uniquely named disposable PostgreSQL
database. It uses a local Git object, a synthetic authorized GitHub client, the existing
keyword retrieval and report worker, and `httpx.MockTransport`. The evaluation command
has no paid mode. It does not contact GitHub or the model provider, enable paid background
generation, modify the normal application database, or reindex a live repository.

The source is dataset `issue-report-v1`, SHA-256
`416cbf9e46b9399cf78d118f581a882d16cf512da439d352d3af29674c447bf6`, case
`signature_exact`, commit `30705da4c044192cab4ac207e253ab8e8a1bd100`, tree
`beac4e3116133a810f679761e17a7441fa77c2d7`. Its reviewed label is
`apps/api/app/modules/github/security.py`, `valid_signature`, inclusive lines 6–8.
The evaluator checks the Git tree, blob, label and source chunk before writing a deliberately
partial synthetic snapshot containing only that source file to the disposable database.
It marks the omitted eligible files as skipped. Retrieval results from this partial fixture
are a workflow check, not a retrieval-quality benchmark. No label is rewritten.

The harness uses the existing issue, evidence and report contracts and invokes the existing
leased report worker directly. The fake provider response is constructed from a verified
evidence reference and is explicitly synthetic. Server-side report and citation validation,
tenant-scoped reads, a simulated durable reservation, usage reconciliation and duplicate
delivery are checked. The response is **not AI reasoning**. The host regression suite covers
refusal, incomplete output, malformed JSON, wrong model or tier, unexpected cache policy,
missing or excessive usage, timeout and connection failure, crash recovery, concurrency,
budget exhaustion, revocation, foreign citations and unsupported hypotheses.

The evaluator's fake HTTP transport has no fallback to a real provider. A Python socket fence
blocks DNS and outbound connections except the dedicated local database port; local Git is
configured to refuse network protocols and lazy fetches. This is defense in depth for the
reviewed harness, not an operating-system sandbox against arbitrary native code or new
subprocesses. No repository source is executed. The input-preview artifact contains only
field names, sizes, selected citation metadata and a hash of the exact serialized request
projection; it does not duplicate issue or source text, credentials or cookies. Hashes are
identifiers, not secrecy guarantees for guessable input.

## Run and artifacts

```bash
cd "/Volumes/Samsung SSD/Project/RepoPilot"
bash apps/api/evaluation/run-5b2a-disposable.sh
```

The script refuses an unavailable Docker image, creates a new container and database with a
random run ID, confirms the database target and empty schema, runs the selected PostgreSQL
suite without skips, checks the security fixture, upgrades to 0010 and checks drift, then
executes the fake-provider evaluation. It retains the new container and volume. The separately
approved committed-source 4F benchmark remains excluded. Run-specific artifacts share the
database suffix and are never overwritten:

- `apps/api/evaluation/5b2a-<run-id>.log` — sanitized verification output.
- `5b2a-<run-id>-pytest.json` — test counts and database/run identity.
- `5b2a-<run-id>-preview.json` — exact-request hash, fields, sizes and budgets.
- `5b2a-<run-id>.json` and `.md` — evidence, grounding, ledger and provenance results.

The machine report includes code fingerprints because the tested working tree can contain
uncommitted changes. The preview is a description of the actual fake request; it is not a
verified token count. The full input-window bound is reserved instead of relying on an
approximate tokenizer. Local Git verification does not by itself verify GitHub-hosted links.

The retained host run `4f6d42946ddad6d4` used disposable database
`repopilot_5b2a_4f6d42946ddad6d4`, passed 338 selected PostgreSQL tests with no skips
and 33/33 synthetic adversarial checks, and reached Alembic 0010 without drift. Its
partial snapshot supplied two evidence items; one of one report citations passed grounding.
The report records one fake request, one worker attempt, and a simulated $5.815551
reservation. It does not measure actual model reasoning, provider behavior or invoice cost.

## Pricing audit — 2026-10-31

[OpenAI's GPT-5.6 Terra documentation](https://developers.openai.com/api/docs/models/gpt-5.6-terra)
lists a 1,050,000-token context window, $2 per million input tokens, $12 per million output
tokens, and multipliers of 2× input and 1.5× output for input above 272,000 tokens.
The [prompt-caching documentation](https://developers.openai.com/api/docs/guides/prompt-caching)
specifies a 1.25× input write rate for the 30-minute setting and a higher 2.5× rate for the
12-hour setting. The adapter explicitly requests the standard service tier and 30-minute
cache policy. It holds the full reservation if the returned model, service tier, or reported
cache lifetime contradicts the assumed policy. Output limits include reasoning tokens
([token-counting documentation](https://developers.openai.com/api/docs/guides/token-counting)).

For one request with at most 2,048 output tokens, reserving the *entire* documented input
window, the maximum 30-minute cache-write rate, long-context multipliers and an additional
10% regional allowance gives:

```text
input:  1,050,000 × $2/1,000,000 × 2 × 1.25 × 1.10 = $5.775000
output:     2,048 × $12/1,000,000 × 1.5 × 1.10     = $0.0405504
total rounded up to microdollars                      = $5.815551
```

This is an intentionally conservative reservation, not an estimate of the actual bill. The
proposed per-investigation cap is $6 and the experiment cap is $10. The reservation counts
the full context window *plus* the output limit, so it overstates a request constrained by
the combined context. The experiment allows one request and no automatic retry after a send
marker. Unknown or inconsistent usage keeps the full reservation. The local ledger cannot
guarantee the provider's eventual invoice, detect all pricing changes, or prevent an
unexpected external billing discrepancy. Review current terms and model identity again
before any future paid use.

Before this audit, the adapter omitted `service_tier`, allowing a project-configured tier
to affect the rate. The correction explicitly requests `default`; a missing or different
returned tier is treated as an uncertain billing outcome. The 30-minute cache lifetime is
also explicit. Refusals and incomplete responses now receive separate safe failure codes
when usable billing metadata is present; untrusted response envelopes with duplicate keys
or inconsistent pricing metadata retain the full reservation.

## Future approval checklist — not an authorization

Review the exact run-specific preview and a separate real-execution design before approving:

1. Provider/model: OpenAI Responses, `gpt-5.6-terra`; confirm the alias and returned
   model identity, account access and current data-handling policy.
2. Pricing: the 2026-10-31 standard-tier, 30-minute policy above; recheck it immediately
   before the experiment and record who reviewed it.
3. Dataset: `signature_exact`, dataset hash and immutable commit listed above.
4. Database: a new, isolated, disposable PostgreSQL database at revision 0010; no normal
   application database or live GitHub issue.
5. At most **one** provider request and **zero** automatic retries.
6. Full 1,050,000-token input-window reservation, 2,048 maximum output tokens, and
   the existing 48,000-byte request-body bound.
7. Durable per-request reservation: **$5.815551** under the verified rate assumptions.
8. Hard local experiment cap **$10**, per-investigation cap **$6**, concurrency one and
   request-count limit one; provider-side billing discrepancies remain possible.
9. Treat timeouts, disconnects, unexpected identities or tier, and unknown usage as
   uncertain; retain the full reservation and require explicit reconciliation.
10. Enable the real provider and paid background gate only in an expressly approved,
    isolated execution process with an enabled tenant experiment and server-side key;
    disable both gates and remove the temporary key after the operation. The current
    evaluation runner has no real execution mode.
11. Review the sanitized issue, selected source excerpt and exact outbound projection:
    those fields, evidence metadata and commit-pinned citation metadata would leave the
    machine. Secret screening is incomplete and `store: false` is not zero retention.
12. Retain run-ID-correlated database, report, preview, usage ledger and sanitized logs;
    do not store credentials or raw prompts in the output artifacts.
13. Use the worksheet below and the existing
    `apps/api/evaluation/issue-report-v1-rubric.md` for human review.

An isolated paid-execution entry point and its exact reviewed preview still need to be built
and reviewed after the fake harness succeeds. Nothing in this document authorizes a paid
request or a normal-database migration.

## Human-review worksheet

Record the experiment ID, reviewer, timestamp, dataset/commit/snapshot, provider/model,
actual reported token usage and any later verified invoice amount. Keep structural checks
separate from substantive judgments.

| Review dimension | Observation and cited evidence | Judgment / uncertainty |
| --- | --- | --- |
| Citation validity and exact lines | | |
| Technical plausibility | | |
| Root-cause relevance | | |
| Unsupported assertions | | |
| Appropriate uncertainty | | |
| Missing diagnostic information | | |
| Suggested diagnostic steps | | |
| Prompt-injection observations | | |
| Actual input/output tokens and verified cost, if known | | |

Mark unassessable items as such, preserve rationales, and adjudicate disagreements. Do not
assign a real-model quality score to the deterministic fake output.
