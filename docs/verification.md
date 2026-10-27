# Verification record — 2026-10-27

Executed in the provided restricted macOS workspace. No existing Git checkout was present.

| Check | Actual outcome |
| --- | --- |
| Reference inspection | Blueprint, SQL, OpenAPI read; originals preserved and copied to docs/reference |
| Signature Pytest subset | **7 passed**, using cached Pytest 8.3.5 and Python 3.14 |
| Python `compileall` | Passed for apps/api and infra |
| TypeScript transpilation | 9 TS/TSX source files; zero syntax diagnostics using cached TypeScript 5.9.3; **not full type checking** |
| `docker compose config --quiet` | Passed with locally generated ignored .env |
| `make dev` | Blocked: permission denied opening Docker daemon socket |
| `make smoke` | Blocked: same Docker socket restriction; no issue persisted during this session |
| Full Pytest suite | Collection blocked: FastAPI not installed; remaining dependencies unavailable |
| Ruff | Blocked: module unavailable |
| Frontend `npm run typecheck` | Blocked: tsc not installed in application dependencies |
| Frontend lint/build | Not reached after dependency/typecheck failure |
| Dependency installation | PyPI/npm DNS/network unavailable; offline cache lacks required dependencies |
| Lock generation | Incomplete; neither uv.lock nor package-lock.json fabricated |
| Migrations / PostgreSQL concurrency | Not executed |
| Browser-rendered dashboard verification | Not executed |
| GitHub Actions | Configuration authored; no remote run performed |

An initial signature test failed because the expected fixture digest was transcribed incorrectly.
The expected value was corrected against GitHub's published test vector, and all seven tests
then passed. The implementation's HMAC calculation did not need modification.

This does not satisfy the complete Sprint 1 definition of done. On an unrestricted development
host, resolve dependencies (`make lock`), commit the locks (Docker/CI already enforce frozen installs), then run
`make dev`, `make seed`, `make smoke`, the full PostgreSQL suite, Ruff, frontend type checking,
ESLint, production build, and browser verification. Fix failures before calling the sprint complete.
