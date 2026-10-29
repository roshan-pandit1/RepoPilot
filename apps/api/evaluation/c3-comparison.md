# C2 retrieval before and after

Repository: roshan-pandit1/RepoPilot; commit: 63491908290e6874dbaaf2b15c2a96473aad1324

Same 20 questions, incomplete definition-anchor labels, and limit 10. Fake semantic and hybrid results are **MECHANICAL TEST ONLY**. Real semantic quality is not measured.
Latencies include authorization and network time; a single run of 20 queries per mode is not a load benchmark.

## keyword

| Metric | Before | After |
| --- | ---: | ---: |
| Recall@1 | 0.250 | 0.250 |
| Recall@3 | 0.600 | 0.600 |
| Recall@5 | 0.600 | 0.600 |
| Recall@10 | 0.800 | 0.800 |
| MRR | 0.434 | 0.434 |
| nDCG@10 | 0.521 | 0.521 |
| Queries with no labeled result | 4 | 4 |
| Queries with zero results | 0 | 0 |
| Fallbacks | 0 | 0 |
| Results returned | 198 | 198 |
| Invalid citations | 0 | 0 |
| p50 ms | 1301.600 | 1150.900 |
| p95 ms | 1789.300 | 1426.700 |

| Query | Before labeled ranks | After labeled ranks | Before returned | After returned |
| --- | --- | --- | ---: | ---: |
| sync | 2 | 2 | 10 | 10 |
| signature | 9 | 9 | 10 | 10 |
| webhook | 1 | 1 | 10 | 10 |
| dispatch | 2 | 2 | 10 | 10 |
| authorization | none | none | 10 | 10 |
| tenant | none | none | 10 | 10 |
| csrf | 2 | 2 | 10 | 10 |
| principal | 2 | 2 | 10 | 10 |
| login | none | none | 10 | 10 |
| callback | 1 | 1 | 10 | 10 |
| logout | none | none | 10 | 10 |
| enroll | 1 | 1 | 10 | 10 |
| choose | 1 | 1 | 10 | 10 |
| installations | 7 | 7 | 10 | 10 |
| visible | 9 | 9 | 10 | 10 |
| accept | 2 | 2 | 10 | 10 |
| process | 3 | 3 | 10 | 10 |
| revoke | 3 | 3 | 10 | 10 |
| health | 1 | 1 | 8 | 8 |
| delivery | 7 | 7 | 10 | 10 |

## semantic

| Metric | Before | After |
| --- | ---: | ---: |
| Recall@1 | 0.050 | 0.050 |
| Recall@3 | 0.050 | 0.050 |
| Recall@5 | 0.100 | 0.100 |
| Recall@10 | 0.150 | 0.150 |
| MRR | 0.070 | 0.070 |
| nDCG@10 | 0.088 | 0.088 |
| Queries with no labeled result | 17 | 17 |
| Queries with zero results | 0 | 0 |
| Fallbacks | 0 | 0 |
| Results returned | 200 | 200 |
| Invalid citations | 0 | 0 |
| p50 ms | 1223.400 | 1210.800 |
| p95 ms | 1446.300 | 1426 |

| Query | Before labeled ranks | After labeled ranks | Before returned | After returned |
| --- | --- | --- | ---: | ---: |
| sync | none | none | 10 | 10 |
| signature | none | none | 10 | 10 |
| webhook | none | none | 10 | 10 |
| dispatch | none | none | 10 | 10 |
| authorization | none | none | 10 | 10 |
| tenant | none | none | 10 | 10 |
| csrf | none | none | 10 | 10 |
| principal | none | none | 10 | 10 |
| login | none | none | 10 | 10 |
| callback | none | none | 10 | 10 |
| logout | none | none | 10 | 10 |
| enroll | 1 | 1 | 10 | 10 |
| choose | none | none | 10 | 10 |
| installations | 7 | 7 | 10 | 10 |
| visible | none | none | 10 | 10 |
| accept | none | none | 10 | 10 |
| process | none | none | 10 | 10 |
| revoke | 4 | 4 | 10 | 10 |
| health | none | none | 10 | 10 |
| delivery | none | none | 10 | 10 |

## hybrid

| Metric | Before | After |
| --- | ---: | ---: |
| Recall@1 | 0.050 | 0.050 |
| Recall@3 | 0.150 | 0.150 |
| Recall@5 | 0.450 | 0.450 |
| Recall@10 | 0.700 | 0.700 |
| MRR | 0.188 | 0.188 |
| nDCG@10 | 0.305 | 0.305 |
| Queries with no labeled result | 6 | 6 |
| Queries with zero results | 0 | 0 |
| Fallbacks | 0 | 0 |
| Results returned | 200 | 200 |
| Invalid citations | 0 | 0 |
| p50 ms | 1241 | 1267.200 |
| p95 ms | 1496.800 | 1783.700 |

| Query | Before labeled ranks | After labeled ranks | Before returned | After returned |
| --- | --- | --- | ---: | ---: |
| sync | 6 | 6 | 10 | 10 |
| signature | none | none | 10 | 10 |
| webhook | 10 | 10 | 10 | 10 |
| dispatch | 4 | 4 | 10 | 10 |
| authorization | 5 | 5 | 10 | 10 |
| tenant | none | none | 10 | 10 |
| csrf | 10 | 10 | 10 | 10 |
| principal | none | none | 10 | 10 |
| login | 10 | 10 | 10 | 10 |
| callback | 3 | 3 | 10 | 10 |
| logout | none | none | 10 | 10 |
| enroll | 1 | 1 | 10 | 10 |
| choose | 9 | 9 | 10 | 10 |
| installations | 4 | 4 | 10 | 10 |
| visible | none | none | 10 | 10 |
| accept | 5 | 5 | 10 | 10 |
| process | 5 | 5 | 10 | 10 |
| revoke | 2 | 2 | 10 | 10 |
| health | 4 | 4 | 10 | 10 |
| delivery | none | none | 10 | 10 |

Citation validation checks URL structure, commit, path and inclusive line fragment; it does not independently open every GitHub link.
Authorization evidence and test counts are recorded separately in docs/verification.md.
Labels are incomplete; the pinned commit predates the indexing, chunking, citation and embedding modules.
