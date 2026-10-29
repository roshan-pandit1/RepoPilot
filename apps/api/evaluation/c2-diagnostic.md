# C2 read-only PostgreSQL candidate comparison

Pinned commit: `63491908290e6874dbaaf2b15c2a96473aad1324`; published snapshot chunks: 278.

This operator diagnostic compared the unchanged labels against SQL candidate strategies in a read-only transaction. It does not use the authenticated API and is not the after-deployment API benchmark. Historical-match counts are limited to this repository and tenant. Recall uses one definition-anchor label per query.

| Strategy | Recall@1 | @3 | @5 | @10 | MRR | nDCG@10 | Zero results |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 20 |
| english_or | 0.250 | 0.600 | 0.600 | 0.800 | 0.434 | 0.521 | 0 |
| english_or_boost | 0.250 | 0.600 | 0.600 | 0.800 | 0.434 | 0.521 | 0 |

| Query | Baseline history candidates | Baseline published candidates | English OR published candidates | English OR + symbol boost relevant ranks |
| --- | ---: | ---: | ---: | --- |
| sync | 0 | 0 | 61 | 2 |
| signature | 0 | 0 | 33 | 9 |
| webhook | 0 | 0 | 54 | 1 |
| dispatch | 0 | 0 | 45 | 2 |
| authorization | 0 | 0 | 50 | none |
| tenant | 0 | 0 | 66 | none |
| csrf | 0 | 0 | 54 | 2 |
| principal | 0 | 0 | 48 | 2 |
| login | 0 | 0 | 69 | none |
| callback | 0 | 0 | 69 | 1 |
| logout | 0 | 0 | 97 | none |
| enroll | 0 | 0 | 92 | 1 |
| choose | 0 | 0 | 69 | 1 |
| installations | 0 | 0 | 92 | 7 |
| visible | 0 | 0 | 96 | 9 |
| accept | 0 | 0 | 41 | 2 |
| process | 0 | 0 | 53 | 3 |
| revoke | 0 | 0 | 61 | 3 |
| health | 0 | 0 | 16 | 1 |
| delivery | 0 | 0 | 29 | 7 |
