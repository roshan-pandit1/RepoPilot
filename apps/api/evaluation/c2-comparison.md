# C2 retrieval before and after

Repository: roshan-pandit1/RepoPilot; commit: 63491908290e6874dbaaf2b15c2a96473aad1324

Same 20 questions, incomplete definition-anchor labels, and limit 10. Fake semantic and hybrid results are **MECHANICAL TEST ONLY**. Real semantic quality is not measured.
Latencies include authorization and network time; a single run of 20 queries per mode is not a load benchmark.

## keyword

| Metric | Before | After |
| --- | ---: | ---: |
| Recall@1 | 0.000 | 0.250 |
| Recall@3 | 0.000 | 0.600 |
| Recall@5 | 0.000 | 0.600 |
| Recall@10 | 0.000 | 0.800 |
| MRR | 0 | 0.434 |
| nDCG@10 | 0.000 | 0.521 |
| Queries with no labeled result | 20 | 4 |
| Queries with zero results | 20 | 0 |
| Fallbacks | 0 | 0 |
| Results returned | 0 | 198 |
| Invalid citations | 0 | 0 |
| p50 ms | 1206.900 | 1301.600 |
| p95 ms | 1774.400 | 1789.300 |

| Query | Before labeled ranks | After labeled ranks | Before returned | After returned |
| --- | --- | --- | ---: | ---: |
| sync | none | 2 | 0 | 10 |
| signature | none | 9 | 0 | 10 |
| webhook | none | 1 | 0 | 10 |
| dispatch | none | 2 | 0 | 10 |
| authorization | none | none | 0 | 10 |
| tenant | none | none | 0 | 10 |
| csrf | none | 2 | 0 | 10 |
| principal | none | 2 | 0 | 10 |
| login | none | none | 0 | 10 |
| callback | none | 1 | 0 | 10 |
| logout | none | none | 0 | 10 |
| enroll | none | 1 | 0 | 10 |
| choose | none | 1 | 0 | 10 |
| installations | none | 7 | 0 | 10 |
| visible | none | 9 | 0 | 10 |
| accept | none | 2 | 0 | 10 |
| process | none | 3 | 0 | 10 |
| revoke | none | 3 | 0 | 10 |
| health | none | 1 | 0 | 8 |
| delivery | none | 7 | 0 | 10 |

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
| p50 ms | 1223 | 1223.400 |
| p95 ms | 1595.500 | 1446.300 |

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
| Recall@3 | 0.050 | 0.150 |
| Recall@5 | 0.100 | 0.450 |
| Recall@10 | 0.150 | 0.700 |
| MRR | 0.070 | 0.188 |
| nDCG@10 | 0.088 | 0.305 |
| Queries with no labeled result | 17 | 6 |
| Queries with zero results | 0 | 0 |
| Fallbacks | 0 | 0 |
| Results returned | 200 | 200 |
| Invalid citations | 0 | 0 |
| p50 ms | 1213.500 | 1241 |
| p95 ms | 1796.100 | 1496.800 |

| Query | Before labeled ranks | After labeled ranks | Before returned | After returned |
| --- | --- | --- | ---: | ---: |
| sync | none | 6 | 10 | 10 |
| signature | none | none | 10 | 10 |
| webhook | none | 10 | 10 | 10 |
| dispatch | none | 4 | 10 | 10 |
| authorization | none | 5 | 10 | 10 |
| tenant | none | none | 10 | 10 |
| csrf | none | 10 | 10 | 10 |
| principal | none | none | 10 | 10 |
| login | none | 10 | 10 | 10 |
| callback | none | 3 | 10 | 10 |
| logout | none | none | 10 | 10 |
| enroll | 1 | 1 | 10 | 10 |
| choose | none | 9 | 10 | 10 |
| installations | 7 | 4 | 10 | 10 |
| visible | none | none | 10 | 10 |
| accept | none | 5 | 10 | 10 |
| process | none | 5 | 10 | 10 |
| revoke | 4 | 2 | 10 | 10 |
| health | none | 4 | 10 | 10 |
| delivery | none | none | 10 | 10 |

Before keyword returned zero citations, so its zero invalid count did not validate any citations.
Citation validation checks URL structure, commit, path and inclusive line fragment; it does not independently open every GitHub link.
Authorization evidence and test counts are recorded separately in docs/verification.md.
Labels are incomplete; the pinned commit predates the indexing, chunking, citation and embedding modules.
