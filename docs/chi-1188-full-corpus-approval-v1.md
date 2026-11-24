# chi #1188 — full eligible-corpus collection request

**Status: NOT APPROVED.** This is a concrete proposal for later review, not
permission to collect source, run a model or execute a benchmark. Its
[machine-readable request](../apps/api/evaluation/chi-1188-full-corpus-approval-v1.json)
also records all proposed permissions as `NOT_APPROVED`.

## Exact target and scope

| Item | Proposed value |
| --- | --- |
| Repository | `go-chi/chi`, GitHub repository ID `44344606` |
| Commit | `3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc` |
| Root tree | `7c01dddb05b4c19847a3d6259a3f4d519e3b27fb` |
| Issue | Existing private #1188 context only; SHA-256 `61d54f284c13e89445d1b5ff0c4761a67d32190157b4dcc49b716ef67e4469e7` |
| License | Retained MIT notice: Git blob `d99f02ffac5185e2550770d33333a67e2cf2092b`, SHA-256 `a2d51b7515acfaff2f7a88688650f2fc4fd99561383e72bba2305e3db59a1647` |
| Data use | Pilot/development only; not an untouched held-out query |

Enumerate **all tree metadata** at that exact root, then retain the complete
eligible source universe under RepoPilot's current
`eligible_source_path(multilingual=True, exclude_generated=True)` policy,
including eligible tests. This covers `.py`, `.js`, `.jsx`, `.mjs`, `.ts`,
`.tsx`, `.java`, `.go`, `.rs`, `.c`, `.h`, `.cc`, `.cpp`, `.hpp` and `.cs`.
It is a complete *eligible* corpus under a declared policy, not a claim that
every repository file or dependency has been copied. Record every excluded
path and reason, including generated files, vendor directories, unsupported
extensions, symlinks and gitlinks. Do not follow symlinks or submodules.

