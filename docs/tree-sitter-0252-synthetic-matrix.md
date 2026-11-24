# Tree-sitter 0.25.2 synthetic cross-language matrix

**Result:** all 15 registered extensions passed the synthetic parser and chunking checks, with one independent repeat per extension. The original milestone marked its verdict incomplete because production chunk IDs are generated with uuid4. The subsequent staged-update acceptance criterion explicitly confirms that opaque publication IDs are intended to be random; fixed-configuration source processing, rather than regeneration of the same IDs, is the deterministic contract.

This experiment uses GIL-enabled CPython 3.14.10 on macOS 27.2 ARM64, Tree-sitter 0.25.2 and the exact grammar versions from the existing lock. It does not authorize a production change and does not prove universal stability.

## Runtime and grammar wheels

The alternative runtime wheel SHA-256 is bda059af9d621918efb813b22fb06b3fe00c3e94079c6143fcb2c565eb44cb87 (tree_sitter-0.25.2-cp314-cp314-macosx_11_0_arm64.whl). The eight grammar wheels matched the project lock and official PyPI metadata; Go was reused from a previously verified local wheel. Installed payloads matched the verified archives. No unrelated dependencies were installed.

| Grammar | Version | Verified wheel | SHA-256 |
| --- | --- | --- | --- |
| tree-sitter-c | 0.24.2 | tree_sitter_c-0.24.2-cp310-abi3-macosx_11_0_arm64.whl | 97bc80a224d48215d4e6e6376bf30d114f4c317b8145ff1b02afe785d4ba7bdd |
| tree-sitter-c-sharp | 0.23.5 | tree_sitter_c_sharp-0.23.5-cp310-abi3-macosx_11_0_arm64.whl | a75994a11f6fed3f5b8c36ad6a00e5dc43205bd912c43af3a2a54fdf649664eb |
| tree-sitter-cpp | 0.23.4 | tree_sitter_cpp-0.23.4-cp39-abi3-macosx_11_0_arm64.whl | bc3c404d9f0cbd87951213a85440afbf4c31e718f8d907fa9ee12bea4b8d276f |
| tree-sitter-go | 0.25.0 | tree_sitter_go-0.25.0-cp310-abi3-macosx_11_0_arm64.whl | 503b81a2b4c31e302869a1de3a352ad0912ccab3df9ac9950197b0a9ceeabd8f |
| tree-sitter-java | 0.23.5 | tree_sitter_java-0.23.5-cp39-abi3-macosx_11_0_arm64.whl | 24acd59c4720dedad80d548fe4237e43ef2b7a4e94c8549b0ca6e4c4d7bf6e69 |
| tree-sitter-javascript | 0.25.0 | tree_sitter_javascript-0.25.0-cp310-abi3-macosx_11_0_arm64.whl | 8264a996b8845cfce06965152a013b5d9cbb7d199bc3503e12b5682e62bb1de1 |
| tree-sitter-rust | 0.24.2 | tree_sitter_rust-0.24.2-cp39-abi3-macosx_11_0_arm64.whl | 01a46622735498493f29f3e628a90de95c96a07bfbeb88996243eb986b1cee36 |
| tree-sitter-typescript | 0.23.2 | tree_sitter_typescript-0.23.2-cp39-abi3-macosx_11_0_arm64.whl | c7cc1b0ff5d91bac863b0e38b1578d5505e718156c9db577c8baea2557f66de8 |

## Language and ABI results

The runtime reports grammar ABI range 13–15. Every valid fixture used the application's actual analyzer and collector, with Python using its existing AST path. Each malformed fixture returned the explicit syntax_error fallback; the node-limit fallback was also checked. Each valid extension ran in two independent processes and had identical symbol metadata, boundaries, synthetic-ID fingerprints and citations. Each larger workload ran once, not as a repeated reliability benchmark.

