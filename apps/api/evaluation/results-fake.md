# Retrieval evaluation

Repository: roshan-pandit1/RepoPilot
Commit: 63491908290e6874dbaaf2b15c2a96473aad1324
Provider: fake; model: deterministic-hash; dimensions: 32; limit: 10

Fake-vector semantic and hybrid results: **MECHANICAL TEST ONLY**. Real semantic quality has not been measured.
Binary relevance uses incomplete, manually reviewed labels; ranks are not comprehensive judgments.

## keyword

Recall @1/@3/@5/@10: 0.000 / 0.000 / 0.000 / 0.000
MRR: 0.000; nDCG@10: 0.000; no relevant: 20
Fallbacks: 0; returned results: 0; invalid citations: 0 (no citation evidence if no results); latency p50/p95: 1206.9/1774.4 ms

| Query | Relevant ranks | Effective mode |
| --- | --- | --- |
| sync | none | keyword |
| signature | none | keyword |
| webhook | none | keyword |
| dispatch | none | keyword |
| authorization | none | keyword |
| tenant | none | keyword |
| csrf | none | keyword |
| principal | none | keyword |
| login | none | keyword |
| callback | none | keyword |
| logout | none | keyword |
| enroll | none | keyword |
| choose | none | keyword |
| installations | none | keyword |
| visible | none | keyword |
| accept | none | keyword |
| process | none | keyword |
| revoke | none | keyword |
| health | none | keyword |
| delivery | none | keyword |

Representative misses (unlabeled results are not necessarily irrelevant):
- sync: top result none or invalid citation
- signature: top result none or invalid citation
- webhook: top result none or invalid citation

## semantic

Recall @1/@3/@5/@10: 0.050 / 0.050 / 0.100 / 0.150
MRR: 0.070; nDCG@10: 0.088; no relevant: 17
Fallbacks: 0; returned results: 200; invalid citations: 0 (no citation evidence if no results); latency p50/p95: 1223.0/1595.5 ms

| Query | Relevant ranks | Effective mode |
| --- | --- | --- |
| sync | none | semantic |
| signature | none | semantic |
| webhook | none | semantic |
| dispatch | none | semantic |
| authorization | none | semantic |
| tenant | none | semantic |
| csrf | none | semantic |
| principal | none | semantic |
| login | none | semantic |
| callback | none | semantic |
| logout | none | semantic |
| enroll | 1 | semantic |
| choose | none | semantic |
| installations | 7 | semantic |
| visible | none | semantic |
| accept | none | semantic |
| process | none | semantic |
| revoke | 4 | semantic |
| health | none | semantic |
| delivery | none | semantic |

Representative misses (unlabeled results are not necessarily irrelevant):
- sync: top result apps/api/tests/test_ingestion.py
- signature: top result apps/api/app/modules/github/client.py
- webhook: top result apps/api/tests/test_github_client.py

## hybrid

Recall @1/@3/@5/@10: 0.050 / 0.050 / 0.100 / 0.150
MRR: 0.070; nDCG@10: 0.088; no relevant: 17
Fallbacks: 0; returned results: 200; invalid citations: 0 (no citation evidence if no results); latency p50/p95: 1213.5/1796.1 ms

| Query | Relevant ranks | Effective mode |
| --- | --- | --- |
| sync | none | hybrid |
| signature | none | hybrid |
| webhook | none | hybrid |
| dispatch | none | hybrid |
| authorization | none | hybrid |
| tenant | none | hybrid |
| csrf | none | hybrid |
| principal | none | hybrid |
| login | none | hybrid |
| callback | none | hybrid |
| logout | none | hybrid |
| enroll | 1 | hybrid |
| choose | none | hybrid |
| installations | 7 | hybrid |
| visible | none | hybrid |
| accept | none | hybrid |
| process | none | hybrid |
| revoke | 4 | hybrid |
| health | none | hybrid |
| delivery | none | hybrid |

Representative misses (unlabeled results are not necessarily irrelevant):
- sync: top result apps/api/tests/test_ingestion.py
- signature: top result apps/api/app/modules/github/client.py
- webhook: top result apps/api/tests/test_github_client.py