The current path policy excludes `.git`, `.venv`, `venv`, `env`,
`node_modules`, `vendor`, `dist`, `build`, `__pycache__`, `.tox`,
`.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `.next`, `site-packages`,
`generated` and `migrations` path components. It excludes hidden basenames
and names containing `secret`, `credential` or `private_key`; the generated
filter also excludes `.generated.` and the `.min.js`, `.min.mjs`, `.g.cs`,
`.designer.cs`, `.pb.go`, `.pb.gw.go` and `.gen.go` patterns. Only regular
Git blob modes `100644` and `100755` are candidates. UTF-8, byte, line-ending
and known credential-pattern checks apply to source contents; the credential
patterns are not a comprehensive secret scanner. Do not silently remove a
file that otherwise passes the path policy because of a content rejection.

The existing retained tree metadata covers 22 root entries and lists ten
eligible root Go entries. It does **not** establish the recursive file count,
decoded source size or download size. Do not estimate those as fact. The
currently retained five files are a selected subset, not a complete corpus.

## Requested limits and storage

Request a maximum of **100 MiB of HTTP response bodies** for all commit, tree
and blob requests combined, **16 MiB per metadata response**, **100,000
decoded bytes per source file**, **5,000,000 decoded source bytes total**,
**10,000 tree entries** and **1,000 eligible files**. If a later pilot is
separately approved, propose a maximum of **5,000 chunks**. These are
ceilings, not estimates; count retries and redirects toward the transfer cap.
Do not raise them automatically. A single oversize, missing, rejected or
unverifiable otherwise eligible file makes the requested universe incomplete:
stop and report it instead of silently treating the corpus as complete.
Intentional policy exclusions must remain visible in the inventory and any
existing snapshot partial-status accounting.

Proposed destination: a **new**, non-overwriting
`chi-1188-full-corpus-<UTC>-<random>` directory below
`/Users/roshan/Library/Application Support/RepoPilot/benchmarks/source-selection-v1`.
Use owner-only `0700` directories and `0600` files, no application database
or volumes, and no raw issue/source text in Git, logs or public reports.
Review retention after 30 days; deletion or cleanup of retained data needs a
separate decision. Protect the retained MIT copyright and permission notice.

## Collection and verification gates, if approved

1. Revalidate the previously retained issue context and license. Do not
   refetch issue bodies or comments, PR patches, release archives, dependencies,
   other repositories, or any source at another revision.
2. Obtain the exact raw commit object and prove its Git object ID and tree
   binding. Existing GitHub commit metadata alone does not independently prove
   the raw commit hash. If an exact bounded acquisition cannot be established,
   stop; do not substitute a branch head or a different commit.
3. Enumerate pinned trees with bounded official read-only endpoints or a
   separately reviewed Git-object transport. Verify every tree object identity;
   reject truncation, malformed or unsupported modes and paths, ambiguous
   entries or any changed commit/tree. Record symlinks and gitlinks as excluded
   without following them. If recursive metadata is truncated, traverse the
   exact child tree identities only within the same caps.
4. For every eligible path, retrieve only the blob identified by the pinned
   tree; verify Git blob SHA-1, SHA-256, byte length and text eligibility.
   Record sorted paths, modes, object IDs, hashes, byte counts and all
   exclusions. Retain the verified commit, trees and eligible blobs for a
   reviewed offline provenance preflight; this request does not authorize
   downloading excluded blobs merely to satisfy a tool.
5. Use anonymous HTTPS with a strict response-byte counter and timeouts. Do not
   use an unbounded clone, archive download, checkout, submodule fetch, Git
   hooks, credential helpers or lazy fetching. A Git transport may be used only
   if its entire transfer is enforceably bounded; otherwise stop. Disable Git
   replacement refs and untrusted configuration. Never execute repository code.

The normal snapshot planner resolves a default branch, so it must not be used
unmodified to select this historical commit. A dedicated, reviewed pinned-object
collector/exporter and tests are still needed before source collection. The
existing `GitSource` also runs `git ls-tree -l` and parses a numeric size for
every regular blob, including excluded files. In a local synthetic Git fixture,
an absent non-source blob produced a nonnumeric `BAD` size; the metadata-only
`ls-tree` command without `-l` still listed both paths. Therefore the existing
reader can fail on the proposed eligible-blobs-only object store. A separately
reviewed fix must enumerate tree metadata without requiring excluded blob
contents, then require and verify every eligible blob; missing eligible blobs
must still fail closed. Alternatively, any expanded blob download needs a new
explicit scope and limits. The present request does **not** authorize it.

The existing retrieval capture runner accepts only its registered synthetic
fixture; it cannot capture this real corpus. The current provenance wrapper
also expects nonempty development and held-out inputs, so do not invent a
held-out example to make a one-case pilot pass.

## Human review and later pilot

The two existing blind packets are frozen to five files. Do not add full-corpus
files or later comments to either reviewer mid-review. Two independent humans
should submit their judgments first; a separate adjudicator resolves differences.
If later collection exposes additional eligible files, arrange a documented,
blind follow-up review. Do not automatically transfer subset labels to the full
corpus or fill missing human judgments with AI.

Any later real-model pilot needs **separate explicit approval** for supervised
real-source parsing/chunking, a marked disposable PostgreSQL/pgvector instance,
offline CodeRankEmbed inference and embedding generation, and lexical/semantic/
hybrid retrieval. Do not activate normal services, connect to the normal
database or execute source. Verify model and tokenizer hashes again and keep
source and secrets offline. The ONNX export's upstream source revision and
numerical parity remain unverified.

Before seeing retrieval results, freeze the query policy, source/chunk universe,
candidate pools, top-k and fusion weights. A reviewable starting proposal is
production `terms-v2` with its existing title, bounded body and labels; preserve
comments in context without adding them to its query. Propose up to three
queries, 10 lexical candidates per query, 20 lexical evidence candidates, 20
semantic candidates, top 10 results and reciprocal-rank fusion `k=60`. Use the
same frozen chunks and human judgments for all modes, reject missing vectors,
and report citation failures and missing results. These are proposed engineering
settings, not evidence of quality or authorization to run them.

For later review, propose semantic query policy `issue-title-body-v1`: the full
retained issue title, followed when present by two newlines and at most 4,000
body characters; no comments. The local CodeRankEmbed contract adds
`Represent this query for searching relevant code: ` exactly once to the query,
adds no document prefix, uses 768-dimensional CLS pooling, L2 normalization,
cosine distance and an application cap of 512 tokens. The proposed ONNX and
tokenizer revision is `72d8b338380c0b83d02b1e38b40b7b778c1c8703`; their
recorded SHA-256 hashes are
`12ba359756210927940f8a9ec569cc7d6d6f091e7fcfae6cbe09bba6aab8830d`
and `ea725c60b9022a7a491ffc348b5622a199853c806d625f673d0e2ebf1c3b5312`.
Reverify the artifacts and the selected representation contract before use.

Propose Recall@1/5/10, MRR, nDCG@10, citation validity and embedding coverage;
report insufficient-evidence cases separately. With at most 5,000 chunks,
768 float32 components require 15,360,000 bytes of raw vector values, excluding
database rows, indexes, WAL and copies. A batch size of one and CPU-only single
threading are a starting proposal, not a performance guarantee. Use reviewed
resource and network isolation and a disposable database; the earlier sampled
RSS watchdog is not a hard memory limit. A one-issue result is a diagnostic
pilot and cannot support general improvement or statistical claims. Keep future
held-out issues and tuning separate.
