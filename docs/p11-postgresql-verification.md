# P11 — Disposable PostgreSQL verification (2026-11-15)

## Runtime and isolation

P11 provisioned a private native PostgreSQL 16.16 runtime on Apple Silicon using the
official Homebrew ARM64 bottle (`postgresql@16`, bottle SHA-256
`d8d1d22d2e6cdadb2d69591d2e663973d5c002b32e7dffddf316a42a4db29c70`). It was installed
without linking global commands, running post-install cluster creation, or registering a
background service. The required pgvector 0.8.7 extension was built against that runtime
from a source archive verified against the published formula SHA-256
`cac0b10c360f05b2d521200105ba3697e773d4cd3731f5a915a7e37ebe0bea85` (133,025 downloaded
bytes). No Docker image was downloaded and Docker Desktop was not restarted. Homebrew's
aggregate transfer byte count was not retained.

The sole P11 cluster/data directory, private Unix socket, passfiles and logs were under
`~/Library/Application Support/RepoPilot/p11-20261115-7c4e` with private directory/file
permissions. The unprivileged server listened only on `127.0.0.1` and its private socket,
with SCRAM required for TCP; an unauthenticated TCP attempt was rejected. It used bounded
connections and shared memory, had no external listener, and exposed no application mount
or credential. Tests used a dedicated disposable role/database and synthetic marker. The
test role was a superuser within this private test cluster to support migration harnesses;
this does not describe production least privilege. No application database was used.

The same private cluster/database was assigned test-specific names required by separate
existing harness guards; these were identity labels for the same disposable storage, not
additional databases. Credential values are intentionally omitted.

## Migration and schema evidence

From an empty disposable database, the complete Alembic chain reached `0018 (head)`. A
fresh-schema `alembic check` reported no new upgrade operations. The schema had pgvector
0.8.7, the source-provenance fields (`source_byte_length`, `source_encoding`,
`source_coverage`, with the existing `content_hash` as SHA-256), and the expected indexed,
foreign-key and check-constraint structures. The PostgreSQL legacy-upgrade test started
from its historical schema and upgraded through head. The final isolated drift/migration/
patch-proposal regression selection passed **31, failed 0, skipped 0**. It exercised the
schema-local Alembic version table so test schemas do not collide with the database-wide
revision marker.

The test database fixtures drop their application tables after each suite; therefore a
catalog query after teardown is not represented as a complete live application schema.
Fresh migration, schema drift and legacy upgrade were verified in their respective tests.
No production upgrade or historical production record was altered.

## PostgreSQL-backed test results

- PostgreSQL pipeline selection (source collection/persistence, snapshots, patch proposals,
  validation/provider contracts, investigation evidence/jobs/reports, ingestion and auth):
  **309 passed**.
- Synthetic capture PostgreSQL suite: **50 passed**.
- PostgreSQL token-counting suite after UTC normalization fix: **81 passed**.
- PostgreSQL provider-count integration suite: **54 passed**.
- Final migration, schema-drift and patch-proposal regression: **31 passed**.
- Broad PostgreSQL backend selection (excluding separately run migration/drift and synthetic
  capture suites, and excluding explicitly source-executing fixtures): **1,200 passed,
  1 failed, 6 skipped, 2 deselected**. The single failure requires optional NumPy in
  `test_vector_foundation`; it was not installed because it is absent from the verified
  offline wheel cache and is unrelated to the PostgreSQL runtime. No failing test was
  removed or converted to a skip.

The counts above are separate selections and must not be added as if they were one unique
suite. No repository source or generated patch was executed; P9's trusted demonstration was
not repeated. No Ollama inference occurred.

The broad offline/SQLite selection separately reported **1,203 passed, 1 failed,
53 skipped, 2 deselected**, with the same optional NumPy test as the failure. SQLite results
are not used as PostgreSQL evidence. The private P11 venv was created from the existing
hash-verified P6 wheelhouse and current lock; all 66 available locked wheel artifacts
matched the retained manifest. `uv lock --check --offline`, Ruff and `git diff --check`
passed. Optional NumPy/ONNX model dependencies were not downloaded.

## Verified correction and remaining limits

PostgreSQL returns timezone-aware timestamps in the session timezone. A token-count binding
digest had depended on the original offset representation, causing equivalent values to
hash differently after database round-trip. `utc()` now converts aware values to UTC (and
continues to interpret legacy naive values as UTC); the new regression test covers a
non-UTC offset. This fixed behavior passed the PostgreSQL token-count and provider-count
selections.

The isolated migration harness now supports an explicitly selected, validated schema for
its Alembic version table and excludes that bookkeeping table from ORM schema comparison.
This prevents migration tests from colliding with the public test database's Alembic marker
and avoids false drift from migration bookkeeping.

The broad backend suite is not completely green because NumPy is unavailable in the
authorized verified wheel cache. Production patch execution remains disabled pending the
separate reviewed Linux KVM/Firecracker architecture; the P9 host demonstration is not a
production validation. Live provider configuration, production migration approval,
operational monitoring and deployment review remain outstanding. Frontend files and normal
services were not changed or restarted.

## Cleanup

The P11 PostgreSQL process was stopped and its PID/port were confirmed absent. Only the P11
data directory, socket and disposable credentials were removed. The PostgreSQL runtime,
compiled pgvector extension, private locked Python environment, server log, sanitized
verification JSON and private JUnit summary are retained for reproducibility. Existing
Docker resources and all normal application data remain untouched.
