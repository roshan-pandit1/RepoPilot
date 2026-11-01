# Sprint 5C1 issue-retrieval comparison

Dataset: issue-report-v1 (416cbf9e46b9399cf78d118f581a882d16cf512da439d352d3af29674c447bf6)
Commit: 30705da4c044192cab4ac207e253ab8e8a1bd100; snapshot: 1a8e0d9e-1cf1-4e0a-9cac-f8ced23f1694; database: repopilot_4f_disposable_4f762b71ae8d9569
Runs: eda70e4b43a14eb6 (terms-v1) and 1fdf3b79925eaede (evaluation-body-first)

Implementation files with different or newly recorded hashes: app/evaluation/issue_retrieval_candidates.py, app/evaluation/issue_retrieval_replay.py

| Metric | Baseline | Candidate |
| --- | ---: | ---: |
| Recall@1 | 0.3750 | 0.3750 |
| Recall@3 | 0.5000 | 0.3750 |
| Recall@5 | 0.5625 | 0.5000 |
| Recall@10 | 0.6250 | 0.6562 |
| MRR | 0.5141 | 0.4922 |
| nDCG@10 | 0.5205 | 0.5021 |
| Labeled hits@10 | 12.0000 | 12.0000 |
| Zero-result cases | 2.0000 | 2.0000 |
| Evidence items | 226.0000 | 288.0000 |
| Direct retrieval p50 ms | 54.5200 | 74.5170 |
| Direct retrieval p95 ms | 97.6720 | 132.7270 |

| Case | Baseline labeled ranks | Candidate labeled ranks |
| --- | --- | --- |
| signature_exact | 1 | 1 |
| signature_natural | 2 | 4 |
| oauth_callback | 1 | 5 |
| installation_enrollment | 2 | 1, 6 |
| repository_access | none | none |
| repository_sync | 1 | 1 |
| index_incomplete_tree | 7 | 10 |
| index_lease | 1 | 1 |
| python_chunking | none | none |
| embedding_cache | 4 | 8 |
| embedding_idempotence | 1 | 1 |
| celery_redelivery | 2, 4 | 1, 6 |
| snapshot_publication | none | none |
| citation_boundaries | none | none |
| report_grounding | 1 | 1 |
| snapshot_unavailable | 3 | 5 |
| insufficient_details | unscored | unscored |
| unreviewed_negative | unscored | unscored |
| malicious_prompt | unscored | unscored |

Incomplete synthetic labels; unlabeled candidates are not confirmed irrelevant.
Latency measures direct retrieval and is not an end-to-end or load benchmark.
