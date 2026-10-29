# Benchmark v2: disposable evaluation procedure

**Prepared, not executed.** Source commit: `956a4f92983b222ce179891bbde39cb49a2022b2`.
Dataset: `repopilot-v2-956a4f9.json` (16 scored candidates, 30 labels, two unscored negative
candidates). This commit is local; no claim is made that GitHub can fetch it. The dataset is
in the working tree and is not part of that commit. Its current SHA-256 is
`813414c2eece2fa42f57d75d9cc12b6dd77eb5d75d63999ad8cae14b65bdd2ba`; it must be reviewed separately.

The existing browser capture is hardcoded to the older live commit. The repository does not
yet contain the Git-backed source adapter or dedicated v2 runner described below. Consequently,
there is **no ready-to-run command** for creating this snapshot: those components and their
tests must be implemented before execution. Do not substitute a working-tree checkout or an
invented snapshot ID. The steps below define the intended procedure, not evidence of a run.

## Approval and isolated setup

1. Obtain explicit approval to create and publish a **test-only source snapshot** from the
   specified commit in a newly created disposable PostgreSQL database. This does not approve
   a production database change, a GitHub push, a live reindex or a paid call. Confirm the
   commit is present locally with `git cat-file -e 956a4f92983b222ce179891bbde39cb49a2022b2^{commit}`
   and run `python -m app.evaluation.verify_labels evaluation/repopilot-v2-956a4f9.json` from
   `apps/api`. The validation reads Git objects and creates no database records.
2. After approval, make an isolated source checkout/archive from that exact commit in a new
   temporary directory, without modifying the user's working tree. Build the API test runtime
   from that committed source. The v2 dataset and updated validator currently exist outside
   the commit, so copy their reviewed bytes into the isolated **test harness**, and verify
   their recorded hashes before use. Do not treat those uncommitted test files as source from
   the checkpoint. Preserve the original C1 dataset separately.
3. Create a uniquely named disposable PostgreSQL database, verify its name and connection before
   running migrations 0001–0006, and set `TEST_DATABASE_URL` only to that database. Never
   run the test fixture against the normal application database; its teardown drops tables.
   Keep the database and Docker volumes unless the user separately authorizes deletion.

## Runner to implement and validate

4. Implement an injected Git-object source client for the committed Git tree. Its
   `repository`, `commit`, `tree`, and `blob` methods must satisfy the existing `SourceClient`
   and `BlobClient` protocols. Use Git plumbing with argument arrays, no shell interpolation:
   `git ls-tree -rz --full-tree <commit>` for paths/modes/object IDs, `git cat-file -s <blob>`
   for sizes and `git cat-file blob <blob>` for content. Return the selected commit SHA and a
   non-truncated recursive tree. Reject unknown SHAs, symlinks, oversized data and malformed
   paths through existing planner/collector limits. Never execute retrieved source.
5. In the dedicated test database, create an isolated tenant, membership, active installation,
   repository and authenticated test session. Use an injected fake GitHub authorization client
   consistent with that test identity; do not supply an arbitrary repository URL or token to
   a public request. Submit the existing CSRF-protected indexing request and read its real job
   ID. Invoke the existing worker with the injected Git-object and GitHub fakes, or use a
   dedicated fake-compatible Celery worker. Keep network calls and paid providers disabled.
6. Let `publish_snapshot` create its own snapshot/file/chunk UUIDs. Read the committed snapshot
   row and verify the selected commit, tenant/repository foreign keys, publication, counts,
   file paths, hashes, and inclusive source slices against Git. Assert failed/interrupted work
   preserves the previous published snapshot and that another tenant or revoked installation
   cannot read it. Never invent IDs or reuse the application snapshot.
7. Adapt the evaluation runner to use the test client's existing authenticated search endpoint
   with this v2 dataset and the same fixed result limit. Generate fake embeddings only if
   desired; report fake semantic/hybrid scores as mechanical checks. The two negative candidates
   remain outside the scored list until independently reviewed and the evaluator supports a
   suitable no-answer metric. Write separate Markdown/JSON results with source commit, snapshot
   ID, dataset hash, labels, retrieval configuration, per-query outcomes and structural citation
   checks; do not record session credentials or source snippets.
8. Verify each returned commit/path/line range against local `git show` and inclusive slices.
   A link shaped like `https://github.com/.../blob/<local-commit>/...` is **unresolved** until
   independently confirmed on GitHub. Pushing the commit, publishing it elsewhere, and live
   GitHub App indexing each require separate explicit permission. Do not fabricate remote links
   or claim line highlighting from local Git validation.

## Provenance to record

Record the actual Git commit, dataset SHA-256, migrations applied to the disposable database,
test snapshot UUID returned by the database, owner IDs appropriate to the fixture, file/chunk
counts, test commands, skipped/failing tests and resulting report paths. Do not treat the
working-tree dataset hash as a commit or as evidence of a completed retrieval benchmark.

## Implementation update (2026-10-29)

The user has approved the test-only adapter, runner and a new disposable PostgreSQL snapshot.
`app/evaluation/git_source.py` reads the exact commit with Git plumbing; it uses the existing
planner and collector. `app/evaluation/v2_disposable.py` performs authenticated fixture
indexing and keyword searches, checks published chunk slices against local Git objects, and
writes sanitized reports. It scores the 16 positive/ambiguous questions only; no fake vectors
are generated. The two negative candidates remain unscored. A local in-memory collection
found 77 accepted files, 556 chunks, one screened file and all 30 labels. This is not a
published snapshot or a retrieval result.

Docker was inaccessible from the agent sandbox. To perform the approved run from the host,
execute `bash apps/api/evaluation/run-v2-disposable.sh` from the repository root. The script
creates a separate Docker container with a randomly named database, confirms the connection
and an empty public schema, runs the destructive test fixtures only there, then migrates and
runs the benchmark in that database. It retains the new container and its new data volume.
It requires the local `pgvector/pgvector:pg16` image and the project `.venv`. It makes no paid
calls, does not use Compose services, and exits on errors. Review the script before execution.
The prior statement that no runner exists is superseded by this update; the runner has not
been tested against PostgreSQL in the agent sandbox and its results are not yet verified.
