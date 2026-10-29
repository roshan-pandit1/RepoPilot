# Retrieval evaluation

Repository: roshan-pandit1/RepoPilot
Commit: 63491908290e6874dbaaf2b15c2a96473aad1324
Provider: fake; model: deterministic-hash; dimensions: 32; limit: 10

Fake-vector semantic and hybrid results: **MECHANICAL TEST ONLY**. Real semantic quality has not been measured.
Binary relevance uses incomplete, manually reviewed labels; ranks are not comprehensive judgments.

## keyword

Recall @1/@3/@5/@10: 0.250 / 0.600 / 0.600 / 0.800
MRR: 0.434; nDCG@10: 0.521; no relevant: 4
Fallbacks: 0; returned results: 198; invalid citations: 0 (no citation evidence if no results); latency p50/p95: 1150.9/1426.7 ms

| Query | Relevant ranks | Effective mode |
| --- | --- | --- |
| sync | 2 | keyword |
| signature | 9 | keyword |
| webhook | 1 | keyword |
| dispatch | 2 | keyword |
| authorization | none | keyword |
| tenant | none | keyword |
| csrf | 2 | keyword |
| principal | 2 | keyword |
| login | none | keyword |
| callback | 1 | keyword |
| logout | none | keyword |
| enroll | 1 | keyword |
| choose | 1 | keyword |
| installations | 7 | keyword |
| visible | 9 | keyword |
| accept | 2 | keyword |
| process | 3 | keyword |
| revoke | 3 | keyword |
| health | 1 | keyword |
| delivery | 7 | keyword |

Representative misses (unlabeled results are not necessarily irrelevant):
- authorization: top result apps/api/app/modules/github/enrollment.py
- tenant: top result apps/api/alembic/versions/0001_foundation.py
- login: top result apps/api/app/modules/auth/routes.py

## semantic

Recall @1/@3/@5/@10: 0.050 / 0.050 / 0.100 / 0.150
MRR: 0.070; nDCG@10: 0.088; no relevant: 17
Fallbacks: 0; returned results: 200; invalid citations: 0 (no citation evidence if no results); latency p50/p95: 1210.8/1426.0 ms

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

Recall @1/@3/@5/@10: 0.050 / 0.150 / 0.450 / 0.700
MRR: 0.188; nDCG@10: 0.305; no relevant: 6
Fallbacks: 0; returned results: 200; invalid citations: 0 (no citation evidence if no results); latency p50/p95: 1267.2/1783.7 ms

| Query | Relevant ranks | Effective mode |
| --- | --- | --- |
| sync | 6 | hybrid |
| signature | none | hybrid |
| webhook | 10 | hybrid |
| dispatch | 4 | hybrid |
| authorization | 5 | hybrid |
| tenant | none | hybrid |
| csrf | 10 | hybrid |
| principal | none | hybrid |
| login | 10 | hybrid |
| callback | 3 | hybrid |
| logout | none | hybrid |
| enroll | 1 | hybrid |
| choose | 9 | hybrid |
| installations | 4 | hybrid |
| visible | none | hybrid |
| accept | 5 | hybrid |
| process | 5 | hybrid |
| revoke | 2 | hybrid |
| health | 4 | hybrid |
| delivery | none | hybrid |

Representative misses (unlabeled results are not necessarily irrelevant):
- signature: top result apps/api/app/smoke.py
- tenant: top result apps/api/tests/test_ingestion.py
- principal: top result apps/api/app/infra/database.py
