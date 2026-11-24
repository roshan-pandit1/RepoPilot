# HTTPX #3734 pinned source review

**Outcome: SOURCE_APPLICABILITY_UNRESOLVED.** The selected snapshot contains the
named function and stream structures, so a human can review their relationship
to the issue. The issue does not identify the HTTPX revision actually used, and
this static inspection does not establish the reported memory behavior or a
root cause. Do not admit this case as a positive benchmark label until an
association with the reporter's source state is established and independently
reviewed. No relevance grades or gold labels were created.

## Identity and scope

- Repository: [`encode/httpx`](https://github.com/encode/httpx), GitHub ID
  `179492861`; issue: [#3734](https://github.com/encode/httpx/issues/3734).
- Retained `issue-context-v1` canonical SHA-256:
  `b23e59ea453789ad4783bfbee1e6c0b0e25ac4bfb6938c0bc4b6435338cd6689`.
  The saved envelope, standalone context, triage manifest and schema agreed
  before source collection; the issue and comments were not refetched.
- Pinned commit: [`def4778d622e8bf49a9fea4dda78cca4cf666d8a`](https://github.com/encode/httpx/commit/def4778d622e8bf49a9fea4dda78cca4cf666d8a),
  committer timestamp `2025-10-16T09:04:38Z`, parent
  `435e1dac899adeb0c156c00721ecbb1124d75842`.
- Root tree `706b304f7f46b07fa19e000148be76c059890b26`; `httpx` tree
  `d5640c0fface3a952922cac81d6f47b3683c976e`; `httpx/_transports` tree
  `38e10a73288c8a7f899dd7fc934f599dbbef4a34`.

The GitHub Git-commit API returned the exact requested SHA and expected root
tree. The three tree objects were reconstructed from their returned entries and
their Git SHA-1s independently recomputed; each selected blob was checked
against its entry, byte count and Git SHA-1. An independent local `git
hash-object` recheck used `GIT_NO_REPLACE_OBJECTS=1`. The raw Git commit object
was not downloaded, so its object hash and its cryptographic binding to the
root tree were **not** independently recomputed. These checks do not establish
signed-commit authenticity, authenticate the capture producer, or prove a
complete source inventory.

Only these three `100644` Python blobs were retained. SHA-256 is over each
unaltered source file, not a chunk or an embedding.

| Path | Bytes | Git blob SHA-1 | Source SHA-256 |
| --- | ---: | --- | --- |
| `httpx/_client.py` | 65,713 | `13cd9336732a0854dae25b53b34e4b2e749b5897` | `ed717b3ac00debb48d089daeb4dd7fbaf47cb5642ebc4a6e76f3a2fc6cfc0f70` |
| `httpx/_config.py` | 8,547 | `467a6c90ae269babe3af7963d9d7c78b9f012268` | `a4fa7653ec2271f70ab05f8a6111352d876dddee84446788a1767c1a3a372d67` |
| `httpx/_transports/default.py` | 13,984 | `fc8c70970a8d7a1101677ac8d9ed209b4a053a5b` | `bfb106716ce33f4c29583cc1e43803109a9dba532613ec4f6fe2cd09e7c022e3` |

Seven anonymous, no-redirect HTTPS requests returned **133,052 HTTP
response-body bytes**, excluding headers and TLS overhead. The three source
files total **88,244 decoded bytes**. The prior manifest's stricter 100,000
bytes per file and 5,000,000 source bytes per snapshot were observed, as were
the scoped 80-file and 32 MiB response limits. No PR diff, attachment, other
issue, repository archive or other source was fetched. Recognized credential
patterns were screened, which is not a guarantee that arbitrary source is free
of secrets.

The private capture, tree metadata and source manifest are under
`/Users/roshan/Library/Application Support/RepoPilot/benchmarks/source-selection-v1/httpx-3734-source-review-20261107T024816Z-41fc3565`.
Directories were checked as owner-only `0700` and files `0600`; no raw source
or issue text is recorded in this document. The earlier license review found
BSD-3-Clause at the pinned commit. Preserve its copyright notice, conditions
and disclaimer when redistributing source; binary redistribution has the
license's notice requirements, and the non-endorsement condition applies.
Review any other applicable terms before further use. No license file was
refetched in this step.

## Historical applicability gate — Step 2B.3F

On 2026-11-07 the retained issue envelope, standalone v1 context, all three
source blobs and the three tree objects were rechecked against the recorded
fingerprints above. The following distinguishes retained issue data, GitHub
metadata, participant claims and inference. Times are UTC.

| Time | Evidence and limits |
| --- | --- |
| `2024-12-06 15:35:41` | The [tag metadata](https://api.github.com/repos/encode/httpx/tags?per_page=50&page=1) identifies `0.28.1` with commit `26d48e0634e6ee9cdc0533996db289ce4b430177`; that commit's [metadata](https://api.github.com/repos/encode/httpx/git/commits/26d48e0634e6ee9cdc0533996db289ce4b430177) reports this committer time. It is not a verified release publication time or the reporter's version. |
| `2025-10-16 09:04:38` | Pinned commit `def4778d622e8bf49a9fea4dda78cca4cf666d8a`; [GitHub's reachable-history response](https://api.github.com/repos/encode/httpx/commits?sha=def4778d622e8bf49a9fea4dda78cca4cf666d8a&until=2024-12-06T15%3A35%3A41Z&per_page=1&page=1) returned the `0.28.1` tag commit as an ancestor. This does not establish which release or revision the reporter used. |
| `2025-12-18 22:23:59` | Issue #3734 creation time in the retained context. Its example specifies Python `>=3.13`, but the retained issue and comments do not specify an exact HTTPX version or revision. The example's declaration is not an observed runtime result. |
| `2025-12-19` to `2026-01-08` | The [issue-events endpoint](https://api.github.com/repos/encode/httpx/issues/3734/events?per_page=30&page=1) returned four subscription events. This endpoint is not the full GitHub timeline and omits comment bodies. |
| `2025-12-29 22:52:40` | First retained comment created and last updated; its participant discusses context reuse and a possible certificate-store freshness tradeoff. This is a participant's assessment. |
| `2026-01-15 03:08:43` | [Commit metadata](https://api.github.com/repos/encode/httpx/git/commits/6eb7ac2f0618025fc2e284f8863716acfb18d8bc) for `6eb7ac2f0618025fc2e284f8863716acfb18d8bc` reports this committer time. Its message describes fixing the issue by breaking reference cycles; that description is a claim, not a reviewed patch or proof of a fix. |
| `2026-01-15 03:08:53` | The issue-events endpoint records a `referenced` event pointing to that commit. [GitHub's reachable-history response](https://api.github.com/repos/encode/httpx/commits?sha=6eb7ac2f0618025fc2e284f8863716acfb18d8bc&until=2025-10-16T09%3A04%3A38Z&per_page=1&page=1) returned the pinned commit as an ancestor of it. No diff, PR source or later source was fetched. |
| `2026-01-15 05:41:08` | Second retained comment created and last updated; its participant says a related PR appears to resolve the issue. No PR was inspected, and this is not independent confirmation. |
| `2026-02-25 09:42:57` | Third retained comment created and last updated; the retained issue's last-updated field has the same time. Intermediate issue edits, if any, were not reconstructed. |

The endpoint returned five issue events on one page with no next-page link:
four subscriptions and one commit reference. Six anonymous metadata requests
returned **38,561 HTTP response-body bytes** in total, below the approved
1,048,576-byte limit; this excludes headers and TLS overhead. The first tags
page contained 50 entries and had a next-page link; no completeness claim is
made for all tags. GitHub's commit-history responses establish only the
ancestry reported by GitHub, not independent signed-object provenance. No
additional issue or comment body, source, patch or attachment was downloaded.

| Gate | Assessment |
| --- | --- |
| Reporter behavior associated with this or an equivalent source revision | **Unresolved.** The reporter's HTTPX and dependency versions are not established. Neither the tag's ancestry nor the later commit message links the reporter's environment to the pinned tree. |
| Named functionality exists | **Supported as a static fact.** The named function and wrappers are in the three hash-verified files above. |
| Observable behavior described | **Partially supported.** The retained issue describes memory growth and an example; it has not been executed or independently reproduced. |
| Snapshot not known to postdate the referenced fix | **Supported only relative to the later referenced commit.** GitHub reports the pinned commit as its ancestor; the message's fix claim and any other fix history remain unverified. |
| Snapshot appropriate for a reproducible issue-to-code question | **Unresolved.** Source-version applicability, dependency/runtime conditions and a complete source universe remain unestablished. |

Decision: **SOURCE_APPLICABILITY_UNRESOLVED**. A date, a symbol match and a
later commit message are useful leads, but they do not establish that the
reported behavior affected this source state. Keep #3734 out of positive
held-out relevance labels. It may be retained as a diagnostic or possible
abstention example, without assuming an independently verified expected result.

For a human reviewer, the decision criteria are: establish the reporter's
actual HTTPX and dependency versions or another defensible source-state link;
verify the selected revision or demonstrably equivalent relevant code against
that evidence; assess whether the retained report describes an observable
question suitable for this snapshot; record contrary evidence and unresolved
runtime conditions; and only then decide whether independent relevance
annotation is appropriate. Do not treat the participant's PR claim or a commit
subject as a gold label. Any additional issue history, source or patch needs
its own scope-specific approval.

### Replacement-candidate plan

The following were existing pilot leads from the approval manifest at the time
of Step 2B.3F, not newly collected issues or established eligible examples.
Step 2B.3G subsequently collected their contexts under separate approval; see
the [replacement triage](benchmark-replacement-issue-triage-v1.md). The
information in this historical table is limited to what was known in 2B.3F:

| Candidate | Existing metadata cue | Unresolved |
| --- | --- | --- |
| `expressjs/express` [#7506](https://github.com/expressjs/express/issues/7506) | Behavioral `res.redirect`/HTTP-header cue; listed issue date `2026-10-05` versus proposed commit date `2026-09-29`. | Exact affected version, reproduction and source relationship. The short date gap is not proof. |
| `go-chi/chi` [#1188](https://github.com/go-chi/chi/issues/1188) | Route-matching behavior cue; listed issue date `2026-09-23` versus proposed commit date `2026-09-18`. | Exact affected version, reproduction and source relationship. |
| `expressjs/express` [#7532](https://github.com/expressjs/express/issues/7532) | Named `req.subdomains` cue and listing labels `4.x`, `5.x`, `bug`. | Branch labels do not specify an affected release; reproduction and correspondence to the `2026-09-29` proposed commit remain unknown. |

None has a verified affected version, reproducible symptom or historical
snapshot relationship from title metadata alone. Review independently and
reject unsuitable candidates rather than assuming these leads meet the gate.

## Static candidate ranges

These are candidate locations for blinded human review, **not** adjudicated
relevance grades or verified causes:

1. [`httpx/_config.py:23–69`](https://github.com/encode/httpx/blob/def4778d622e8bf49a9fea4dda78cca4cf666d8a/httpx/_config.py#L23-L69)
   defines `create_ssl_context`. For `verify=True`, the function calls
   `ssl.create_default_context`; an already supplied context is used in a
   different branch. No shared-context cache is visible in this function.
2. [`httpx/_transports/default.py:280–303`](https://github.com/encode/httpx/blob/def4778d622e8bf49a9fea4dda78cca4cf666d8a/httpx/_transports/default.py#L280-L303)
   calls that helper while constructing `AsyncHTTPTransport`, and passes the
   result to `httpcore.AsyncConnectionPool`. The
   [synchronous transport](https://github.com/encode/httpx/blob/def4778d622e8bf49a9fea4dda78cca4cf666d8a/httpx/_transports/default.py#L135-L157)
   has a corresponding call. These lines show construction per transport,
   not proof of allocation per connection.
3. [`httpx/_client.py:139–182`](https://github.com/encode/httpx/blob/def4778d622e8bf49a9fea4dda78cca4cf666d8a/httpx/_client.py#L139-L182)
   defines both issue-named stream wrappers and stores a response reference.
   The asynchronous request path
   [assigns its bound wrapper to `response.stream`](https://github.com/encode/httpx/blob/def4778d622e8bf49a9fea4dda78cca4cf666d8a/httpx/_client.py#L1729-L1736),
   and the [synchronous path](https://github.com/encode/httpx/blob/def4778d622e8bf49a9fea4dda78cca4cf666d8a/httpx/_client.py#L1013-L1021)
   has an analogous assignment. These references support investigating a
   possible cycle; they do not establish garbage-collection behavior, SSL
   context retention, memory growth or a defect.
4. [`httpx/_client.py:1399–1410,1432–1452`](https://github.com/encode/httpx/blob/def4778d622e8bf49a9fea4dda78cca4cf666d8a/httpx/_client.py#L1399-L1452)
   shows the default asynchronous client path creating a transport. The actual
   runtime path may differ with custom transports, environment or dependencies.

The retained issue describes a Python 3.13-or-later example and refers to SSL
context memory and stream cycles. The commit predates the issue's creation by
about two months, but date ordering alone does not show that the issue's
environment used this commit, or that this commit is an appropriate pre-fix
state. Exact HTTPX and dependency versions, observed runtime behavior, and the
effect of Python/SSL versions are unresolved. A later comment mentioning a PR
is not proof; no PR patch or later source was examined.

Independent annotators may review the retained issue and these candidate ranges
without model rankings. Before creating positive labels, document the link
between the reporter's environment and this snapshot, assess counterevidence
and decide whether source-level relevance is sufficiently supported. If it
cannot be established, retain an unresolved or excluded case rather than
inventing a label. Further issue history, version metadata or source requires
separate narrowly scoped authorization.

## Capture and future compatibility

The retained issue validates as `issue-context-v1`. In-memory checks using the
existing Python chunker covered the three complete files without changing
their text, producing 33, 11 and 14 chunks in the table's order. The existing
citation builder and `fingerprint_chunk` accepted synthetic identities for
those chunks. This was a static compatibility check, not a database snapshot,
index, search, embedding or benchmark.

`plan_snapshot` normally resolves a default branch; the existing offline
`GitSource`/benchmark provenance preflight instead expects a local Git object
repository, the actual commit object, and a source inventory. These three
files and partial tree metadata do not supply that complete input. Establishing
a pinned, complete eligible source universe, trusted capture origin and
tenant/snapshot identities will require separate review and approval; the
current private manifest is not a `git-source-inventory-v1` record. The
preflight also cannot prove independent annotation or inventory completeness.
Production terms-v2 is unchanged and does not add comments to its lexical
query.

No HTTPX code or issue-provided commands were executed. No application database,
GitHub write, real model inference, embedding generation or search benchmark was
used. The exact upstream CodeRankEmbed export revision, numerical parity,
retrieval quality and existing kernel-registry crash remain unresolved.
