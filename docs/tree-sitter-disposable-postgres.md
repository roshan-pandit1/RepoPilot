# Test-only Tree-sitter PostgreSQL gate

The selected disposable PostgreSQL gate for the locally staged Tree-sitter
0.25.2 change **passed in Step 2B.3H.8**. Its repository-local runner is
[`apps/api/evaluation/tree_sitter_pg_harness.py`](../apps/api/evaluation/tree_sitter_pg_harness.py).
Its [standard-library safety tests](../apps/api/evaluation/test_tree_sitter_pg_harness.py)
use synthetic data and a fake Docker adapter. A separate real disposable
database run supplied the PostgreSQL evidence recorded below. This does not
authorize activation in normal services or establish full-suite coverage.

## Prerequisites and offline preparation

- GIL-enabled **CPython 3.14.10 on macOS ARM64**, invoked from a base
  interpreter, not the application's `.venv`.
- A verified **uv 0.13.6** executable and its original official wheel
  `uv-0.13.6-py3-none-macosx_11_0_arm64.whl`, SHA-256
  `51361029b7cf91185d0092c4b356d110b4ad629e9cb11593f1e006ac72a72ca9`.
  The runner checks the wheel hash, compares its embedded executable with the
  supplied executable, and checks the version. uv 0.9.5 is insufficient.
- An offline wheelhouse containing compatible binary wheels for the locked
  base and development dependencies. The current lock graph selects 66
  packages, including Tree-sitter 0.25.2 and the eight existing grammars; it
  excludes the optional ONNX and tokenizer dependencies. The runner reports
  missing packages and verifies each selected wheel against `uv.lock`. It
  deliberately does not trust or inspect the normal application's environment
  or a global uv cache. A cache without the original wheel files does not
  by itself satisfy this wheelhouse requirement.
- An already accessible **local Docker daemon**, a local Docker Unix socket,
  and the previously recorded `pgvector/pgvector:pg16` image ID
  `sha256:0dd3149a06e4579a0d70d8fef9945636cd514005e7237deb27f9b67886f8dc4f`.
  The runner never pulls an image or switches the global context. The daemon
  and image are not checked by its read-only `check` action.
- The staged `apps/api/pyproject.toml` and `uv.lock` must still match the
  reviewed hashes embedded in the runner. A later intentional dependency
  change requires a fresh review; the runner will refuse it rather than
  regenerating a lockfile.

For Step 2B.3H.8, 67 official wheels (uv plus 66 locked test dependencies)
were verified and retained under
`/private/tmp/repopilot-h8-artifacts-m0ggfx81`. That directory is temporary
and may disappear. The [sanitized gate manifest](../apps/api/evaluation/tree-sitter-0252-postgres-gate-3faa77a8ded7c798.json)
records their filenames, sizes, published hashes and sources. No model weights
or optional ONNX packages were downloaded. Future missing artifacts require
their own authorization before download.

Set the following task-specific variables to **existing, reviewed local
paths**. The wheelhouse and tool paths below are examples to replace; the
runner does not create or download them.

```sh
repopilot_test_python='/opt/homebrew/opt/python@3.14/bin/python3.14'
repopilot_test_uv='/absolute/path/to/verified/uv'
repopilot_test_uv_wheel='/absolute/path/to/uv-0.13.6-py3-none-macosx_11_0_arm64.whl'
repopilot_test_wheels='/absolute/path/to/verified-offline-wheelhouse'
```

From the repository root, this command only checks local prerequisites. It
does not create a virtual environment, contact Docker, install packages or
run PostgreSQL tests:

```sh
"$repopilot_test_python" -I -B apps/api/evaluation/tree_sitter_pg_harness.py check \
  --python "$repopilot_test_python" --uv "$repopilot_test_uv" \
  --uv-wheel "$repopilot_test_uv_wheel" --wheelhouse "$repopilot_test_wheels"
```

Once the prerequisites are restored, Docker access can be provided without
disturbing normal services, and execution is separately authorized, review the
runner and run this command from the repository root:

```sh
"$repopilot_test_python" -I -B apps/api/evaluation/tree_sitter_pg_harness.py run \
  --python "$repopilot_test_python" --uv "$repopilot_test_uv" \
  --uv-wheel "$repopilot_test_uv_wheel" --wheelhouse "$repopilot_test_wheels" \
  --docker '/Users/roshan/.docker/bin/docker' \
  --socket '/Users/roshan/.docker/run/docker.sock'
```

