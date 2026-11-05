# Portfolio and interview guide

## Five-minute read-only walkthrough

Use an already authenticated local session, an enrolled public repository, and previously
persisted jobs. If those prerequisites or the browser review are unavailable, use the
architecture and verified artifacts instead of inventing a live result.

1. **0:00–0:45 — Problem.** Explain that an issue often names a symptom while the relevant
   code is elsewhere. RepoPilot narrows the search to inspectable source candidates.
2. **0:45–1:30 — Issue and authorization.** Show the selected repository and existing issue.
   Explain GitHub App sign-in, repository authorization and why access is checked again.
3. **1:30–2:30 — History and evidence.** Open a completed investigation from history. Show
   job state, evidence ranks, a file path and a citation that pins the commit and line range.
   Say that a retrieved candidate is not a confirmed cause.
   Optionally explain that CIE-v1 can statically inspect existing evidence without executing it;
   its PostgreSQL and browser verification remain outstanding, so do not present it as verified.
4. **2:30–3:15 — Report.** Open an existing report and point to **MOCK REPORT — DEMONSTRATION
   ONLY**, supporting evidence, uncertainty and missing information. Explain that this is
   deterministic mock output, not verified AI reasoning.
5. **3:15–4:15 — Architecture.** Trace signed webhook → database/outbox → dispatcher → Redis →
   worker, then snapshot-fenced retrieval and authorized dashboard reads. Explain duplicate
   delivery, idempotency and commit-pinned citations.
6. **4:15–5:00 — Evidence and limits.** Describe the synthetic retrieval comparison, security
   tests and the remaining browser acceptance. Explain that real-model quality and public
   deployment have not been verified.

Do not click **Investigate issue**, **Generate report**, or reindex during this walkthrough;
they create work. The [browser acceptance checklist](sprint-5c2-dashboard.md#read-only-browser-acceptance-on-the-mac)
has the detailed checks.

## Resume-ready bullets

- Built a GitHub issue investigation platform with Next.js, FastAPI, PostgreSQL and Celery,
  connecting authenticated issue workflows to commit-pinned Python source evidence.
- Designed transactional outboxes, worker leases and idempotent processing for at-least-once
  event delivery, with tenant-scoped access and signed webhook verification.
- Evaluated deterministic lexical ranking on a pinned synthetic benchmark; Recall@10 increased
  from 0.6250 to 0.7188 on 16 scored cases, with incomplete labels and same-set selection.
- Added evidence-grounded mock reports and an investigation dashboard, backed by 587 passing
  disposable PostgreSQL tests and 33 adversarial checks in the final local regression run.

## Interview questions

**Why use an outbox?** Writing the delivery and dispatch record in one transaction avoids a
database commit succeeding while a broker publish is lost. A dispatcher retries publication;
workers still must handle duplicate delivery.

**How do retries remain safe?** Workers claim bounded leases and recheck ownership and access
before committing effects; uniqueness constraints, idempotent operations and fencing prevent
duplicate delivery from silently duplicating completed work.

**How is tenant access enforced?** Session and membership checks, tenant/repository predicates,
active-installation checks and current GitHub authorization guard reads. Composite foreign keys
protect ownership relationships. PostgreSQL row-level security is not implemented.

**Why pin citations to a commit?** A branch changes over time. The snapshot commit, file and
inclusive line range allow a reviewer to inspect the source version used for retrieval; evidence
fingerprints and ownership checks guard subsequent reads.

**What does the ranking result mean?** It is a comparison over the same synthetic dataset and
snapshot. It shows a measured top-10 recall gain with increased latency and an individual case
regression; incomplete labels and same-set strategy selection limit generalization.

**Why are the reports labeled mock?** The deterministic mock exercises the report schema,
citation validation and presentation. It is not a real-model evaluation or proof of diagnosis.

**Why build CIE-v1?** It offers a reproducible, no-model way to connect explicit issue signals
to already authorized source evidence. Python AST parsing extracts bounded definitions and
syntactic relationships; every finding cites existing evidence and includes uncertainty.
Dynamic Python behavior and incomplete chunks limit what it can infer. An offline replay showed
no ranking gain, so the existing retrieval order remains in use.

## Screenshots still needed

- Repository issue inbox and investigation history.
- A completed investigation with evidence and a commit-pinned citation.
- An existing report with its mock warning visible.
- Mobile view showing readable controls and evidence.

Capture only after [manual browser review](sprint-5c2-dashboard.md), with private information
and credentials removed. No screenshots or public demo URL are fabricated.
