# Pinned source chunk audit

Commit: `63491908290e6874dbaaf2b15c2a96473aad1324`. Reconstructed locally from the Git object using the current source selection, UTF-8 decoding, credential filter and chunker; no database writes or source execution.

40 eligible files; 278 chunks; 109 whitespace-only gap chunks; 169 nonempty chunks; 168 distinct nonempty content hashes. All chunk text matches its exact inclusive line slice. Empty files produce no chunks. The worker excludes whitespace-only chunks using Python `str.strip()`. Gaps are retained because the chunker partitions all lines around top-level definitions; whitespace-only gaps have no lexical content and no definition symbol. No slicing or encoding mismatch was found in this reconstruction. The host database totals and per-file counts were independently reported by the user.

Nonempty chunk bytes: 107202; distinct-content bytes: 107162.

| File | Whitespace-only gap | Nonempty |
| --- | ---: | ---: |
| apps/api/alembic/env.py | 0 | 1 |
| apps/api/alembic/versions/0001_foundation.py | 1 | 4 |
| apps/api/alembic/versions/0002_auth_sessions.py | 1 | 3 |
| apps/api/app/__init__.py | 0 | 0 |
| apps/api/app/api/__init__.py | 0 | 0 |
| apps/api/app/api/v1/__init__.py | 0 | 0 |
| apps/api/app/api/v1/routes.py | 4 | 6 |
| apps/api/app/core/__init__.py | 0 | 0 |
| apps/api/app/core/config.py | 1 | 3 |
| apps/api/app/domain/__init__.py | 0 | 0 |
| apps/api/app/domain/models.py | 15 | 17 |
| apps/api/app/infra/__init__.py | 0 | 0 |
| apps/api/app/infra/database.py | 2 | 4 |
| apps/api/app/main.py | 4 | 8 |
| apps/api/app/modules/__init__.py | 0 | 0 |
| apps/api/app/modules/auth/__init__.py | 0 | 0 |
| apps/api/app/modules/auth/routes.py | 4 | 6 |
| apps/api/app/modules/auth/session.py | 5 | 7 |
| apps/api/app/modules/github/__init__.py | 0 | 0 |
| apps/api/app/modules/github/client.py | 3 | 5 |
| apps/api/app/modules/github/enrollment.py | 5 | 7 |
| apps/api/app/modules/github/guards.py | 1 | 3 |
| apps/api/app/modules/github/schemas.py | 4 | 6 |
| apps/api/app/modules/github/security.py | 0 | 2 |
| apps/api/app/modules/ingestion/__init__.py | 0 | 0 |
| apps/api/app/modules/ingestion/service.py | 0 | 2 |
| apps/api/app/modules/tenancy/__init__.py | 0 | 0 |
| apps/api/app/modules/tenancy/auth.py | 0 | 2 |
| apps/api/app/seed.py | 0 | 3 |
| apps/api/app/smoke.py | 0 | 3 |
| apps/api/app/workers/__init__.py | 0 | 0 |
| apps/api/app/workers/dispatcher.py | 1 | 4 |
| apps/api/app/workers/tasks.py | 5 | 7 |
| apps/api/tests/conftest.py | 4 | 6 |
| apps/api/tests/test_auth_enrollment.py | 20 | 22 |
| apps/api/tests/test_config.py | 3 | 5 |
| apps/api/tests/test_github_client.py | 3 | 5 |
| apps/api/tests/test_ingestion.py | 21 | 23 |
| apps/api/tests/unit/test_security.py | 2 | 4 |
| infra/init_env.py | 0 | 1 |
