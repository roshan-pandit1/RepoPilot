# Sprint 5C1 production-v2 retrieval

Run: 3d44ea7dbd159dd9; database: repopilot_4f_disposable_68ed7b3fd6171439; snapshot: 95751038-f44e-4715-b4bd-932e446f457b
Dataset: issue-report-v1 (416cbf9e46b9399cf78d118f581a882d16cf512da439d352d3af29674c447bf6); commit: 30705da4c044192cab4ac207e253ab8e8a1bd100; Git tree: beac4e3116133a810f679761e17a7441fa77c2d7
Recall@1/3/5/10: 0.3750 / 0.5000 / 0.5625 / 0.7188
MRR: 0.5177; nDCG@10: 0.5469; labeled hits@10: 13/16
Direct retrieval p50/p95: 82.396/124.066 ms
Locally verified citations: 298/298

| Case | Outcome | Labeled ranks |
| --- | --- | --- |
| signature_exact | labeled_hit | 1 |
| signature_natural | labeled_hit | 2 |
| oauth_callback | labeled_hit | 1 |
| installation_enrollment | labeled_hit | 2, 10 |
| repository_access | no_labeled_hit_in_top_10 |  |
| repository_sync | labeled_hit | 1 |
| index_incomplete_tree | labeled_hit | 10 |
| index_lease | labeled_hit | 1 |
| python_chunking | no_labeled_hit_in_top_10 |  |
| embedding_cache | labeled_hit | 4 |
| embedding_idempotence | labeled_hit | 1 |
| celery_redelivery | labeled_hit | 2, 4 |
| snapshot_publication | labeled_hit | 10 |
| citation_boundaries | no_labeled_hit_in_top_10 |  |
| report_grounding | labeled_hit | 1 |
| snapshot_unavailable | labeled_hit | 3 |
| insufficient_details | unscored_candidates | unscored |
| unreviewed_negative | no_evidence | unscored |
| malicious_prompt | no_evidence | unscored |

Incomplete synthetic labels; unlabeled results are not judged.
Latency measures direct retrieval only; it is not an end-to-end or load benchmark.
Authentication and worker behavior require separate regression tests.
