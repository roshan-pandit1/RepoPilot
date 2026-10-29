# Retrieval evaluation

Repository: roshan-pandit1/RepoPilot
Commit: 956a4f92983b222ce179891bbde39cb49a2022b2
Provider: disabled; model: None; dimensions: None; limit: 10

Fake-vector semantic and hybrid results: **MECHANICAL TEST ONLY**. Real semantic quality has not been measured.
Binary relevance uses incomplete, manually reviewed labels; ranks are not comprehensive judgments.

## keyword

Recall @1/@3/@5/@10: 0.125 / 0.318 / 0.443 / 0.510
MRR: 0.404; nDCG@10: 0.367; no relevant: 4
Fallbacks: 0; returned results: 160; invalid citations: 0 (no citation evidence if no results); latency p50/p95: 27.0/61.7 ms

| Query | Relevant ranks | Effective mode |
| --- | --- | --- |
| sessions | 1 | keyword |
| access | none | keyword |
| signature | 3 | keyword |
| snapshot | none | keyword |
| index | 2, 9 | keyword |
| chunking | none | keyword |
| screening | 4 | keyword |
| citations | none | keyword |
| embedding_jobs | 4 | keyword |
| embedding_cache | 2 | keyword |
| keyword | 1 | keyword |
| fusion | 1, 8 | keyword |
| retry | 2, 5 | keyword |
| dispatch | 2 | keyword |
| access_ambiguous | 2 | keyword |
| completion_ambiguous | 8 | keyword |

Representative misses (unlabeled results are not necessarily irrelevant):
- access: top result apps/api/app/workers/tasks.py
- snapshot: top result apps/api/app/workers/tasks.py
- chunking: top result apps/api/app/modules/ingestion/code_routes.py


Local Git blob citation validation passed; remote commit availability is unverified. Two negative candidates remain unscored.
