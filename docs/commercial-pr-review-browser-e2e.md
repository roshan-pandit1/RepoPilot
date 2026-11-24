# Offline PR review to browser verification

## Fixture and identity

On 2026-11-21, 22 anonymous read-only GitHub requests captured the public
[encode/httpx#3690](https://github.com/encode/httpx/pull/3690) data. The private
owner-only fixture is `~/Library/Application Support/RepoPilot/fixtures/httpx3690-19348c64f3743221`;
its canonical manifest SHA-256 is `19348c64f374322107b39c6d6cf60375ddecd0c293ad20a91ab3615c6bba25eb`.
Replay is previously verified public GitHub data, not a fresh GitHub request. The
project is identified as BSD-3-Clause; fixture data is retained privately and no
redistribution determination is claimed. Base `20380490fd0bd13c68704080754c1385bff96d69`,
head `350221558d4f079fc4ab3673d81a4bc730fbb9c3`, repository ID `179492861`,
and PR ID `2910330172` were checked. Source bytes were never executed or sent to a model.

| Head file | Raw bytes | Git blob SHA-1 | Raw SHA-256 |
| --- | ---: | --- | --- |
| `src/ahttpx/_parsers.py` | 18446 | `2c0f153cdbafba48e122ad6bd8190b3387ff2f8e` | `1dee3bac5ec464ed0abbc2ab93faa2254b4f2e7aa3d11f3d0eff99cd9bb9813b` |
| `src/ahttpx/_server.py` | 4744 | `219342e2dbbdcbe061180c13b18b2606dffd9189` | `5ed9965b5f33605d88ba914461b04e3cd5f69610ccaeb674fa0f981ba84ee6a8` |
| `src/httpx/_parsers.py` | 18236 | `d275a111921bd2e36c3ee72ee19edcb3c7869c7b` | `c1f676c41f8803c53decdf0f764d9b778ec9cd816e9118adb5bfad3e13993191` |
| `src/httpx/_server.py` | 4523 | `d5a88050eef1e63198b2b749618733a4aee24905` | `f0b477d1b7ef7755dff326c76d6cd993d8e74c7412cd3fcb00c5b4fc78638c6b` |

All four head files were complete and their source and diff identities checked by
the existing analyzer; total head bytes were 45,949. One narrow Python rule produced
zero findings. Overall review coverage is partial and does not establish security.
The offline transport checks owner-only storage, the exact manifest digest and each
object's digest and length, rejects missing objects and has no network fallback.
The guarded stack also denies GitHub network fallback. Fixture data does not grant
repository access; synthetic OAuth membership and repository authorization remain active.

## Running application evidence

Fresh isolated PostgreSQL 16.16/pgvector and Redis 7.4.11 instances, a real
dispatcher, solo Celery worker, FastAPI and Next.js were started on unique loopback
ports. Alembic upgraded through head 0020 and `alembic check` passed. A synthetic
OAuth provider issued real application session/CSRF cookies via the existing API;
these were loaded into an isolated WebKit data store. Browser login against GitHub
was not performed. The browser used actual Next.js proxy and FastAPI responses; no
browser response interception or in-process worker invocation was used.

* Desktop 1440×900 HTTPX fixture: browser submission and reload/reopen passed; review
  `b4047894-98a2-434b-870a-80e20d9cba00` reached completed/partial with four files,
  zero findings, one processed outbox dispatch and an observed Celery receipt. The
  database creation-to-completion interval was 0.188225 seconds. A second tenant
  received 404.
* Mobile 375×812 HTTPX fixture: browser submission, all four paths, diff display,
  pinned commits and reload/reopen passed; review `0ced3489-47f1-4fdc-a8dc-cb755e6ab50e`
  completed partial with four files and one dispatch. The second tenant received 404.
  This earlier mobile run preceded the final explicit network-fallback guard; later
  desktop HTTPX and mobile synthetic runs used that guard.
* Mobile 375×812 synthetic positive control: review
  `74ab6dc4-a511-4394-ab10-fac14fca44fc` generated one `PY-SHELL-001` finding through
  the actual scanner, showed its source SHA-256, stored `useful` feedback, and showed
  it again after reload and reopening. Database feedback was `useful`, outbox processed
  with one dispatch and a worker receipt; creation-to-completion was 1.058843 seconds.
  A second tenant was denied review and feedback access. The previous desktop
  synthetic run also passed submission and feedback reload at 1440×900.

These are isolated single-run timings, not queue-delay measurements or P95 claims.
The earlier guarded real-broker test verified duplicate delivery and CSRF rejection;
those were not separately re-exercised in each browser run. The initial test harness
made a read-only GitHub request using only a synthetic token before its synthetic sync
client was corrected; the successful final offline stack denies that fallback. There
were no GitHub writes or real model calls.

## Repeatable opt-in regression

With retained PostgreSQL 16, pgvector, Redis 7.4, Node 24, local web dependencies,
macOS Swift/WebKit and the private fixture available, from `apps/api` run:

```sh
RP_E2E_ALLOW=1 RP_MODE=httpx RP_WIDTH=1440 RP_HEIGHT=900 \
RP_PR_FIXTURE_DIR="$HOME/Library/Application Support/RepoPilot/fixtures/httpx3690-19348c64f3743221" \
.venv/bin/python evaluation/run_pr_review_fullstack.py
RP_E2E_ALLOW=1 RP_MODE=synthetic RP_WIDTH=375 RP_HEIGHT=812 \
.venv/bin/python evaluation/run_pr_review_fullstack.py
```

Set the alternate viewport values for the other layouts. The script creates unique
database, broker, queue, credentials and ports, verifies the database marker and
process boundaries, and tears down owned processes and data. The fixture transport
never falls back to GitHub. This is a local macOS test harness, not a production
configuration or a substitute for an authenticated live GitHub test.

## Checks and limitations

Focused backend: 127 passed, 0 failed, 2 skipped (separate opt-in broker test and
PostgreSQL-only row-lock test in the SQLite selection). Frontend: 115 passed, 0 failed,
0 skipped; TypeScript, ESLint and Node 24 build passed. The build's symlinked dependencies
caused 27 standalone trace omissions, so standalone packaging remains unverified. Ruff,
offline lock and `git diff --check` passed. The private fixture corruption/missing-object
unit tests passed. Full browser coverage for every requested failure state was not
performed. GitHub authentication, durable pinned retry, AI approval integration,
production untrusted-code isolation, independent security review and release approval
remain open. Inference stays fail-closed. All disposable services were stopped and
test ports checked closed; normal services and P19 checkpoints were preserved.