`run` creates a fresh private directory under `/private/tmp` and prints its
path. It stages sources, checks Docker connectivity read-only, and copies the
verified uv executable. Inside a no-network macOS sandbox it creates a fresh
virtual environment, generates requirements from the locked versions and
verified wheel hashes, and runs `uv pip sync --require-hashes --offline
--no-index --no-build --no-python-downloads` using only the private wheelhouse.
It separately runs `uv lock --check --offline` and the staged harness safety
suite before creating its temporary database. The Step 2B.3H.8 run completed
these steps with 66 installed locked packages; it did not modify the normal
application environment.

## Source and fixture identity

The runner copies the current working-tree Python application and Alembic
files, an explicit test and helper list, `alembic.ini`, the staged dependency
files, and four explicitly named test fixtures. It checks the required test
names and rejects missing files, symlinks, credential-named paths, unexpected
staged files and oversized inputs. It does not copy `.git`, `.env` files,
application databases, model artifacts or private benchmark source.

The private `source-manifest.json` records file hashes and sizes, runner hash,
selected wheel hashes and the explicit deselection. This is a **working-tree
snapshot**, including authorized uncommitted local changes; its `git_commit`
is `null`. It is not an immutable Git commit. The runner rechecks both the
original files and staged copy immediately before and after pytest. The
manifest, staged files, log and JUnit report remain in the printed private run
directory for inspection.

## Database safeguards and cleanup

The runner creates a random name and `repopilot_5b1_checks_<random>` database,
uses the pinned local image by ID with `--pull=never`, and generates a
test-only password. It checks the exact container ID, name, image and two run
labels; unprivileged bridge networking; an empty mount list; PostgreSQL data
on tmpfs; and a single randomly assigned `127.0.0.1` port. It requires SCRAM
for all host and local HBA rules, an empty public schema, the test database
marker, refusal of passwordless TCP, and an authenticated loopback identity
check. It constructs and validates its own strict `TEST_DATABASE_URL`; it
never accepts an application URL or uses `repopilot-local`.

The test subprocess receives a clean environment with model providers disabled
and Git network protocols disabled. A macOS sandbox denies network access to
installation; during pytest it allows only the verified disposable PostgreSQL
loopback port. Before installation the runner checks that policy with two
self-owned loopback listeners and verifies local IPC. This network policy is
not a complete filesystem or hostile-code sandbox. The runner does not mount
application data or start Compose.

On ordinary completion or an error, cleanup removes only the exact container
ID after rechecking its name, image and run labels. It does not use `--rm`,
`--volumes` or delete Docker volumes. If Docker disappears, identity cannot
be established, or the process is forcibly killed, cleanup can be unconfirmed;
the runner prints the unique container ID/name for manual inspection. Never
remove a container or volume based only on a prefix. The private run directory
is retained; after reviewing its manifest and logs, an operator may remove
that exact printed directory. Do not remove unrelated temporary paths.

## Required suite and known exclusions

The release gate includes the seven previously skipped cases:

- `test_postgres_multilingual_search_and_citations`.
- `test_postgres_concurrent_requests_share_one_active_job`.
- `test_postgres_search_returns_commit_citation`.
- `test_postgres_keyword_search_handles_natural_language_and_identifiers`.
- `test_postgres_keyword_camelcase_and_bounded_results`.
- `test_postgres_concurrent_delivery_commits_one_manifest`.
- `test_postgres_v2_retrieval_deduplicates_and_fences_source`.

It additionally requires `test_postgres_legacy_job_survives_migration`, plus
the selected multilingual, publication, identity, fingerprint, tenant,
citation, evidence, provenance, ingestion and synthetic parser suites listed
in `RELEASE_TESTS` in the runner. JUnit validation fails if any selected test
is skipped or fails, or if any of those eight named PostgreSQL cases is
missing. The fixture-only synthetic capture cases and the two retrieval
metadata fixture tests are included to address relevant missing-fixture
failures from the exploratory run.

One held-out test,
`test_validation_reads_pinned_local_git_objects_without_modifying_repository`,
is explicitly deselected because it reads real repository Git objects and no
such source is staged or authorized here. The PostgreSQL cases in
`test_synthetic_capture.py` require a different dedicated database-name
contract and are also outside this gate; only its listed fixture-only cases
run. The earlier exploratory run's remaining fixture-dependent cases have not
been individually accounted for or rerun. This is not a full-suite result.
Step 2B.3H.8 reported **260 passed, 0 failed, 0 skipped, 1 deselected** and
one pytest configuration warning. All eight named PostgreSQL cases executed.
The migration test upgraded a disposable PostgreSQL schema to head 0016; a
separate PostgreSQL `alembic check` was not run.

The earlier Tree-sitter 0.26.0 native crash, the lack of a production-reviewed
supervised parser boundary, real-source behavior and the ONNX export's
provenance and parity remain unresolved. Normal-service activation, real
source parsing and any model evaluation require their respective later
authorizations.