| Family | Extensions | Grammar / version | ABI | Initial + repeat | Larger fixture | Fallback |
| --- | --- | --- | ---: | --- | --- | --- |
| Python | .py | Python AST | — | 2/2 passed | passed (.py) | syntax_error, node_limit |
| JavaScript / JSX | .js, .jsx, .mjs | tree-sitter-javascript 0.25.0 | 15 | 6/6 passed | passed (.js) | syntax_error, node_limit |
| TypeScript | .ts | tree-sitter-typescript 0.23.2 | 14 | 2/2 passed | passed (.ts) | syntax_error, node_limit |
| TSX | .tsx | tree-sitter-typescript 0.23.2 | 14 | 2/2 passed | passed (.tsx) | syntax_error, node_limit |
| Java | .java | tree-sitter-java 0.23.5 | 14 | 2/2 passed | passed (.java) | syntax_error, node_limit |
| Go | .go | tree-sitter-go 0.25.0 | 15 | 2/2 passed | passed (.go) | syntax_error, node_limit |
| Rust | .rs | tree-sitter-rust 0.24.2 | 15 | 2/2 passed | passed (.rs) | syntax_error, node_limit |
| C | .c, .h | tree-sitter-c 0.24.2 | 15 | 4/4 passed | passed (.c) | syntax_error, node_limit |
| C++ | .cpp, .cc, .hpp | tree-sitter-cpp 0.23.4 | 14 | 6/6 passed | passed (.cpp) | syntax_error, node_limit |
| C# | .cs | tree-sitter-c-sharp 0.23.5 | 15 | 2/2 passed | passed (.cs) | syntax_error, node_limit |

.h is mapped to the C grammar. C++-only syntax in a .h file may therefore fall back; it was not treated as C++ syntax-aware success. JSX shares the JavaScript grammar; TypeScript and TSX use separate entry points of the TypeScript package.

## Fixture fingerprints

Small valid fixtures use UTF-8 and CRLF; malformed fixtures are separate UTF-8 strings. Repeated hashes mean the same fixture text was tested through multiple extension mappings.

The inert fixture generator is retained at
[tree_sitter_0252_matrix_fixtures.py](../apps/api/evaluation/fixtures/tree_sitter_0252_matrix_fixtures.py).
It matches the generator used for the observed runs (SHA-256
`d9dd13c7db29c98db5e920b53287c147588d2ed71312c7c674ba5a2030fe8e29`).
It generates source strings only; it does not compile, execute or parse them.

| Extension | Valid bytes | Valid SHA-256 | Malformed SHA-256 |
| --- | ---: | --- | --- |
| .py | 163 | b1a2b2518933c915cfb2faa639f43f3c6c79c66137c9a748cb7951d1a1082029 | 553eda8c53fc903895e005a1bc644c6058ffd91ce4df67c9fbdbe8763f6d8862 |
| .js | 151 | 28c75badf6ac068161b6821fab470a29b46a6f25f1cf74196c6f417d7cf05f59 | ff6e2a6cf56e91d01d1729815c725fba4cd1c75c59fd4097f22f8498f9cde32b |
| .jsx | 109 | 6abe8cc0c4aa60f6750b98fd33c5940766e0b8d48dbf1db1f5260b3df0a8d8d9 | ff6e2a6cf56e91d01d1729815c725fba4cd1c75c59fd4097f22f8498f9cde32b |
| .mjs | 151 | 28c75badf6ac068161b6821fab470a29b46a6f25f1cf74196c6f417d7cf05f59 | ff6e2a6cf56e91d01d1729815c725fba4cd1c75c59fd4097f22f8498f9cde32b |
| .ts | 136 | a5c7a9bd59e1b7d36ae4bab638819a336e094d3da892b2d2a9cb86c950ceb022 | ff6e2a6cf56e91d01d1729815c725fba4cd1c75c59fd4097f22f8498f9cde32b |
| .tsx | 130 | 905c8d6984c13239ec83414282b4056c3897c9a0a0e2c5e84f38ea260f000693 | ff6e2a6cf56e91d01d1729815c725fba4cd1c75c59fd4097f22f8498f9cde32b |
| .java | 132 | f397972ea873db229840d558088d38955ec8ce7c80903573b1e9c8fa6722cb63 | e9a87386fd4a2bfab15f168af9f79b12e33b9368f497aa96dc3a471ad2ba4472 |
| .go | 150 | 1782f1e9eff5cb6f3d7c06551583f7e48f2a0a96694d2c738a6aaf185ba0b84d | 54184642ab172fe3cbe871be2a0ed8892280cecc557d8d4bd04177434171b06f |
| .rs | 128 | 46cc7c209d4d28a3dee8734239c63857c8aad62d3040c52c99015d93ebaaccf9 | cdfb6929e7c395b73c03414e1e440cdd98a1dad4b6d9da55d069594ab6048847 |
| .c | 150 | a0d8f5b9871cd2324a9794b1b66ddf8cb79754422e4b389cbc45e2ca10aa67a2 | 30b71af0334678bd5e966ceabc8d45ffe9402ffd629eea256ca129e60b708616 |
| .h | 150 | a0d8f5b9871cd2324a9794b1b66ddf8cb79754422e4b389cbc45e2ca10aa67a2 | 30b71af0334678bd5e966ceabc8d45ffe9402ffd629eea256ca129e60b708616 |
| .cpp | 119 | c1d081b20eacf428177cbf96d230f92cddcca257229f75c67346cdc846acde15 | 30b71af0334678bd5e966ceabc8d45ffe9402ffd629eea256ca129e60b708616 |
| .cc | 119 | c1d081b20eacf428177cbf96d230f92cddcca257229f75c67346cdc846acde15 | 30b71af0334678bd5e966ceabc8d45ffe9402ffd629eea256ca129e60b708616 |
| .hpp | 119 | c1d081b20eacf428177cbf96d230f92cddcca257229f75c67346cdc846acde15 | 30b71af0334678bd5e966ceabc8d45ffe9402ffd629eea256ca129e60b708616 |
| .cs | 101 | 6e2809c8889458d780942129455bf5aa0d4b6d1f7fee3e1b7278ec0c1253a4f9 | 7e60fc2f74d4dbbb6f7383ba35387910683f15f9c24bd43c14730d4664e39aa1 |

