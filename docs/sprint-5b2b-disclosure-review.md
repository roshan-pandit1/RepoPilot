# Sprint 5B2B: redacted synthetic disclosure review

This is a preparation record, not permission to disclose source or make a paid request.
The only source considered here is the `signature_exact` synthetic fixture at commit
`30705da4c044192cab4ac207e253ab8e8a1bd100`. The reconstructed template uses placeholder
identifiers; its request hash is **not** the hash of the staged request.

| Reviewed material | Identity and SHA-256 |
| --- | --- |
| Dataset | `416cbf9e46b9399cf78d118f581a882d16cf512da439d352d3af29674c447bf6` |
| `apps/api/app/modules/github/security.py`, complete committed 322-byte blob | Git blob `9d1ca57c87b5f6a7141baf3abb8c0a097d1dbae3`; SHA-256 `b49bb45a35edd38fc5bcbf010a692ba3453cc8ec97824c67b9fc1913095e5fcd` |
| Original lines 1–5, including line endings | 96 bytes; `47b45bc1ec79dafd217949051ed894e0d79bafd925a0075e84a6285444e7166d` |
| Original lines 6–8, including line endings | 226 bytes; `e45f500e3be82c8361cc1c268c01b4dab0f38131c6451d2f9409c82a7dc35dd7` |
| Sanitized model excerpt for lines 1–5 | 51 bytes; `6019d85f8bb86d1f2542a1deec81ae85e39d8d146857e050acda62281f680a72` |
| Sanitized model excerpt for lines 6–8 | 249 bytes; `bec83e08d9555d3527d64e7936f50406682b0b5e5ff9e1e31305763adc3ef293` |
| Application instructions in the template | 445 bytes; `92967e953d2a471714d98aa532e843f91f826f1b595a6c4223ac1d59e56cdd76` |
| Strict output JSON schema in the template | `01a5052e4d0525866c0a87edeab1c12fdb6f923e767bbe7d4e23655032da7f23` |
| Canonical template request / manifest | `2448dd78bafd00dad82a7a4e39addafb6b0309d5bffa3e6174367119abff019c` / `f8b62ef29ded70fa0177b02ebc1a0269358b211fb839fb81f418f4bf9ef2af1c` |

The original file consists of imports and a webhook-signature verification function; its
`secret` name is a function parameter, not a credential value. The model-bound excerpts are
separately sanitized, including source literals, comments, numbers and sensitive identifiers.
The synthetic issue is titled “valid_signature rejects a delivery”; its title is 34 UTF-8
bytes and its body is 84 bytes. Issue text is untrusted data, and the request has no issue
comments or labels. The request also contains the public repository name in commit-pinned
citations, synthetic repository/issue identifiers, snapshot/investigation and chunk IDs, line
ranges, issue dates, application instructions and the strict report schema. The report
schema asks for a summary, hypotheses, missing evidence, next steps and warnings.

The reconstructed template contains 3,816 canonical request bytes. Dividing bytes by four
gives 954 only as a rough heuristic; no exact tokenizer count or provider token-count request
was performed. The reservation uses the full model input window. The body explicitly requests
`gpt-5.6-terra`, `service_tier=default`, a 30-minute cache policy, `store=false`, disabled
truncation and at most 2,048 output tokens. It specifies no tools, browsing or API metadata.
The HTTP request sends a server-side Authorization header, content type and the synthetic
report-job UUID as `X-Client-Request-Id`; HTTPX also supplies standard transport headers.
The credential value is not part of the body or review artifacts. The provider and network
infrastructure can observe the request, headers and network metadata, and provider-internal
processing cannot be inspected from this repository. `store=false` is not a zero-retention
guarantee.

The complete committed blob and reconstructed request were checked for recognizable OpenAI
and GitHub key patterns, private-key PEM headers, email addresses, credential headers and
the listed prompt-injection phrases; none matched. Source selection's existing sensitive-source
screen also passed. The small source file and synthetic issue were reviewed in context; no
credential values, cookies, unrelated source or apparent instruction attacks were identified.
The public GitHub account/repository name is disclosed as part of the source links. Pattern
screening is incomplete by nature and cannot prove that every secret, personal detail or
attack has been detected.

`app.evaluation.disclosure_screen.screen_exact` repeats the bounded checks for a staged
request and records only hashes, counts, metadata and matched ranges. It does not disclose the
source text, token values or request contents.

For disposable run `b3fa0088237c0c7a`, the independently reconstructed private request and
manifest have SHA-256 values
`9211ff97ef966d0d648d3d175a1808116c576e7cd80adee746fed82a8a2700b5` and
`87f82f93e7338fe567cd43270b163dc268ad2e47326da8968f78977da5a46b0b`, respectively.
Both match the saved synthetic-run artifact and committed-source reconstruction; the
private directory and file modes were verified. The request contains the two evidence ranges
above, synthetic chunk IDs, and the same issue/instructions/schema categories. The
known-pattern screen found zero matches in that request and source. Its synthetic experiment
expires at `2026-11-01T03:20:26.146556+00:00`; its synthetic session expires five minutes
later. Expiry requires a fresh run and a new exact-input review.

The eventual operator must privately inspect
the exact `request.json` and `manifest.json`, review their hashes and the actual synthetic
identifiers, confirm account pricing and retention, and explicitly authorize one invocation.
Both files are protected by mode `0600` inside a mode `0700` directory. The executor requires
explicit source-screening and account-pricing acknowledgements before recording a paid
approval. These acknowledgements are operator attestations, not independent proof of review.
Any modified source, request, manifest, evidence, snapshot or experiment requires a fresh
review. Source screening does not establish provider-side retention, account-specific pricing
or real-model behavior.

**Checkpoint 2B:** the exact staged request above is retained as historical evidence only.
The canonical body was 3,826 bytes; the new 8,192-byte body limit and blocked actual-pricing
state are included in the current disclosure manifest. Consequently the old manifest no
longer reconstructs under the current policy, even though the historical body hash itself has
not changed. Do not reuse its investigation, experiment, evidence or request identities for a
future paid approval. The recorded expiry is `2026-11-01T03:20:26.146556+00:00`; at
`2026-11-01T02:41:06Z` it had not yet expired. After expiry it must not be revived.
The experiment was expired when checked after `2026-11-01T03:23:07Z`; its artifacts remain
historical evidence only.

The byte limit covers the entire serialized request, including instructions and structured
output schema. It is not a verified upper bound on provider-billed input tokens. No real
token-count or model endpoint was called. A future, explicitly scoped synthetic preparation
must regenerate and review every identifier, request and manifest hash and disclosure record
after the durable input-token and pricing gates are resolved.
