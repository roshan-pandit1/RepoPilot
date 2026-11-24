# chi #1188 — blind human review protocol

This is a **pilot/development, partial-source review**, not a held-out label
set. The case is `go-chi/chi` issue 1188, issue ID `5552950835`, with
issue-context-v1 SHA-256
`61d54f284c13e89445d1b5ff0c4761a67d32190157b4dcc49b716ef67e4469e7`,
commit `3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc`, and root tree
`7c01dddb05b4c19847a3d6259a3f4d519e3b27fb`. The verified five-file
`human-review-inventory-v1` SHA-256 is
`23e84c9f7661db61d37e16cb0db95536bd3bbac7f22f81935eba89268ae0e25a`.

The available files are `chi.go`, `context.go`, `mux.go`, `tree.go` and
`tree_test.go`. Their full retained bytes, Git blob hashes and source ranges
were checked against the existing private manifest and root tree. The tree
was independently rehashed; the raw commit object is unavailable, so the
commit-to-tree association still relies on retained GitHub metadata. Neither
these checks nor the issue's applicability status prove the reported behavior,
a defect, a root cause, source completeness or an independent human judgment.

The prepared packet is stored privately at
`/Users/roshan/Library/Application Support/RepoPilot/benchmarks/source-selection-v1/chi-1188-human-review-20261112T101323Z-19f88e6b`.
Its `reviewer-a` and `reviewer-b` copies now each contain twelve owner-only
files, including the complete pinned license and its provenance. At creation,
the canonical per-copy filename/SHA-256 manifest digest was
`f898c90504e3f44e2bd73bd13479304acf272f8f4fc03a1a1cff886a27f934dd`.
After the separately authorized license update both copies matched digest
`3286432f96f0b36a0a3035c45bff9f408ae95ea9c53da8ea69312f077e57fc1f`.
The retained originals and packet remain outside Git. No human judgment has
been submitted.

## Coordinator: blind review

The private packet contains two identical reviewer copies with the original
issue title and body, all five complete files with line numbers, source
identities, a blank response template and instructions. It contains no model
rankings, prior candidate ranges, prior static explanations or prefilled
grades. The ordered comment is **withheld from initial blind review** because
later statements could anchor a reviewer. Its contents remain in the verified
private issue-context record and its bytes contribute to the full context
fingerprint. A reviewer may abstain if the withheld context is needed. If
comments are disclosed later for adjudication, record that disclosure and do
not rewrite the original submissions.

Give two people separately controlled access to the respective copies; do not
give either access to the other's response, model rankings or the prior source
audit. Two `0700` directories owned by the same account are **not** an access
barrier between people sharing that account. The coordinator should:

1. Assign pseudonyms and provide each person only their own packet through
   separate OS accounts or a protected offline handoff.
2. Include that packet's unmodified `source/LICENSE` alongside the source;
   retain the source copyright, permission and disclaimer notice.
3. Receive and protect each response separately. Do not disclose one response
   to the other reviewer before both independent submissions are frozen.
4. Give the frozen responses to a separate adjudicator only afterward. Do not
   collect names or contact details in annotation records.

