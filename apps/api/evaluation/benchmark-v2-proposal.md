# Benchmark v2 proposal — NOT A GROUNDED DATASET

The current checkout has no committed Git revision containing the newer indexing, chunking,
search, or embedding modules. The following are review candidates from the working tree, not
verified commit-pinned labels. Do not mix them into `repopilot-6349190.json` or score them as
ground truth. No repository has been reindexed for this proposal.

| Proposed question | Working-tree evidence to review |
| --- | --- |
| How are GitHub login sessions created and revoked? | `app/modules/auth/routes.py` `callback`, `logout` |
| How is current repository access enforced? | `app/modules/ingestion/code_routes.py` `allowed_repository` |
| How are GitHub webhook signatures checked? | `app/modules/github/security.py` `valid_signature` |
| How is a pinned repository snapshot planned? | `app/modules/ingestion/code_snapshot.py` `plan_snapshot` |
| Where are indexing jobs claimed and published? | `app/workers/tasks.py` `process_index` |
| How are Python definitions split into source chunks? | `app/modules/ingestion/code_chunking.py` `chunk_python` |
| How are source files screened before indexing? | `app/modules/ingestion/code_collect.py` `collect_source` |
| Where are commit-pinned GitHub citations built? | `app/modules/ingestion/code_routes.py` `search_code` |
| How are embedding jobs processed in batches? | `app/workers/tasks.py` `process_embedding` |
| Where is embedding cache reuse recorded? | `app/modules/ingestion/embedding_store.py` `persist_embedding` |
| How does keyword search handle natural language? | `app/modules/ingestion/code_routes.py` `search_code` |
| How are keyword and semantic ranks combined? | `app/modules/ingestion/rank_fusion.py` `reciprocal_rank_fusion` |
| How are transient ingestion failures retried? | `app/workers/tasks.py` `ingest_issue`, `index_repository` |
| How are pending jobs republished safely? | `app/workers/dispatcher.py` `dispatch_once` |
| Ambiguous: Where is repository access checked? | Review API, GitHub enrollment and worker checks as separate relevance labels. |
| Ambiguous: Where are jobs completed? | Review index, embedding and issue worker completion paths separately. |
| Negative candidate: Where are pull requests automatically generated? | Requires exhaustive review of a chosen committed snapshot before asserting no answer. |
| Negative candidate: Where is a remote paid embedding call executed by the worker? | Requires exhaustive review of a chosen committed snapshot and its configuration before asserting no answer. |

To finalize: select an existing commit that contains these files, inspect the exact source at
that SHA, add line-anchored labels and rationales, independently review negative judgments, and
store a separate versioned dataset. A benchmark against the app then requires an authorized
snapshot at that commit; obtain explicit approval before creating or publishing it. Never replace
the original benchmark or use working-tree line numbers as commit citations.
