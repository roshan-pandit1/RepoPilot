# Mock report evaluation

Dataset: mock-report-v1
Valid model outputs: 7/9
Invalid outputs rejected: 2
Validated synthetic evidence references: 6
Duplicate replay: 1 report, 1 worker attempt; revoked access HTTP 404
In-process model validation p50/p95: 0.585/1.197 ms

| Case | Outcome | References |
| --- | --- | ---: |
| exact_function | valid | 1 |
| natural_language | valid | 1 |
| ambiguous | valid | 1 |
| no_evidence | valid | 0 |
| unsupported | valid | 0 |
| contradictory | valid | 2 |
| malicious | valid | 1 |
| malformed | rejected | 0 |
| foreign_citation | rejected | 0 |

Mock mechanics only; synthetic references, no real model reasoning, remote citations, real Celery or performance/load claim.
