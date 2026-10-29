# C3 PostgreSQL generated-corpus scale test

Synthetic temporary tables on a disposable PostgreSQL database; 3 fixed queries, 12 executions per query per condition, no app data and no paid calls. The query reproduces the C2 lexical expressions, owner and snapshot predicates, ranking, OR across joined tables and limit, but uses simplified integer IDs and projections. Each condition has 36 wall-clock samples; p95 is a small-sample nearest-rank statistic and p99 is not reported. Cache warmup/order and generated source distribution limit generalization. CPU and total memory were not measured. A three-second timeout was used for search and EXPLAIN.

| Total chunks | Eligible snapshot chunks | Indexes | Samples | Timeouts | p50 ms | p95 ms | Total index bytes | Candidate build seconds |
| ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1000 | 800 | existing_indexes | 36 | 0 | 5.881 | 11.066 | 172032 | 0.000 |
| 1000 | 800 | candidate_english_gin | 36 | 0 | 6.136 | 10.877 | 270336 | 0.005 |
| 10000 | 8000 | existing_indexes | 36 | 0 | 55.416 | 112.333 | 1212416 | 0.000 |
| 10000 | 8000 | candidate_english_gin | 36 | 0 | 55.654 | 112.459 | 2023424 | 0.043 |
| 50000 | 40000 | existing_indexes | 36 | 0 | 280.509 | 554.890 | 5373952 | 0.000 |
| 50000 | 40000 | candidate_english_gin | 36 | 0 | 288.401 | 559.828 | 8953856 | 0.220 |

Each plan used Limit, top-N heapsort, a hash join and sequential scans of both tables. No candidate English GIN index was selected. The candidate indexes showed no consistent p95 improvement and increased index size, so no application index or migration is justified by this test. In the 50,000-chunk run, the broad query matched 39,750 rows at the hash join; the sort showed 29 kB of in-memory top-N sort space and zero temporary blocks written. Other plan/buffer details and per-index sizes are in `c3-scale.json`.

Result checks passed for completed queries: exact-symbol search placed its exact match first, repeat order remained stable, and candidate indexes preserved order. This synthetic test does not validate authenticated API access, real repositories, production concurrency, real-source size distribution, or English GIN performance after a differently structured query. The 50,000 total / 40,000 eligible case is above current indexing chunk limits and is a stress scenario, not a supported-repository claim.
