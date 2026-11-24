# chi #1188 pinned source-applicability review

**Applicability: APPLICABILITY_SUPPORTED** for independent human source review.
The reporter explicitly identified master `3d1777a`; GitHub's commit-list
metadata resolved that abbreviation to the approved full commit, and the
pinned source contains the APIs and routing structures described in the issue.
This is evidence that the snapshot is suitable for further review, not proof
that the reported behavior was reproduced or that any function is the root
cause. No authoritative source-relevance label was created.

**Verification limitation:** Step 2B.3H used only the safe line-window
fallback because its Python environments lacked the Go parser packages. In
Step 2B.3H.1, the approved packages were installed into a disposable
environment and a small synthetic parse passed. The subsequent five-file
check exited with `SIGSEGV`; the previously skipped small Go test then passed
in a separate process, while a larger synthetic input reproduced the native
crash. The five-file syntax-aware check remains **blocked**. See
[verification](verification.md#step-2b3h1--go-parser-recovery-and-native-crash-2026-11-07).
This does not change the completed static applicability review below.

Step 2B.3H.2 classified the previously observed synthetic failure as
`NODE_ACCESS_CRASH`: parsing returned before the failure during tree
traversal and symbol-text access. The underlying native cause is still
unresolved. Four small synthetic cases and the small Go pytest case passed in
a network-denied sandbox; no larger crash-prone case was repeated, and no
retained chi source was read in that investigation. The five-file
syntax-aware check is still **blocked**. See the
[crash investigation](#synthetic-only-native-crash-investigation).

Step 2B.3H.3 subsequently tested Tree-sitter 0.25.2 with the same Go grammar
in a new disposable environment. Small, medium and 700-function synthetic
cases passed, including three independent repetitions of the larger case.
This did not read the retained chi files or change production dependencies;
their five-file syntax-aware check remains outstanding.

## Independent human-review preparation — Step 2B.3I

The retained issue envelope, complete issue-context-v1 and all five partial
source files were reverified. Two owner-only blind copies are prepared in the
approved private benchmark directory; they contain the original title/body,
the complete selected files with line numbers, blank templates and no prior
candidate-range suggestions or model rankings. The ordered issue comment is
withheld during initial review and remains included in the full context hash.
No human relevance judgments have been created. The raw Git commit object
remains unavailable, and source coverage remains partial. See the
[coordinator protocol](chi-1188-human-labeling.md) and
[verification record](verification.md#step-2b3i--chi-human-review-preparation-2026-11-12).

## Reviewer packet license — Step 2B.3J

The separately approved pinned `LICENSE` blob was fetched and verified against
the existing root-tree entry. Its Git blob SHA-1 is
`d99f02ffac5185e2550770d33333a67e2cf2092b`, its SHA-256 is
`a2d51b7515acfaff2f7a88688650f2fc4fd99561383e72bba2305e3db59a1647`, and
its original size is 1,123 bytes. Both private reviewer source directories
contain identical complete notices and provenance. Existing issue, source and
blank annotation files remained unchanged. See the
[coordinator protocol](chi-1188-human-labeling.md) and
[verification record](verification.md#step-2b3j--chi-review-packet-license-2026-11-12).
Reviewers still need separately controlled access and independent judgment;
the case remains a partial-source pilot with zero human labels.

## Issue and revision identity

- Repository [`go-chi/chi`](https://github.com/go-chi/chi), GitHub repository
  ID `44344606`; issue [#1188](https://github.com/go-chi/chi/issues/1188),
  issue ID `5552950835`, created `2026-09-23T11:49:57Z`.
- The already retained `issue-context-v1` record and its envelope matched
  canonical context SHA-256
  `61d54f284c13e89445d1b5ff0c4761a67d32190157b4dcc49b716ef67e4469e7`
  and envelope SHA-256
  `800cc6dbb868a166bc033224b44b195850ac3269b35a5a7ce4b2606340270ba6`.
  No issue or comment was refetched.
- Pinned commit
  [`3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc`](https://api.github.com/repos/go-chi/chi/git/commits/3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc),
  committer timestamp `2026-09-18T11:51:53Z`, parent
  `b1c9ab47626cc46b34393ad4d35779c4363c4e1e`, root tree
  `7c01dddb05b4c19847a3d6259a3f4d519e3b27fb`.
- [GitHub's commit-list metadata](https://api.github.com/repos/go-chi/chi/commits?sha=3d1777a&per_page=1&page=1)
  resolved the issue's seven-character `3d1777a` to that full SHA. A previous
  Git-object API lookup of the short form was reported as 404; it was not
  repeated here. The successful commit-list lookup and the separate reported
  404 do not conflict. Resolution is GitHub metadata, not an independent
  offline uniqueness proof across every possible Git object.
- The [`v5.3.2` ref](https://api.github.com/repos/go-chi/chi/git/ref/tags/v5.3.2)
  targets `38939062c5df4d3e8814aad1a488983112627ced`, whose committer timestamp
  is `2026-08-20T09:37:52Z`. GitHub's individual commit metadata showed the
  pinned commit 13 single-parent steps after that tag target. Only metadata
  was compared: no source from the tag or another revision was fetched, and
  ancestry does not establish source equivalence or reproduced behavior.

GitHub returned the approved commit and expected tree. The root tree's 22
entries contained ordinary blobs and trees in modes `100644` and `040000`;
no symlink or gitlink was present in that inspected tree. The tree and each
selected blob were independently rehashed with `git hash-object`, using
`GIT_NO_REPLACE_OBJECTS=1`. The raw commit object was not available from the
metadata responses and was not independently rehashed; its relationship to
the tree relies on the approved SHA and GitHub's response. These checks do not
authenticate the capture producer or prove the rest of the repository was
captured.

## Retained source

The five `100644` Go blobs below were obtained only from the pinned root tree.
Their SHA-256 values cover full retained file bytes.

| Path | Bytes | Git blob SHA-1 | SHA-256 |
| --- | ---: | --- | --- |
| `chi.go` | 4,812 | `6911bb55114a1ddad831baa7c3664a625cc1500a` | `47c70ececcbb9d71f973eda3cbadad0a46c8cc2261b285f7049b5261f337d678` |
| `context.go` | 5,788 | `c5c9a7432a3f599d8d32602523761f49052bc1c5` | `b19edcca252e2fe74e82802c4c7ce1a1c0855728f9ede1288f0224283dfc7e53` |
| `mux.go` | 17,308 | `7cfc6143d64d1e3c4f14af2ba2069878cd231b3e` | `cc44c2d620e6306b16d6d80f5f6c70f02b5814b357a4f5823372818f355ae67d` |
| `tree.go` | 22,069 | `af4052c8c0b0f2d74cadc6a1312dc9555ef32316` | `f4b12b63b662fb8e36658172b36b35705cfb24eefae0665635f4fbd52e64fb79` |
| `tree_test.go` | 27,932 | `6b542d84ca0980fbb971d2afa36fbc85d3ca458e` | `e9d8f7755589f1852791ed5b4a853c16ad12cdf8ba0db3208dac33b2dac398c1` |

Twenty-three anonymous GitHub API requests read **162,617 response-body
bytes**, including **53,845 bytes** of metadata and **108,772 bytes** of blob
responses. Headers and TLS overhead are excluded; these are bytes read, not
packet-level measurements. The retained decoded Go source is **77,909 bytes**.
The narrower previously proposed limits were enforced: 10 files, 100,000
bytes per file, 1,000,000 decoded source bytes and 4 MiB HTTP response bodies.

The source and metadata are retained outside Git under
`/Users/roshan/Library/Application Support/RepoPilot/benchmarks/source-selection-v1/chi-1188-source-review-20261107T035911Z-7b2c9613`.
The run directory and nested directories are `0700`; files are `0600`.
`metadata.json` SHA-256 is
`70902e748e88d8e1388ee71f8b7c87e743fd583d90e047843f5de9b5d569825c`.
The private capture includes an MIT license-attribution record derived from
the existing [source approval manifest](benchmark-source-approval-v1.md),
with a link to the [pinned LICENSE](https://github.com/go-chi/chi/blob/3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc/LICENSE).
No license text was fetched in this step; retain the applicable copyright and
permission notice when redistributing copies or substantial portions.
Recognized source credential-pattern checks are not exhaustive.

## Static observations for independent reviewers

The retained issue describes a regexp placeholder followed by a suffix and
contrasts its reported handling of a path containing `/` with expected 404
behavior. Its Go example uses `chi.NewRouter`, `Get`, `ServeHTTP` and
`chi.URLParam`. These API and candidate ranges are present at the pinned
commit:

- [`chi.go:30–48`](https://github.com/go-chi/chi/blob/3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc/chi.go#L30-L48)
  documents placeholder matching; [`chi.go:61–64`](https://github.com/go-chi/chi/blob/3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc/chi.go#L61-L64)
  defines `NewRouter`.
- [`context.go:10–20`](https://github.com/go-chi/chi/blob/3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc/context.go#L10-L20)
  defines the `URLParam` access path.
- [`mux.go:153–157`](https://github.com/go-chi/chi/blob/3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc/mux.go#L153-L157)
  defines `Get`; [`mux.go:428–499`](https://github.com/go-chi/chi/blob/3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc/mux.go#L428-L499)
  contains route registration and request dispatch to the routing tree.
- [`tree.go:383–406,410–468`](https://github.com/go-chi/chi/blob/3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc/tree.go#L383-L468)
  contains route lookup and the parameter/regexp traversal branch. The regex
  match and the slash check occur in alternate branches of that control flow.
  That observation identifies a line range to inspect; it is not a verified
  causal explanation.
- [`tree.go:735–793`](https://github.com/go-chi/chi/blob/3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc/tree.go#L735-L793)
  extracts pattern segments and their trailing delimiter. The selected
  [`tree_test.go:180–193`](https://github.com/go-chi/chi/blob/3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc/tree_test.go#L180-L193)
  and [`tree_test.go:272–310`](https://github.com/go-chi/chi/blob/3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc/tree_test.go#L272-L310)
  contain related suffix and regexp cases. A search of this selected file did
  not find the issue's exact `[^.]` regexp; no claim is made about unreviewed
  tests elsewhere.

These ranges are candidates for independent judgment, not grades. The
reporter's version and short SHA, GitHub's resolution and the source APIs
support using this snapshot for review. The report's output and a later
participant's claim of a fix remain unverified. No Go program or test was run,
and no PR patch, dependency or later source was fetched. Reviewers should
independently decide which, if any, ranges are relevant, record uncertainty
and disagreements, and remain blind to model rankings. A full benchmark still
needs a complete authorized source universe and an independently adjudicated
labeling process.

## Existing capture-contract compatibility

`issue-context-v1`, Git-pinned source paths, full-file hashes, citation
construction and production chunk fingerprints were checked in memory. All
five files were accepted as Go and covered without text loss by fallback
windows (2, 2, 5, 8 and 6 chunks in table order). Each returned
`parser_unavailable`; no symbols were inferred during Step 2B.3H. Step
2B.3H.1 installed the locked `tree-sitter==0.26.0` and
`tree-sitter-go==0.25.0` wheels in a disposable environment. Its small
synthetic syntax-aware parse passed, but the five-file check and a larger
synthetic diagnostic crashed with signal 11. No file-level syntax-aware result
was completed or recorded. No packages were installed into the application
environment and no Go modules were installed.

The offline `GitSource` provenance preflight expects a local Git object
repository, the raw commit object, full relevant tree objects, and a bound
tenant/repository/snapshot chunk inventory. This partial five-file capture is
not such an inventory and has no authenticated capture producer. The existing
real-data capture path is not prepared; no persistent index, SQL corpus,
lexical query, vector or retrieval result was created.

Before retrying the missing five-file syntax-aware check, separately resolve
and verify the parser risk using synthetic inputs and an authorized test
environment. Verified wheel hashes and small passing examples do not prove the
parser is safe on larger files. Before real CodeRankEmbed evaluation,
separately approve a complete bounded pinned source/Git-object capture,
independent labels, disposable database setup and offline inference; also
retain the unresolved model provenance and numerical-parity limitations.

## Synthetic-only native crash investigation

**Classification: `NODE_ACCESS_CRASH`; underlying cause unknown.** The prior
700-function synthetic diagnostic reached `analyze_source` tree traversal
after `Parser.parse()` returned, then crashed during symbol `node.text`
access and the parser's source callback. The saved fault stack includes
`node_get_text`, `bytes_subscript` and `PySlice_Unpack`. A separate
previous trial that replaced symbol text access with byte slicing also
crashed; that trial was reverted. The five-file process likewise crashed
before any file result and had `node_get_text` on its native stack, but the
record did not identify its current file or pinpoint which traversal step
had completed. Neither report establishes that parsing itself, object
finalization, the callback, or a specific reference-count error caused the
failure.

On macOS 27.2 ARM64, the existing disposable environment used GIL-enabled
CPython 3.14.10, `tree-sitter==0.26.0` and
`tree-sitter-go==0.25.0`. Go grammar ABI 15 is within the runtime-reported
13–15 range; this is an ABI compatibility check, not stability proof. The
installed package files matched their verified wheels. Four short synthetic Go
fixtures passed parse, root and child inspection, deep traversal, byte offsets,
`Point.row`/`column`, node text, and the unchanged RepoPilot analysis and
syntax-aware chunking, with no fallback. The copied, byte-identical small Go
pytest case passed (**1 passed, 13 deselected**). This task did not repeat the
larger crash-prone input because the saved synthetic traceback already
identified the failure stage. The five retained source files were not read.

Public reports are consistent with, but do not prove, a shared cause:
[Trailmark #61](https://github.com/trailofbits/trailmark/issues/61) describes
node-access crashes on larger Go files and
[its merged #64](https://github.com/trailofbits/trailmark/pull/64) pins the
0.25 series; [py-tree-sitter #500](https://github.com/tree-sitter/py-tree-sitter/issues/500)
discusses a `Point` reference-count fix and
[#505](https://github.com/tree-sitter/py-tree-sitter/issues/505) reports
different results between 0.26.0 and 0.25.2 when reading `Point.row`. Those
are upstream reports, not a diagnosis of this RepoPilot crash.

RepoPilot holds the source bytes, parser and tree during traversal, constructs
a new parser for each source, and reads `start_point.row`, `end_point.row`,
`end_point.column` and symbol `node.text`. Its parser input callback slices
the UTF-8 byte buffer at the requested offset; the current implementation does
not read node byte offsets. It uses `named_children`; it does not use
`TreeCursor` or `Parser.reset()`. No application-level ownership misuse was
established. Its bounded fallback handles expected Python-level parser
failures; **it cannot catch an in-process SIGSEGV**. Python-only indexing
remains the default; this investigation did not change the configuration,
parser or dependency pins.

| Option | Change, risk and scope | Follow-up and existing snapshots |
| --- | --- | --- |
| Keep 0.26.0 and correct a proven application misuse | No dependency change, but no such misuse has been proven. A local code change needs separate approval; shared traversal affects all non-Python grammars. | Reproduce the specific misuse synthetically and test all eight non-Python language families, Unicode, line ranges, limits, retries and citations. Do not mutate existing snapshots. |
| Test a different released runtime | Compare 0.26.0 with an officially released 0.25-series wheel, such as 0.25.2, **only if** a verified compatible binary exists. Use a separate disposable environment; any later production pin/lock change needs separate approval. Runtime behavior for all eight non-Python language families can change. | Run an isolated synthetic compatibility matrix and relevant indexing, worker, publication and citation regressions before proposing a pin. Testing does not require rebuilding snapshots; future indexing may differ. |
| Bypass Go syntax parsing with bounded line windows | This requires a separately approved explicit Go bypass; merely retaining today's exception fallback does not contain SIGSEGV. Go loses syntax-derived symbols while lexical chunks remain possible; other languages retain their existing risk. | Test fallback markers, line coverage, citations, ranking, partial status and idempotency. Existing published snapshots remain immutable; no rebuild is automatic. |
| Isolate native parsing in a supervised worker | This needs a separately approved architecture change and crash/timeout handling; process isolation limits blast radius but is not by itself a security boundary for hostile code. It affects all Tree-sitter languages if shared. | Test signal detection, clean failure, bounded retries, explicit fallback, worker delivery and all language/citation regressions. Preserve existing snapshots; no rebuild is automatic. |

The immediate recommendation is to keep multilingual indexing disabled unless
separately reviewed and complete an approved cross-language synthetic matrix
before choosing a production change. Human review of chi #1188 may proceed
independently of parser verification; there is still no reproduced routing
behavior, proven root cause or authoritative relevance label.

## Tree-sitter 0.25.2 synthetic Go experiment

In a separate environment using Tree-sitter 0.25.2 and the unchanged
tree-sitter-go 0.25.0 grammar, the four prior small fixtures, a 200-function
fixture and a 700-function fixture passed parsing, traversal and the existing
RepoPilot syntax-aware chunker. Three further independent processes passed the
700-function fixture and produced the same chunk/citation/fingerprint
manifest. No fallback was substituted for a successful syntax-aware parse.
The prior 0.26.0 crash is recorded rather than rerun; the earlier large
fixture had no saved input hash, so exact historical byte identity cannot be
independently established.

These results make 0.25.2 a candidate for a separately approved cross-language
matrix; they do not establish universal stability or authorize a production
pin change. The current fallback still cannot catch an in-process SIGSEGV.
Supervising a parser worker remains a separately reviewable containment
option. The retained chi source was not read in this experiment, the
five-file syntax-aware check remains outstanding, and the applicability
decision is unchanged. Wheel identities, input hashes, isolation limits and
actual counts are in [verification](verification.md#step-2b3h3--tree-sitter-0252-synthetic-go-compatibility-2026-11-07).

## Cross-language synthetic follow-up

The separately authorized 0.25.2
[cross-language matrix](tree-sitter-0252-synthetic-matrix.md) passed all 15
registered extensions, one independent repeat per extension and larger
synthetic workloads for every grammar. The existing adapter and in-memory
collector were used unchanged. Production publication IDs are random UUIDs,
so the requested deterministic ID generation across new snapshots is not
provided; fixed-identity fingerprint checks passed. No production pin
changed, no database was used and the five retained chi files were not read.

The earlier 0.26.0 native crash remains unexplained, and the five-file
syntax-aware check remains outstanding. A production change, a parser-worker
design and any later real-source retry need separate review and authorization.
The chi applicability finding is unchanged and is not a root-cause result.
