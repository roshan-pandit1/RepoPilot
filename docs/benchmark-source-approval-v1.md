# RepoPilot benchmark source approval request — v1

**Status: NOT APPROVED.** This is a request to review a metadata-only shortlist,
not permission to collect source or issue content, generate embeddings or run a
benchmark. The accompanying [machine-readable manifest](../apps/api/evaluation/benchmark-source-approval-v1.json)
contains the exact identities, proposed limits and denied permissions.

**Later scoped approval:** Step 2B.3D separately authorized retrieval and
private retention of issue contexts for `encode/httpx` #3712, #3713, #3728 and
#3734 only. It did not authorize the other six issue contexts, repository
source, embeddings or inference. Step 2B.3E then separately authorized a
bounded, pinned source review for #3734 only; see the
[source review](benchmark-httpx-3734-source-review.md). The machine-readable v1
manifest remains a denied-by-default request for its broader ten-issue scope;
it is not an authorization record for either narrower exception.

Step 2B.3F separately authorized read-only #3734 event, commit-ancestry and
tag metadata. That review confirmed a later issue-reference commit and a
GitHub-reported ancestry relationship, but did not establish the reporter's
HTTPX version or this snapshot's applicability. Its decision remains
**SOURCE_APPLICABILITY_UNRESOLVED**; see the
[historical gate and replacement plan](benchmark-httpx-3734-source-review.md#historical-applicability-gate--step-2b3f).
The metadata exception does not authorize other issue bodies, source, labels,
model inference or benchmark execution.

Step 2B.3G separately authorized and retained complete issue contexts for
Express #7506, chi #1188 and Express #7532 only. All three validate as
`issue-context-v1`; the [triage record](benchmark-replacement-issue-triage-v1.md)
recommends chi #1188 for a separately approved source review. Its reporter's
abbreviated commit matches the proposed snapshot prefix, but source
applicability and any relevance labels remain unverified. This exception does
not authorize Git objects, source, other issues, embeddings or inference.

Step 2B.3H separately authorized and retained a five-file Go source review at
the pinned chi #1188 commit, plus the relevant tag and ancestry metadata. Its
[review packet](benchmark-chi-1188-source-review.md) supports snapshot
applicability for independent human review, while the local syntax-aware Go
parser check remains unavailable. This narrow exception does not approve a
complete source corpus, other issues, source at the tag, labels, embeddings or
benchmark execution; the broader machine-readable manifest remains denied.

A later [chi #1188 full eligible-corpus request](chi-1188-full-corpus-approval-v1.md)
proposes one exact commit, bounded private collection and fail-closed checks.
It is **NOT APPROVED** and does not authorize parsing, inference or a benchmark.

In the 2026-11-07 metadata-only selection step, read-only GitHub repository
metadata, issue-list titles and dates, commit-list metadata, and the three
license files at the specified commits were inspected. No issue body, comment,
source file/tree, patch or PR diff was fetched in that step. Issue title cues below are paraphrased; open states and
visible labels are listing observations and can change. An empty visible-label
list is **not** a claim that an issue has no labels.

## Proposed repositories and pinned snapshots

| Repository | Public / default branch | GitHub size (KB) | Primary language | License at proposed commit | Proposed commit and committer date |
| --- | --- | ---: | --- | --- | --- |
| [encode/httpx](https://github.com/encode/httpx) | Public / `master` | 8,619 | Python | [BSD-3-Clause](https://github.com/encode/httpx/blob/def4778d622e8bf49a9fea4dda78cca4cf666d8a/LICENSE.md) | [`def4778d622e8bf49a9fea4dda78cca4cf666d8a`](https://github.com/encode/httpx/commit/def4778d622e8bf49a9fea4dda78cca4cf666d8a), 2025-10-16 09:04:38 UTC |
| [expressjs/express](https://github.com/expressjs/express) | Public / `master` | 10,074 | JavaScript | [MIT](https://github.com/expressjs/express/blob/7ef98448f8b38099ab1ded55e458538ad47a51e7/LICENSE) | [`7ef98448f8b38099ab1ded55e458538ad47a51e7`](https://github.com/expressjs/express/commit/7ef98448f8b38099ab1ded55e458538ad47a51e7), 2026-09-29 04:59:24 UTC |
| [go-chi/chi](https://github.com/go-chi/chi) | Public / `master` | 3,848 | Go | [MIT](https://github.com/go-chi/chi/blob/3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc/LICENSE) | [`3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc`](https://github.com/go-chi/chi/commit/3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc), 2026-09-18 11:51:53 UTC |

GitHub repository metadata: [httpx](https://api.github.com/repos/encode/httpx),
[Express](https://api.github.com/repos/expressjs/express), and
[chi](https://api.github.com/repos/go-chi/chi). The size field is GitHub's
reported repository-size metadata, **not** a measured checkout, transfer size
or eligible-source count. Its combined open-issues-and-PRs values at inspection
were 140, 260 and 144 respectively; they are not issue-only counts.

Selection is based on varied supported languages, issue-title diversity and
moderate reported repository sizes, rather than popularity alone. HTTP client,
HTTP server and router workloads offer distinct candidate retrieval problems.
The code-license metadata agrees with the license text inspected at each
proposed commit. The actual eligible-source sizes, source dependencies and
relevant code remain unexamined.

The BSD-3-Clause text requires preserving its notices and conditions and
includes a non-endorsement condition; the MIT texts require retaining the
copyright and permission notices. Both disclaim warranties. Review separately
for vendored files, dependencies, attribution and any other applicable terms.
The source-code license does **not** by itself grant blanket rights to retain or
redistribute issue bodies and comments; review their applicable terms and privacy
implications before any collection.

## Preliminary pilot issue candidates

The following are ten **pilot candidates**, not labeled examples. Their
observed state was open on the linked GitHub issue lists. Exact creation times,
complete labels, issue context, source applicability and any fix status have
not been independently checked. Dates are calendar dates shown by the lists.

| Repository / issue | Listed creation date | Paraphrased title cue | Preliminary selection cue |
| --- | --- | --- | --- |
| [httpx #3712](https://github.com/encode/httpx/issues/3712) | 2025-11-24 | MockTransport elapsed property | Named-symbol lead |
| [httpx #3713](https://github.com/encode/httpx/issues/3713) | 2025-11-25 | Intermittent SSL wrong-version error | Ambiguous environment/dependency lead |
| [httpx #3728](https://github.com/encode/httpx/issues/3728) | 2025-12-15 | RuntimeError involving cancel-scope exit | Exception named in title |
| [httpx #3734](https://github.com/encode/httpx/issues/3734) | 2025-12-18 | `create_ssl_context` memory consumption | Named-function lead |
| [Express #7506](https://github.com/expressjs/express/issues/7506) | 2026-10-05 | `res.redirect` content length and transfer encoding | Behavioral and possible interaction lead |
| [Express #7532](https://github.com/expressjs/express/issues/7532) | 2026-10-20 | `req.subdomains` and dotted IPv6 hosts | Named-symbol lead; listing showed `4.x`, `5.x`, `bug` |
| [Express #7538](https://github.com/expressjs/express/issues/7538) | 2026-10-21 | `res.send` typed-array data loss or error | Behavioral lead |
| [Express #7560](https://github.com/expressjs/express/issues/7560) | 2026-10-25 | `res.render` after a response was sent | Exception named in title |
| [chi #1188](https://github.com/go-chi/chi/issues/1188) | 2026-09-23 | Regexp route suffix and slash matching | Behavioral lead |
| [chi #1247](https://github.com/go-chi/chi/issues/1247) | 2026-11-01 | `RouteHeaders` and mixed-case patterns | Named-symbol lead |

The title cues come from the public issue lists for
[httpx](https://github.com/encode/httpx/issues),
[Express](https://github.com/expressjs/express/issues) and
[chi](https://github.com/go-chi/chi/issues). For all other candidates, labels
were not established from the displayed listing. A title mentioning an
exception does not prove that a stack trace is available; a possible interaction
does not prove a cross-module cause. The ambiguous candidate is not labeled
insufficient-evidence. No source relevance grade has been assigned.

## Temporal and provenance safeguards

Each proposed SHA is the last default-branch commit returned by GitHub's
metadata list before the UTC calendar day of that repository's earliest listed
candidate: [httpx cutoff](https://api.github.com/repos/encode/httpx/commits?sha=master&until=2025-11-23T23%3A59%3A59Z&per_page=1),
[Express cutoff](https://api.github.com/repos/expressjs/express/commits?sha=master&until=2026-10-04T23%3A59%3A59Z&per_page=1),
and [chi cutoff](https://api.github.com/repos/go-chi/chi/commits?sha=master&until=2026-09-22T23%3A59%3A59Z&per_page=1).
Commit dates and list dates are metadata, not proof of issue/commit causality,
default-branch availability at report time, or pre-fix status. The shared chi
snapshot predates #1247 by roughly six weeks, and the httpx snapshot predates
the last candidate by roughly two months; the relevant behavior may have been
introduced or fixed in between. **The reporter's source-version relationship
remains UNVERIFIED for all ten cases.** The narrower #3734 review established
that named components exist at the proposed HTTPX commit, but did not establish
the reporter's HTTPX revision or reproduce the reported behavior. After separate
approval, exclude or separately re-pin any case
whose reported version, precise issue history, pre-fix state or source
applicability cannot be established. Do not substitute a later commit silently.

## Proposed future collection boundaries

Every permission below is **NOT APPROVED**. A later approval would need to name
the exact three repositories, three SHAs and ten issue numbers above, and
separately authorize each relevant operation:

The four-HTTPX-issue triage and #3734 source-review exceptions described above
do not authorize the full ten-issue or three-repository collection in this table.

| Future operation | Current permission |
| --- | --- |
| Download Git objects, trees or source files at the three pinned SHAs | NOT APPROVED |
| Download issue bodies or ordered comments for the ten listed issues | NOT APPROVED |
| Download PR patches or diffs | NOT APPROVED |
| Store source files or issue context locally | NOT APPROVED |
| Embed source chunks or run local CodeRankEmbed inference | NOT APPROVED |
| Execute a real retrieval benchmark | NOT APPROVED |
| Send source externally, use a paid provider or write to GitHub | NOT APPROVED |

If separately authorized, the proposed maximum is three snapshots and ten
issues: 100 MiB source transfer per repository, 300 MiB aggregate source
transfer and 10 MiB aggregate issue-context transfer. Review transfer behavior
before using Git; stop rather than silently exceed a cap or index a truncated
snapshot. Retain existing limits of 100,000 bytes per eligible file and
5,000,000 source bytes per snapshot. For issue context, propose at most 10,000
body characters, 30 comments and 2,000 characters per comment. An issue whose
complete ordered context cannot be captured within the agreed bounds must be
excluded or separately reviewed; do not silently treat it as complete.

The proposed retention directory is
`/Users/roshan/Library/Application Support/RepoPilot/benchmarks/source-selection-v1`,
outside the repository, with directory mode `0700`, file mode `0600`, no
external upload and a proposed maximum retention of 30 days. The separately
approved four issue contexts and #3734 source review were retained in private
subdirectories; broader collection and deletion are not approved by this
manifest. Confirm disk protection, access controls, issue-text
terms, redaction and a retention/deletion decision before collecting data.

## Annotation and comparison protocol

Use two independent annotators where feasible, blind to lexical, semantic and
hybrid rankings. For each included case, record the complete approved issue
context, source commit, candidate ranges, the evidence linking each range to
the issue, whether that evidence predates the fix, relevance grade, confidence,
uncertainty, reviewer identity and adjudication. A linked PR or title alone is
not ground truth. Record exclusions and disagreements; cases without
established relevant source must be reported separately from recall metrics.

For the proposed graded protocol, use **3** for a directly issue-relevant
implementation range supported by independent evidence, **2** for a strongly
related range, **1** for useful supporting context and **0** only for a range
explicitly reviewed as irrelevant. These grades describe retrieval relevance,
not proof of root cause. Leave unreviewed or uncertain ranges unjudged; an
uncertain case is not an automatic zero. Freeze detailed scoring instructions
and adjudication rules before reviewing the held-out set.

All ten cases are pilot candidates. Freeze a separate future held-out corpus
and prevent shared issues, duplicated defects, backports and near-duplicate
contexts across splits. No held-out case is selected here. If a future run is
approved, use the production `terms-v2` investigation builder as lexical
baseline; preserve ordered comments in `issue-context-v1` without adding them
to lexical queries. Use identical pinned chunks, candidate universe, labels and
top-k across modes, predeclare reciprocal-rank fusion, and do not tune on the
held-out set. The existing provenance preflight checks consistency but does not
authenticate the capture producer or prove label independence or inventory
completeness.

The existing synthetic PostgreSQL verification passed 132 tests with no skips;
it does not establish real-model search quality. The ONNX Runtime kernel-registry
crash, the export's precise upstream revision and numerical parity remain
unresolved. This source-selection task did not run inference or a benchmark.