Every grammar entry point also received a bounded larger LF/UTF-8 fixture with a function exceeding the 120-line chunk limit and 150 additional declarations. Python's AST path received an analogous workload.

| Larger workload | Bytes | SHA-256 | Chunks |
| --- | ---: | --- | ---: |
| .py | 5309 | a4fde86c72f8709774fb520bbf6a8051f03b54484c607096acaa0ba0d6ff0e3a | 153 |
| .js | 5939 | 6858cd7c2f19ba5871d015fe2919d9afd6b0e8b80aad24d439a00b70e777206e | 153 |
| .ts | 7147 | 73ba6af1df67ea378702bd078724e1456c860035f155b037fc933cf72fbc94b0 | 153 |
| .tsx | 8965 | 4ecc18ed4963f02c4a2c7e83a04ab9bf8881369f4a9271b41ac1a1e9ad066a72 | 153 |
| .java | 7002 | 46d771829a1d19c9f3bc08bd1808dcf2fadd7826796bf430ad33cc8ed97f962a | 153 |
| .go | 5664 | c4002db307faa0dc0e661e3b027361fe6ba7e3c839ad1b2a54fd82d319cac300 | 153 |
| .rs | 4887 | 8d6af79a300735ddbb930016bc763ed0bcbbe92ea400626de28b94ceb76c7b11 | 153 |
| .c | 5789 | c244a1e013d2459c3941830d201b81fcfd995184abaad96db7df4c1f8daa2cb3 | 153 |
| .cpp | 5789 | c244a1e013d2459c3941830d201b81fcfd995184abaad96db7df4c1f8daa2cb3 | 153 |
| .cs | 8059 | 9f5cf440554c10a41fd19f3de30bdc1a22dacef22835d6c0d7f9ea68cee5b5dd | 153 |

## Test method and limits

Forty isolated processes passed: 30 small initial/repeat runs plus ten larger runs; none failed, skipped, crashed, exceeded a watchdog or showed nondeterminism. The byte-identical copied existing adapter suite also passed **14 tests, 0 failed, 0 skipped**. A separate no-database identity audit confirmed the publication ID behavior described below. Ruff and git diff --check passed.

The tests checked grammar initialization and ABI, node traversal, node.text, row/column and byte offsets, actual analyze_source, chunk_python or chunk_multilingual, and collect_source with a synthetic blob client and snapshot plan. They checked import/symbol metadata, exact line coverage, 120-line chunk bounds, source hashes, citations and the unchanged pure fingerprint_chunk function. No external repository source was compiled, executed, downloaded or parsed.

The sandbox denied network, home and repository reads, writes and process forks; the existing app test packages were read-only only for the copied pytest suite. Core dumps were disabled, with a 10-second CPU limit and 18-second alarm for matrix workers. A supervisor enforced a 24-second wall limit and sampled RSS against 256 MiB. macOS rejected the address-space limit; the RSS watchdog was sampled, **not a hard memory limit**. Peak sampled RSS was 36,368 KiB for the matrix and 46,512 KiB for pytest.

The diagnostics and logs are temporary under /private/tmp/repopilot-ts0252-matrix.ztbsM047; they are not durable application test infrastructure. Their absence later would not create or modify application data.

## Identifier and fingerprint limitation

publish_snapshot creates the snapshot, indexed-file and code-chunk IDs with uuid4. Those IDs are stable after persistence but are **not deterministically regenerated** across new publications. The matrix used deterministic synthetic IDs solely to compare fixed-identity results; it does not validate production ID generation. fingerprint_chunk binds the chunk ID, file ID and snapshot ID as well as source and range, so identical source in a different new snapshot can have a different evidence fingerprint. With fixed IDs and contents, the tested fingerprints were repeatable. This is an existing contract, not a regression shown to be caused by 0.25.2.

