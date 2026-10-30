# Issue-to-code and mock-report evaluation

Dataset: issue-report-v1 (416cbf9e46b9399cf78d118f581a882d16cf512da439d352d3af29674c447bf6)
Commit: 30705da4c044192cab4ac207e253ab8e8a1bd100; Git tree: beac4e3116133a810f679761e17a7441fa77c2d7; snapshot: 1a8e0d9e-1cf1-4e0a-9cac-f8ced23f1694
Database: repopilot_4f_disposable_4f762b71ae8d9569; evaluation time: 2026-10-29T16:43:30.566125+00:00
Scored/unscored: 16/3
Recall@1/3/5/10: 0.375/0.500/0.562/0.625
MRR: 0.514; nDCG@10: 0.521; labeled hits@10: 12/16
Zero-result cases: 2; evidence items: 226
Direct-worker p50/p95: 50.798/92.294 ms
Reports: 19/19 schema-valid; 17/17 references valid; 19/19 duplicate replays idempotent
Grounding probes: 10/10 passed

| Case | Category | Outcome | Relevant ranks | Evidence |
| --- | --- | --- | --- | ---: |
| signature_exact | webhook | labeled_hit | 1 | 18 |
| signature_natural | webhook | labeled_hit | 2 | 10 |
| oauth_callback | authentication | labeled_hit | 1 | 15 |
| installation_enrollment | authorization | labeled_hit | 2 | 18 |
| repository_access | authorization | no_labeled_hit_in_top_10 | none | 10 |
| repository_sync | synchronization | labeled_hit | 1 | 18 |
| index_incomplete_tree | indexing | labeled_hit | 7 | 10 |
| index_lease | indexing | labeled_hit | 1 | 20 |
| python_chunking | chunking | no_labeled_hit_in_top_10 | none | 10 |
| embedding_cache | embedding | labeled_hit | 4 | 10 |
| embedding_idempotence | embedding | labeled_hit | 1 | 20 |
| celery_redelivery | dispatch | labeled_hit | 2, 4 | 10 |
| snapshot_publication | indexing | no_labeled_hit_in_top_10 | none | 10 |
| citation_boundaries | citations | no_labeled_hit_in_top_10 | none | 10 |
| report_grounding | reports | labeled_hit | 1 | 17 |
| snapshot_unavailable | evidence | labeled_hit | 3 | 10 |
| insufficient_details | insufficient | unscored_candidates | unscored | 10 |
| unreviewed_negative | negative | no_evidence | unscored | 0 |
| malicious_prompt | security | no_evidence | unscored | 0 |

Synthetic issues and incomplete labels; unlabeled results are not necessarily irrelevant.
Negative and insufficient cases are unscored.
Direct workers and mocked GitHub, not real Celery or AI reasoning.
Citations checked against local Git blobs; remote GitHub resolution was not checked.
