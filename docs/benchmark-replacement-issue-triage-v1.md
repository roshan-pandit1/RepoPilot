# Replacement issue triage — 2026-11-07

**Subsequent Step 2B.3H:** The separately approved chi #1188 pinned-source
review found applicability supported for independent human review; see the
[chi review packet](benchmark-chi-1188-source-review.md). The Go syntax-aware
parser was unavailable in the local environment, and no behavior, root cause,
gold label or real benchmark was verified. The comparison below records the
earlier triage, including its original conditional source-review recommendation.

The strongest lead for a later, separately approved pinned-source review is
[`go-chi/chi` #1188](https://github.com/go-chi/chi/issues/1188). Its reporter
describes a concrete routing discrepancy, supplies a Go example and reports
testing both chi `v5.3.2` and master abbreviated as `3d1777a`. That prefix
matches the proposed commit `3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc`.
This is a **reporter claim**, not independent proof that the abbreviation is
unique, that the issue affects the full pinned commit, or that any code is
relevant. The example was not executed and no source was downloaded.

## Candidate comparison

| Issue and UTC creation | Type and reported evidence | Version and proposed snapshot | Schema | Recommendation and missing evidence |
| --- | --- | --- | --- | --- |
| [Express #7506](https://github.com/expressjs/express/issues/7506), `2026-10-05 19:10:04` | Reported bug: a redirect and two HTTP framing headers yield a Node client parse error. The body contains a short JavaScript example and expected behavior. Comments propose a change; those are claims. | No exact Express or Node version was reported in the retained context. Proposed Express commit `7ef98448f8b38099ab1ded55e458538ad47a51e7` predates the issue; that alone does not establish applicability. | Complete `issue-context-v1` accepted. | **APPLICABILITY_UNRESOLVED.** Establish the affected version and its relationship to the proposed commit before a source review. |
| [chi #1188](https://github.com/go-chi/chi/issues/1188), `2026-09-23 11:49:57` | Reported routing bug: a regexp placeholder with a suffix is said to accept a slash where comparison routes return 404. The issue includes a Go example and output. A later comment claims reproduction and a fix; the PR and claim were not checked. | Reporter claims chi `v5.3.2` and master `3d1777a`; the abbreviation matches the prefix of proposed commit `3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc`, dated `2026-09-18`. Prefix uniqueness and runtime equivalence are unverified. | Complete `issue-context-v1` accepted. | **ELIGIBLE_FOR_SOURCE_REVIEW**, conditional on separate approval. Verify the commit identity and independently assess source applicability; do not create gold labels from the issue or comment. |
| [Express #7532](https://github.com/expressjs/express/issues/7532), `2026-10-20 19:05:03` | Reported bug: an IPv6 host containing dots gives an unexpected `req.subdomains` result. The body includes examples and expected versus observed values; a linked full reproduction was not fetched. | Reporter names Express `5.3.0` and `4.22.3`, Node `v24.21.0` and Darwin. The proposed Express commit predates the issue, but its relationship to those releases is unknown. | Complete `issue-context-v1` accepted. | **APPLICABILITY_UNRESOLVED.** This is a promising reserve lead, but release/tag and commit relationships require separately approved review before source review is recommended. |

All three were open when captured; observed labels were empty for #7506 and
#1188, and `bug`, `4.x`, `5.x` for #7532. Labels and states can change. A
source snapshot preceding an issue does not prove the bug existed at that
snapshot. None of the reported causes, fixes or test results is independently
verified. No authoritative relevance grades, root causes or gold labels were
created.

## Capture and validation

The only requested issues were the three above. Their repository URL, issue
number, non-PR status, text-comment identities and ordered timestamps were
checked. Initial and final issue metadata matched for each case; this does not
make comment edits atomic. The full original text is retained privately, with
no truncation. Source URLs and per-request retrieval timestamps are in the
private capture. Comments remain context only: production `terms-v2` receives
the title, bounded body and labels, not comments.

| Issue | Comments | HTTP response-body bytes | Selected UTF-8 text bytes | Context SHA-256 |
| --- | ---: | ---: | ---: | --- |
| Express #7506 | 2 | 11,312 | 2,670 | `921a9913204d80e08c53657256c14c117733445ca962008714c4aab2bd096c21` |
| chi #1188 | 1 | 11,797 | 3,364 | `61d54f284c13e89445d1b5ff0c4761a67d32190157b4dcc49b716ef67e4469e7` |
| Express #7532 | 0 | 10,122 | 1,789 | `f22d6ba8a329d7ebadc3a38c174328902cb5a5cd8e5c5c91537b64abc0dfa4e9` |

Eight anonymous, allowlisted HTTPS requests read **33,231 response-body
bytes**, including the repeated issue metadata. HTTP headers and TLS overhead
are excluded; this is a count of response-body bytes read, not a packet-level
network measurement. Selected distinct UTF-8 text totals **7,823 bytes**.
The three JSON envelopes and capture summary occupy **17,364 bytes** on disk,
including JSON metadata and escaping. These are different measurements. The
limits were 1,048,576 selected text bytes per issue, 3,145,728 selected text
bytes in aggregate and 4,194,304 HTTP response-body bytes.

The private run is stored under
`/Users/roshan/Library/Application Support/RepoPilot/benchmarks/source-selection-v1/replacement-issue-triage-20261107T034039Z-93bfee19`.
The root and run directory are owner-only `0700`; files are `0600`. The
capture-summary SHA-256 is
`891d7bb291d82fcb20597079602b095405fb151b7fddc879ca9598835c43841c`.
File hashes, canonical context hashes, identity, comment order and counts,
permissions, expected filenames, budgets and query-builder compatibility were
independently checked. Recognized credential-pattern scans were negative, but
are not a complete guarantee that arbitrary text contains no secret. No
credentials were supplied to or stored by the collector. Existing capture
retention and deletion decisions remain separate operational matters.

## Proposed next approval

If the user chooses to continue, request permission for a **read-only source
review of chi #1188 only** at full commit
`3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc`: resolve the reported short SHA,
retrieve that commit's Git metadata and necessary tree metadata, then retain
only necessary Go source and directly related Go tests identified from that
tree. Proposed bounds are at most 10 Go files, 100,000 bytes per file,
1,000,000 decoded source bytes and 4 MiB HTTP response bodies, all within the
broader manifest limits. Store only in a new owner-only subdirectory of the
existing private benchmark root, verify Git object and SHA-256 identities,
and stop on mismatches, symlinks, gitlinks or budget violations.

This is a request for a future decision, not authorization. It excludes
repository archives, additional issue content, PR diffs, Go execution,
dependencies, application databases, indexing, embeddings, inference,
benchmarking and GitHub writes. Release/tag metadata for Express #7532 would
also require a separate, explicitly scoped approval.