The subsequent staged-update milestone treats this behavior as the intended
identity contract. New synthetic SQLite tests passed for separate UUIDs,
stable source processing and citations, publication-bound fingerprints,
cross-tenant foreign keys and cross-snapshot evidence rejection. PostgreSQL
verification remains blocked and the staged runtime is not activated.

## Production impact and remaining work

- A future pin change would require a reviewed pyproject.toml and uv.lock update, compatible binary wheels and separately authorized rollout.
- The callback-based parser API worked on these fixtures without an adapter change. Production-scale syntax, cancellation, resource limits and other platform/Python combinations were not exhaustively tested.
- No paired 0.26.0/0.25.2 cross-language boundary comparison was run. Future chunks and symbols could differ; parser_version records the runtime under the 0015 contract. Static review found no schema change required solely to store this version; database compatibility still needs verification.
- Existing published snapshots and evidence should remain immutable. A runtime change alone does not require rebuilding them. Any new snapshot or changed chunk inventory would need its own provenance and separate approval. Revision 0016 binds chunk-embedding links to chunk fingerprints, so links for newly created chunk identities must be revalidated rather than assumed interchangeable; any embedding generation needs separate approval.
- Before any production decision, use disposable PostgreSQL to verify publication, retries, tenant isolation, citations, evidence manifests and vector-link compatibility. No database or migration was used here.
- A proposed rollback is to stop admitting new multilingual indexing jobs, drain or safely stop affected workers under an approved operations plan, restore the prior reviewed code and lock, and verify existing snapshots and evidence without rewriting them. Because the prior 0.26.0 runtime has a known crash, leave multilingual indexing disabled until a safe parser path is reviewed. A runtime-only rollback does not by itself require a database downgrade.
- A supervised parser process with crash detection and explicit fallback remains advisable for blast-radius control; process isolation alone is not a complete hostile-code sandbox.

The 0.26.0 crash cause, five-file chi syntax-aware check, ONNX export provenance/parity and real semantic retrieval quality remain unverified. The chi source-applicability finding remains supported for independent human review, not a reproduced bug or gold label.

## Staged update follow-up