## H.11 supervised integration additions

The durable harness now stages the feature-flagged integration tests and runs
a separate synthetic native supervisor/collector matrix before creating a
database. The parser child retains its no-network macOS sandbox; the trusted
native pytest coordinator uses a Python-level IP socket guard. The usual
PostgreSQL regression process retains its verified one-port Seatbelt profile.

For real native-child publication tests against disposable PostgreSQL, the
harness also creates an inherited local socketpair and starts a test-only
clean-environment broker. The database pytest worker proxies `_execute` over
that socket; the broker calls the actual application `run()` and its parser
child uses the reviewed no-network sandbox. This avoids nested macOS
sandboxes without giving the broker the database URL, test password or GitHub
credentials. The broker's own IP socket guard is Python-level, not an OS
network sandbox, and this is not a test of the unproxied worker and database
in the same process. The harness safety tests check the broker environment and
the database test's one-port profile. The actual child and collector are
also tested without this broker in the native matrix.

The selected H.11 run reported **119 native**, **322 PostgreSQL/synthetic**,
and **3 native-child PostgreSQL** passes; the PostgreSQL selection had one
real-Git deselection and all three suites had zero failures or skips. A new
separate test upgraded a fresh marker-verified disposable schema to Alembic
head 0016 and ran `alembic check`. The test drops only its uniquely named
schema after rechecking the database marker. The 44-case safety suite also
passed. Two additional targeted interpreter checks were run after the staged
snapshot. Exact artifacts, isolation checks, cleanup and command are recorded in
the [verification record](verification.md#step-2b3h11--supervised-parser-verification-2026-11-08).

## P6 persistent test toolchain

The P6 toolchain is retained outside the repository at
`~/Library/Application Support/RepoPilot/toolchains/p6`. It contains verified Node 24.18.0,
uv 0.13.6, and the 66 compatible locked Python test wheels plus the verified uv wheel; it
contains no application credentials, private benchmark source or model weights. The artifact
inventory and hashes are recorded in `apps/api/evaluation/p6-toolchain-artifacts.json` and
`apps/api/evaluation/p6-toolchain-verification.json`. The Node checksum was obtained from
the official release manifest; its signature could not be verified because GnuPG and a
trusted release-key ring were unavailable.

From the repository root, verify the persistent cache offline with the explicitly required
GIL-enabled macOS ARM64 Python 3.14.10 interpreter:

```sh
/opt/homebrew/opt/python@3.14/bin/python3.14 -I -B \
  apps/api/evaluation/prepare_p6_toolchain.py check
```

`check` verifies the current lock contract, private ownership and modes, wheel hashes, uv
binary and installed Node tree without downloading packages. If artifacts are missing,
the separately authorized `fetch` action validates official metadata and the approved
download caps before recovering them. It never uses source distributions or changes the
application environment. The cache's wheel inventory is tied to the recorded lockfile;
an intentional future lockfile change needs a separately reviewed inventory update.

Once the existing Docker daemon and pinned local image are available, use the reviewed
runner below. The `check` action stages no database and performs no migration; `run` may
create only the uniquely owned disposable resources after its isolation gates pass. The
runner stages a hash-manifested copy of **current working-tree files**, not a pinned Git
commit. It includes the P5 provider-contract and authorization cases in its required
JUnit gate. It never uses `repopilot-local`.

```sh
p6_tool_root="$HOME/Library/Application Support/RepoPilot/toolchains/p6"
/opt/homebrew/opt/python@3.14/bin/python3.14 -I -B \
  apps/api/evaluation/tree_sitter_pg_harness.py check \
  --python /opt/homebrew/opt/python@3.14/bin/python3.14 \
  --uv "$p6_tool_root/uv" \
  --uv-wheel "$p6_tool_root/wheels/uv-0.13.6-py3-none-macosx_11_0_arm64.whl" \
  --wheelhouse "$p6_tool_root/wheels" \
  --docker /Users/roshan/.docker/bin/docker \
  --socket "$HOME/.docker/run/docker.sock"
# After checking daemon and image availability, repeat with `run` in place of `check`.
```

On 2026-11-13, `check` verified 166 source/fixture identities and 66 locked wheels. The
subsequent `run` staged those files, then stopped before container creation because the selected local Docker
socket had disappeared. No real database-isolation gate, PostgreSQL test, migration or
schema-drift check ran in P6. Do not interpret the 44 mocked safety tests as verification
of a real Docker boundary. Restore the daemon manually without changing application
services, then rerun the above procedure; do not pull the image without separate approval.
