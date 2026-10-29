# Benchmark v2 provenance and checkpoint proposal

**Provisional; not a labeled or scored benchmark.** Read-only inspection on 2026-10-29 found
HEAD `63491908290e6874dbaaf2b15c2a96473aad1324` and 18 proposed questions. The 14 concrete
implementation questions comprise two with all listed implementations unchanged from HEAD,
eleven with new or modified working-tree implementations, and one with mixed provenance.
Two ambiguous and two negative candidates require separate judgment. `COMMITTED` below means
the named function's parsed body is the same in HEAD; `UNCOMMITTED` means the function is new
or changed relative to HEAD. Working-tree ranges are inclusive and may change; they are not GitHub
citations. Matching AST bodies do not prove identical surrounding imports or runtime behavior.

| # | Proposed question | Working-tree evidence and inclusive range | HEAD and provenance | Review |
|---:|---|---|---|---|
| 1 | GitHub login sessions created and revoked | `apps/api/app/modules/auth/routes.py`: `callback` 45–114, `logout` 126–135 | Both exist and match HEAD; **COMMITTED** | Two relevant functions. |
| 2 | Current repository access enforced | `apps/api/app/modules/ingestion/code_routes.py`: `allowed_repository` 24–30 | File absent at HEAD; **UNCOMMITTED** | Delegates to `authorized_repos`; multiple legitimate locations. |
| 3 | GitHub webhook signatures checked | `apps/api/app/modules/github/security.py`: `valid_signature` 6–8 | Exists and matches HEAD; **COMMITTED** | Request-level check in `api/v1/routes.py` is also relevant. |
| 4 | Pinned snapshot planned | `apps/api/app/modules/ingestion/code_snapshot.py`: `plan_snapshot` 36–83 | File absent at HEAD; **UNCOMMITTED** | Also review worker authorization before publication. |
| 5 | Indexing jobs claimed and published | `apps/api/app/workers/tasks.py`: `process_index` 162–306; `apps/api/app/modules/ingestion/code_persistence.py`: `publish_snapshot` 12–43 | Functions absent at HEAD; **UNCOMMITTED** | Claim and publication have separate functions; long worker chunks may need multiple labels. |
| 6 | Python source chunking | `apps/api/app/modules/ingestion/code_chunking.py`: `chunk_python` 14–53 | File absent at HEAD; **UNCOMMITTED** | Candidate definition anchor. |
| 7 | Source files screened | `apps/api/app/modules/ingestion/code_collect.py`: `collect_source` 33–63 | File absent at HEAD; **UNCOMMITTED** | Also review selection and filtering functions. |
| 8 | GitHub citations built | `apps/api/app/modules/ingestion/code_routes.py`: `search_code` 142–222 | File absent at HEAD; **UNCOMMITTED** | Citation construction occurs within the function; pick a smaller labeled range. |
| 9 | Embedding jobs batched | `apps/api/app/workers/tasks.py`: `process_embedding` 325–492 | Function absent at HEAD; **UNCOMMITTED** | Long function spans multiple chunks. |
| 10 | Embedding cache reuse | `apps/api/app/modules/ingestion/embedding_store.py`: `persist_embedding` 18–37 | File absent at HEAD; **UNCOMMITTED** | Worker cache lookup in `process_embedding` is also relevant. |
| 11 | Natural-language keyword search | `apps/api/app/modules/ingestion/code_routes.py`: `search_code` 142–222 | File absent at HEAD; **UNCOMMITTED** | Select a bounded range covering query construction. |
| 12 | Keyword and semantic rank fusion | `apps/api/app/modules/ingestion/rank_fusion.py`: `reciprocal_rank_fusion` 5–16 | File absent at HEAD; **UNCOMMITTED** | Caller in `search_code` is also relevant. |
| 13 | Transient ingestion retries | `apps/api/app/workers/tasks.py`: `ingest_issue` 66–72, `index_repository` 312–322 | `ingest_issue` body exists at HEAD 65–71; `index_repository` absent; **MIXED** | Multiple worker types; review both. |
| 14 | Pending jobs republished | `apps/api/app/workers/dispatcher.py`: `dispatch_once` 15–92 | Exists at HEAD 14–47 but body differs; **UNCOMMITTED** | HEAD covers earlier issue/sync jobs, not current index/embedding dispatch. |
| 15 | Ambiguous: repository access checked | `code_routes.py`: `allowed_repository` 24–30; `github/enrollment.py`: `visible_github_repositories` 35–46; `workers/tasks.py`: `process_index` 162–306 | **MIXED**: enrollment function matches HEAD; other cited functions absent | Review multiple valid paths and label each explicitly. |
| 16 | Ambiguous: jobs completed | `workers/tasks.py`: `process_event` 18–52, `process_sync` 75–148, `process_index` 162–306, `process_embedding` 325–492 | **MIXED**: event/sync bodies match HEAD at 17–51 and 74–147; index/embedding absent | Decide which job types the question actually intends. |
| 17 | Negative: automatic pull-request generation | No implementation established; `workers/tasks.py` 127 filters pull-request items from issue sync | **UNVERIFIED NEGATIVE** in both HEAD and working tree | That filter does not prove absence of all generation; perform exhaustive commit-scoped review. |
| 18 | Negative: paid embedding call executed by worker | `workers/tasks.py`: `process_embedding` 360–363 refuses non-fake providers; `modules/ingestion/embeddings.py`: `OpenAIEmbeddingProvider.embed` 86–119 contains an adapter call | Both newer implementations absent at HEAD; **UNCOMMITTED / UNVERIFIED NEGATIVE** | The adapter exists; distinguish an adapter call from the disabled worker execution path. |