RepoPilot's local declaration and uv lock now stage Tree-sitter 0.25.2; the
eight grammar records and all unrelated locked packages remain unchanged.
No normal service was restarted or configured to use it. The 0.25.2 lock
contains prebuilt CPython 3.12–3.14 wheels for macOS and common Linux
x86-64/ARM64 targets, but unlike 0.26.0 it has no Linux RISC-V wheel. The
disposable macOS ARM64 installation and synthetic checks passed; other
platforms were not executed. At Step 2B.3H.5 the staged update was
**incomplete** pending disposable PostgreSQL regression. See
[verification](verification.md#step-2b3h5--staged-tree-sitter-0252-update-2026-11-07).

Step 2B.3H.7 prepared a repository-local
[disposable PostgreSQL procedure](tree-sitter-disposable-postgres.md) and
synthetic guard tests. It did not run PostgreSQL, validate the new runner on a
real daemon, or authorize activation; the seven database cases remained open
at that step.

Step 2B.3H.8 subsequently ran the selected suite against a new, isolated
disposable PostgreSQL instance: **260 passed, 0 failed, 0 skipped, 1
deselected**. All seven previously skipped cases and the PostgreSQL migration
test executed. The container was removed and the normal services were not
restarted. This satisfies the selected database gate, not a full backend
regression or authorization to enable multilingual indexing. The earlier
native crash cause and parser-process isolation decision remain unresolved.

### Parser-process follow-up design

`process_index` currently calls `collect_source` in the Celery worker process,
so a native parser crash can terminate that worker before publication. Late
acknowledgement and lease recovery can cause redelivery or later reclamation;
their behavior for repeated crashing inputs needs explicit testing. The
current Python exception fallback cannot catch SIGSEGV.

A separately reviewed design could run each bounded file parse in a supervised
subprocess with no network, credentials or writable repository access. The
parent would enforce a wall deadline and OS memory/CPU limits where available,
validate the returned ranges and metadata, and treat a signal, timeout or
invalid response as an explicit parser failure. Product policy must decide
whether to skip the file or produce bounded line windows with a visible
failure status; neither outcome may be labeled syntax-aware success. Tests
should cover hostile and malformed input, duplicate deliveries, lease expiry,
retry bounds, atomic publication, tenant fencing and signal cleanup. Process
isolation reduces worker blast radius but is not by itself a complete
security sandbox. No such worker is implemented or activated here.

### Guarded rollback of this staged pin

The exact pre-stage copies were held in
`/private/tmp/repopilot-ts0252-stage.sJz6LqCp/backup`; they were no longer
present during the Step 2B.3H.6 recovery attempt. The following guarded command
will stop until those exact copies are recovered. If they are recovered and
neither staged file has changed since this milestone, the command restores
only those two files to their pre-stage bytes:

```sh
python3 - <<'PY'
from hashlib import sha256
from pathlib import Path
import os
import tempfile

api = Path("/Volumes/Samsung SSD/Project/RepoPilot/apps/api")
backup = Path("/private/tmp/repopilot-ts0252-stage.sJz6LqCp/backup")
hashes = {
    "pyproject.toml": ("138b87d2cef47d6cf48e21aa4652e2039f56fa7dcb4421e9af76eae7f0d54f1c",
                       "e0fe0e272583fefecbc09d4c9e0631c41771f370b267a4dd4569fa349ee4e240"),
    "uv.lock": ("42649a78b5f1b099dc58ae81eea00108fa80dad6453e08a3d0e1a749f1089998",
                "40139126d31b521cc5377f1333b22d7c18de733840d1c63d848309ba7ad9c09a"),
}
for name, (original, staged) in hashes.items():
    if (not (backup / name).is_file()
            or sha256((backup / name).read_bytes()).hexdigest() != original
            or sha256((api / name).read_bytes()).hexdigest() != staged):
        raise SystemExit("Backup missing or file changed; stop and review manually.")
for name in hashes:
    target = api / name
    fd, temporary = tempfile.mkstemp(prefix=".rollback-ts0252-", dir=api)
    with os.fdopen(fd, "wb") as stream:
        stream.write((backup / name).read_bytes())
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temporary, target.stat().st_mode & 0o777)
    os.replace(temporary, target)
print("Restored the exact pre-stage dependency files.")
PY
```

If the backups have disappeared or either file has changed, the guard stops
without overwriting those files; review the current diff and reconstruct a
targeted rollback instead. Do not reset the repository or alter snapshots,
databases or volumes. The previous 0.26.0 runtime has a known native-crash
risk, so rolling back the files does not authorize enabling multilingual
indexing.

## Test-only supervised parser follow-up

Step 2B.3H.9 added a disconnected, macOS-only synthetic
[supervisor prototype](supervised-parser-prototype.md), using this matrix's
original fixtures and the existing 0.25.2 disposable environment. Its final
suite passed **64 tests** across all 15 extensions and controlled child
failures. A separate existing parser/indexing selection passed **53 tests**,
with **3** database-dependent tests deselected. Parser success and explicit
fallback remain distinct. These results neither explain the 0.26.0 crash nor
prove universal native stability. The five retained chi files were not read.
Normal dispatch and the staged dependency files were not changed in this step.
See the [verification record](verification.md#step-2b3h9--supervised-parser-prototype-2026-11-07).

## Feature-flagged collector integration

Step 2B.3H.10 wired a macOS-only supervision path into multilingual collection
behind a second flag that defaults off. Synthetic mocked-transport integration
and 25 sandboxed child/transport checks passed, but the disappeared disposable
environment and missing grammars prevented an actual supervised cross-language
rerun. The prior 40-process matrix and PostgreSQL gate predate this integration;
they do not verify it. Linux isolation, the unresolved 0.26.0 native crash and
the full backend/schema-drift gates remain open. See
[verification](verification.md#step-2b3h10--feature-flagged-supervisor-2026-11-08).

## Supervised integration verification — Step 2B.3H.11

A new hash-verified disposable 0.25.2 environment exercised the actual
application supervisor and collector on all 15 synthetic extension variants.
The native/prototype suite passed **119**, the selected PostgreSQL suite passed
**322** with one real-Git case deselected, and a native-child PostgreSQL and
migration/drift suite passed **3**; none skipped or failed. The harness safety
suite passed **44**. The eight grammar versions and the staged lock remained
unchanged. Two additional targeted interpreter checks passed after the staged
run. These tests supersede H.10's missing-grammar and missing-disposable-
database limitations, not its production-activation restrictions.

The PostgreSQL native test uses a test-only IPC broker to preserve the
database test sandbox while the actual parser child has its own no-network
macOS sandbox. The broker is not itself OS-network-sandboxed, and the exact
unproxied worker-plus-database path was not tested. The earlier 0.26.0 crash
is still unexplained, the 0.25.2 results do not prove universal stability,
and a sampled watchdog cannot guarantee a hard memory limit. Full backend and
Linux sandbox verification remain outstanding. See the detailed
[verification record](verification.md#step-2b3h11--supervised-parser-verification-2026-11-08).
