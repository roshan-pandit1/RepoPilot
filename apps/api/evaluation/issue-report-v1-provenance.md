# Issue-to-report v1 provenance

Dataset SHA-256: 416cbf9e46b9399cf78d118f581a882d16cf512da439d352d3af29674c447bf6
Git commit: 30705da4c044192cab4ac207e253ab8e8a1bd100
Git tree: beac4e3116133a810f679761e17a7441fa77c2d7
Cases: 19; scored: 16; unscored: 3; labels: 23

Git blobs, source selection, symbol ranges and chunk boundaries were checked locally.
No database snapshot or chunk UUID is assigned by this verification.

| Case | Path | Symbol | Label lines | Eligible chunk lines |
| --- | --- | --- | --- | --- |
| signature_exact | apps/api/app/modules/github/security.py | valid_signature | 6-8 | 6-8 |
| signature_natural | apps/api/app/modules/github/security.py | valid_signature | 6-8 | 6-8 |
| signature_natural | apps/api/app/api/v1/routes.py | webhook | 26-34 | 24-59 |
| oauth_callback | apps/api/app/modules/auth/routes.py | callback | 51-68 | 44-114 |
| installation_enrollment | apps/api/app/modules/github/enrollment.py | verified_installations | 17-32 | 17-32 |
| installation_enrollment | apps/api/app/modules/github/enrollment.py | enroll | 56-66 | 56-79 |
| repository_access | apps/api/app/api/v1/routes.py | authorized_repos | 68-79 | 68-79 |
| repository_access | apps/api/app/modules/github/issue_context.py | authorize | 73-105 | 73-105 |
| repository_sync | apps/api/app/workers/tasks.py | process_sync | 138-148 | 75-148 |
| index_incomplete_tree | apps/api/app/modules/ingestion/code_snapshot.py | plan_snapshot | 53-62 | 36-83 |
| index_lease | apps/api/app/workers/tasks.py | process_index | 184-190 | 162-281 |
| python_chunking | apps/api/app/modules/ingestion/code_chunking.py | chunk_python | 28-36 | 14-53 |
| embedding_cache | apps/api/app/workers/tasks.py | process_embedding | 411-424 | 325-444 |
| embedding_cache | apps/api/app/modules/ingestion/embedding_store.py | persist_embedding | 20-31 | 18-37 |
| embedding_idempotence | apps/api/app/modules/ingestion/embedding_store.py | persist_embedding | 28-36 | 18-37 |
| celery_redelivery | apps/api/app/workers/dispatcher.py | dispatch_once | 95-113 | 15-124 |
| celery_redelivery | apps/api/app/workers/tasks.py | investigate_issue | 756-767 | 756-767 |
| snapshot_publication | apps/api/app/modules/ingestion/code_persistence.py | publish_snapshot | 19-31 | 12-43 |
| citation_boundaries | apps/api/app/modules/ingestion/citations.py | github_citation | 8-16 | 8-16 |
| citation_boundaries | apps/api/app/modules/investigation/retrieval.py | load_verified_evidence | 85-105 | 85-105 |
| report_grounding | apps/api/app/modules/investigation/report_model.py | validate_draft | 249-260 | 227-271 |
| snapshot_unavailable | apps/api/app/modules/investigation/retrieval.py | validate_snapshot | 43-49 | 43-49 |
| snapshot_unavailable | apps/api/app/workers/tasks.py | process_investigation | 653-658 | 629-748 |

Labels are incomplete and do not establish diagnostic correctness.
The insufficient-information and negative candidate cases remain unscored.
