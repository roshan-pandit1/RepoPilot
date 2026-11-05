# Sprint 5C1 issue-retrieval comparison

Dataset: issue-report-v1 (416cbf9e46b9399cf78d118f581a882d16cf512da439d352d3af29674c447bf6)
Commit: 30705da4c044192cab4ac207e253ab8e8a1bd100; snapshot: 95751038-f44e-4715-b4bd-932e446f457b; database: repopilot_4f_disposable_68ed7b3fd6171439
Runs: 3d44ea7dbd159dd9 (terms-v2) and 65b99a0ad44ffeec (cie-v1-offline)

Implementation files with different or newly recorded hashes: app/modules/investigation/code_intelligence.py

| Metric | Baseline | Candidate |
| --- | ---: | ---: |
| Recall@1 | 0.3750 | 0.3750 |
| Recall@3 | 0.5000 | 0.5000 |
| Recall@5 | 0.5625 | 0.5625 |
| Recall@10 | 0.7188 | 0.7188 |
| MRR | 0.5177 | 0.5177 |
| nDCG@10 | 0.5469 | 0.5469 |
| Labeled hits@10 | 13.0000 | 13.0000 |
| Zero-result cases | 2.0000 | 2.0000 |
| Evidence items | 298.0000 | 298.0000 |
| Direct retrieval p50 ms | 82.3960 | 82.3960 |
| Direct retrieval p95 ms | 124.0660 | 124.0660 |

| Case | Baseline labeled ranks | Candidate labeled ranks |
| --- | --- | --- |
| signature_exact | 1 | 1 |
| signature_natural | 2 | 2 |
| oauth_callback | 1 | 1 |
| installation_enrollment | 2, 10 | 2, 10 |
| repository_access | none | none |
| repository_sync | 1 | 1 |
| index_incomplete_tree | 10 | 10 |
| index_lease | 1 | 1 |
| python_chunking | none | none |
| embedding_cache | 4 | 4 |
| embedding_idempotence | 1 | 1 |
| celery_redelivery | 2, 4 | 2, 4 |
| snapshot_publication | 10 | 10 |
| citation_boundaries | none | none |
| report_grounding | 1 | 1 |
| snapshot_unavailable | 3 | 3 |
| insufficient_details | unscored | unscored |
| unreviewed_negative | unscored | unscored |
| malicious_prompt | unscored | unscored |

Incomplete synthetic labels; unlabeled candidates are not confirmed irrelevant.
Latency measures direct retrieval and is not an end-to-end or load benchmark.
Retrieval latency is inherited from the earlier terms-v2 run; CIE analysis is timed separately.

Offline CIE analysis p50/p95: 17.011/42.486 ms.
Findings: 4/19 cases. Sample traced Python peak: 2604929 bytes.
