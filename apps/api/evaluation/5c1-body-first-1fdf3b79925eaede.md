# Sprint 5C1 body-first retrieval

Run: 1fdf3b79925eaede; database: repopilot_4f_disposable_4f762b71ae8d9569; snapshot: 1a8e0d9e-1cf1-4e0a-9cac-f8ced23f1694
Dataset: issue-report-v1 (416cbf9e46b9399cf78d118f581a882d16cf512da439d352d3af29674c447bf6); commit: 30705da4c044192cab4ac207e253ab8e8a1bd100; Git tree: beac4e3116133a810f679761e17a7441fa77c2d7
Recall@1/3/5/10: 0.3750 / 0.3750 / 0.5000 / 0.6562
MRR: 0.4922; nDCG@10: 0.5021; labeled hits@10: 12/16
Direct retrieval p50/p95: 74.517/132.727 ms
Locally verified citations: 288/288

| Case | Outcome | Labeled ranks |
| --- | --- | --- |
| signature_exact | labeled_hit | 1 |
| signature_natural | labeled_hit | 4 |
| oauth_callback | labeled_hit | 5 |
| installation_enrollment | labeled_hit | 1, 6 |
| repository_access | no_labeled_hit_in_top_10 |  |
| repository_sync | labeled_hit | 1 |
| index_incomplete_tree | labeled_hit | 10 |
| index_lease | labeled_hit | 1 |
| python_chunking | no_labeled_hit_in_top_10 |  |
| embedding_cache | labeled_hit | 8 |
| embedding_idempotence | labeled_hit | 1 |
| celery_redelivery | labeled_hit | 1, 6 |
| snapshot_publication | no_labeled_hit_in_top_10 |  |
| citation_boundaries | no_labeled_hit_in_top_10 |  |
| report_grounding | labeled_hit | 1 |
| snapshot_unavailable | labeled_hit | 5 |
| insufficient_details | unscored_candidates | unscored |
| unreviewed_negative | no_evidence | unscored |
| malicious_prompt | no_evidence | unscored |

Incomplete synthetic labels; unlabeled results are not judged.
Latency measures direct retrieval only; it is not an end-to-end or load benchmark.
Authentication and worker behavior require separate regression tests.