## Proposed backend source checkpoint — approval required

This is a review list, not an instruction to stage or commit. The goal is a coherent backend
indexing/search/evaluation checkpoint, not a full UI release. Existing working-tree changes may
contain unrelated hunks and must be reviewed before choosing exact contents.

Tracked modified files proposed for review and inclusion:

```text
.env.example
compose.yaml
apps/api/app/core/config.py
apps/api/app/domain/models.py
apps/api/app/main.py
apps/api/app/seed.py
apps/api/app/workers/dispatcher.py
apps/api/app/workers/tasks.py
apps/api/tests/conftest.py
apps/api/tests/test_auth_enrollment.py
apps/api/tests/test_config.py
```

New, currently untracked runtime and migration files proposed for inclusion:

```text
apps/api/alembic/versions/0003_code_index.py
apps/api/alembic/versions/0004_index_job_lease.py
apps/api/alembic/versions/0005_embedding_storage.py
apps/api/alembic/versions/0006_embedding_jobs.py
apps/api/app/core/index_logging.py
apps/api/app/infra/vector_type.py
apps/api/app/modules/github/source_client.py
apps/api/app/modules/ingestion/code_chunking.py
apps/api/app/modules/ingestion/code_collect.py
apps/api/app/modules/ingestion/code_persistence.py
apps/api/app/modules/ingestion/code_routes.py
apps/api/app/modules/ingestion/code_selection.py
apps/api/app/modules/ingestion/code_snapshot.py
apps/api/app/modules/ingestion/embedding_store.py
apps/api/app/modules/ingestion/embeddings.py
apps/api/app/modules/ingestion/rank_fusion.py
apps/api/app/modules/ingestion/semantic_search.py
```

New, currently untracked regression tests proposed for inclusion:

```text
apps/api/tests/test_code_collect.py
apps/api/tests/test_code_persistence.py
apps/api/tests/test_code_primitives.py
apps/api/tests/test_code_snapshot.py
apps/api/tests/test_code_workflow.py
apps/api/tests/test_embedding_workflow.py
apps/api/tests/test_embeddings.py
apps/api/tests/test_index_logging.py
apps/api/tests/test_index_metadata.py
apps/api/tests/test_lexical_diagnostic.py
apps/api/tests/test_postgres_scale.py
apps/api/tests/test_rank_fusion.py
apps/api/tests/test_retrieval_evaluation.py
apps/api/tests/test_seed_sequences.py
apps/api/tests/test_source_client.py
```

Evaluation harness and baseline inputs proposed for inclusion:

```text
apps/api/app/evaluation/__init__.py
apps/api/app/evaluation/compare_reports.py
apps/api/app/evaluation/lexical_diagnostic.py
apps/api/app/evaluation/postgres_scale.py
apps/api/app/evaluation/retrieval.py
apps/api/app/evaluation/verify_labels.py
apps/api/evaluation/README.md
apps/api/evaluation/repopilot-6349190.json
apps/api/evaluation/benchmark-v2-proposal.md
apps/api/evaluation/benchmark-v2-provenance.md
```

Review `README.md` and `docs/verification.md` separately for consistency with the final selected
scope; including historical result artifacts is a separate review choice. The evaluation tests
also reference the original baseline dataset, so it must accompany them. The current diagnostic
and browser-capture helpers hardcode the historical public repository/commit and must not be
presented as a general v2 runner without adaptation.

Explicitly excluded from this backend checkpoint: all `apps/web/` files, including the existing
sidebar/navigation edits, code-intelligence UI and proxy changes; `.env` and all other private
environment files; local databases, browser downloads, logs, caches and dependency directories;
unreviewed generated result files; the original `RepoPilot/` reference bundle and archive.
The UI files mix related and unrelated edits, so do not stage whole files merely to obtain a
backend checkpoint. Excluding the dashboard means the proposed commit does not represent the
full current end-to-end UI and associated historical verification is not a clean-checkout claim.

Migrations 0003–0006 and the ORM/worker/API changes form an interdependent chain; leaving out
untracked migrations or vector type breaks the checkpoint. PostgreSQL needs pgvector for 0005;
no new dependency or lockfile change is identified. Compose and `.env.example` carry optional
embedding configuration; private `.env` is excluded. Paid background generation remains
disabled and the provider has no enforceable spending cap. Secret filtering is incomplete.
The English lexical expressions lack matching indexes, and published source history has no
retention automation. Review exact hunks and test a clean isolated checkout before a commit.

A limited pattern scan of 112 candidate API/config text files reported one private-key marker:
`apps/api/tests/test_source_client.py` contains only a test string for the marker. This is not
comprehensive secret detection. Review all proposed files and generated reports, including
repository identifiers and any personal information, before staging anything.

## Disposable local evaluation design — not executed

1. After separate approval, select or create a real local commit containing the approved source;
   record its full commit SHA. A local Git tree hash or working-tree checksum is not a commit.
   Inspect that commit's code and construct a separately versioned v2 dataset with reviewed
   path/symbol/inclusive-line labels. Extend the evaluator for negative/no-answer questions before
   scoring them; its current recall code assumes at least one positive label.
2. Create a new, clearly named disposable PostgreSQL database. Never reuse the application
   database or existing snapshot; run the selected commit's Alembic migrations there. Tests
   currently drop tables, so the test database must be dedicated.
3. Build an injected local Git source client using `git ls-tree` and `git cat-file` or `git show`
   with argument arrays and the selected SHA. Supply tree/blob metadata from that exact commit,
   preserving Git blob hashes, modes, sizes and normalized relative paths. Feed the existing
   snapshot planner, source-selection, collection and chunking code; do not execute repository
   code. Add tests for truncated/oversized data, filtering and exact source-line slices.
4. In the disposable database, use test-only injected GitHub authorization and an isolated
   tenant/repository/session, then exercise the existing job, `process_index`, and persistence
   path. Let `publish_snapshot` generate actual UUIDs; read the resulting stored snapshot ID
   rather than inventing one. Assert commit, ownership, counts, atomic publication and visibility
   before running retrieval. Repeat access-revocation and cross-tenant tests with the fixture.
5. Run keyword and, if configured, deterministic fake embedding/hybrid retrieval through the
   existing authenticated API/test client. Adapt the evaluation harness to consume this test
   transport and v2 dataset; its present browser capture targets the old live commit. Report
   exact model and mode, metrics, per-query results, citation structure and limitations. Fake
   vector scores are mechanical only. Do not send data to a paid provider.
6. Verify local citations by comparing returned commit, path and line range with the Git object
   using `git show` and inclusive slices. The API can construct a GitHub-shaped URL, but a
   local-only commit is not necessarily present on GitHub: label such links **unresolved**, do not
   claim live GitHub citation verification, and do not publish the commit without separate
   permission. Publication and a real GitHub App reindex are separately approved actions.

None of these steps creates a new v2 benchmark or runs an evaluation in this preparation task.