The pinned MIT notice in each `source/LICENSE` is the original 1,123 bytes,
Git blob `d99f02ffac5185e2550770d33333a67e2cf2092b`, SHA-256
`a2d51b7515acfaff2f7a88688650f2fc4fd99561383e72bba2305e3db59a1647`.
It was obtained from the [verified Git blob](https://api.github.com/repos/go-chi/chi/git/blobs/d99f02ffac5185e2550770d33333a67e2cf2092b)
identified by the pinned commit's retained, rehashed tree; the
[commit-pinned path](https://github.com/go-chi/chi/blob/3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc/LICENSE)
is recorded for attribution. Source-code licensing does not establish rights
to redistribute issue text. Any newly generated packet must separately
include and verify the notice before source copies are shared.

## What reviewers decide

Reviewers independently identify whatever available source ranges they
consider relevant to understanding the reported behavior. They record why,
whether the issue and retained source support the judgment, what source may be
missing and any uncertainty. They may identify no range or abstain. Relevance
is not a claim of defective code or a verified cause. The existing proposal's
`source-relevance-v1` scale is preserved:

| Grade | Meaning |
| --- | --- |
| 0 | A range explicitly reviewed and found not relevant. |
| 1 | Useful supporting technical context. |
| 2 | A strongly related range. |
| 3 | A directly issue-relevant implementation range supported by independent evidence. |

`UNJUDGED` is an explicit unknown, not zero. `INSUFFICIENT_EVIDENCE` and
`OUTSIDE_RETAINED_CORPUS` are case-level abstentions and are not numerical
grades. Explain an abstention; do not fill it with guessed negatives. `JUDGED`
requires at least one explicit numerical judgment, which need not be positive.

## Record and validation contract

`human-relevance-review-v1` is a separate **partial-source human review**
contract, not an automatic `heldout-v2` export. It binds the repository, issue
ID and number, full context digest, pinned commit and tree, source-inventory
digest, `pilot_development` split and a mandatory partial-source warning. It
requires a pseudonymous reviewer ID, `HUMAN` self-attestation, UTC review time,
independence/adjudication status, outcome, evidence sufficiency, missing-source
notes and uncertainty. Each optional range records path, Git blob ID, file
SHA-256, inclusive lines, grade or `UNJUDGED`, rationale and uncertainty. The
blank packet template has no human ID, time, outcome or source labels.

The offline validator rehashes **every supplied retained file**, binds the
record to the verified issue and inventory, rejects wrong hashes, missing files,
duplicate ranges, out-of-range lines, malformed status combinations and
unsupported grades. Its canonical JSON uses sorted keys and compact ASCII
escaping for deterministic fingerprints. The validator cannot establish who
actually wrote a record, whether reviewers really worked independently, or
whether their judgments are correct. Records are human attestations, not
cryptographic proof of reviewer identity or independence.

Reviewers should work independently. After both submissions are frozen, a
separate adjudicator compares disagreements, reviews uncertainty and records
their own resolution with references to both canonical review hashes. The
`human-relevance-adjudication-v1` validator requires at least two distinct
self-declared blind reviewers and a distinct adjudicator before accepting
`ADJUDICATED`. An unresolved disagreement stays `UNRESOLVED`. One reviewer is
`SINGLE_REVIEWER_EXPLORATORY` and cannot be presented as independently
adjudicated. No automated merger infers human labels.

For a completed private response saved under the approved private benchmark
root, the coordinator can run the offline, read-only validation command from
`apps/api` (substitute the actual owner-only path):

```sh
.venv/bin/python -B evaluation/validate_human_review.py \
  --review '/absolute/private/path/to/response.json'
```

Use two `--review` arguments and `--adjudication` for a human-authored
adjudication JSON. The validator rejects files outside the approved private
root, symlinks, non-owner-only permissions, duplicate JSON keys and malformed
records; it does not write review data or send it anywhere. The packet's
`response-format.txt` describes the range fields and accepted statuses. The
coordinator must create any adjudication record by hand, using the same bound
identity and partial-source fields, `version`, `status`, sorted
`submission_sha256s`, `adjudicator_kind`, `adjudicator_id`, `decided_at_utc`, `resolution_note`,
`outcome` and human-supplied `labels`. Do not include personal data in notes.

## Leakage and later complete-corpus approval

The current case is a judgment on **five selected files only**. It is not a
full-repository inventory, a retrieval capture or a held-out example. Do not
promote its labels automatically to full-repository gold. Model results are
separate from initial annotation; tuning on this case makes it development
data and excludes it from an untouched held-out set. Future held-out cases
need a frozen, independent selection and adjudication process, with duplicates,
related defects and source overlap checked across splits. Before using labels
with `heldout-v2`, manually reconcile overlapping ranges, establish complete
Git provenance and satisfy the existing benchmark preflight; no automatic
conversion is provided here.

Before any full-corpus collection, separately approve the exact repository,
commit and root tree; transfer and storage limits; permitted Git objects and
source types; private destination, retention and cleanup; and the pinned
license notice and attribution. Then independently verify the raw commit and
tree objects, recursively enumerate the complete eligible source universe,
document language/extension and generated/vendor/symlink/gitlink exclusions,
hash every retained source, and record chunking and parser versions. Bind
snapshot identities, chunk and source fingerprints, ranges and citations to
the same inventory, and check label/source compatibility and completeness.
Any disposable database, model execution, embeddings and retrieval benchmark
require separate explicit approval. No such collection or inference is
authorized by this document.
