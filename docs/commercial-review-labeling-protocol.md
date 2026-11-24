# Independent review-quality labeling protocol

Status: **LABEL COLLECTION REQUIRED**. This document is a workflow, not a dataset,
completed interview, independent evaluation, or performance claim.

1. Select appropriately licensed public changes or original cases without observing
   analyzer output. Record repository/fixture identity, license, base/head commits,
   paths, source SHA-256, changed ranges and permitted review scope. Do not include
   private code in shared records. A bug-fix commit alone is not a defect label.
2. Freeze a canonical, sorted manifest and its SHA-256, date, curator, selection rules
   and split before running the candidate analyzer. Keep development, regression,
   negative controls and holdout separate; do not tune rules against the holdout.
3. Have at least two independent qualified developers inspect each case blind to
   analyzer results. Record anonymized reviewer IDs, relevant range, actionable defect
   yes/no/uncertain, category, severity rationale, supporting evidence, suggested
   actionability and label provenance. Preserve disagreements; an independent
   adjudicator resolves them with a recorded reason. Do not relabel uncertainty as
   a negative merely to calculate a score.
4. Store each adjudicated case in the evaluator's `review-quality-v1` format, plus a
   separate versioned review record containing reviewer IDs, independent judgments,
   adjudication, scope, sources and manifest hash. Freeze and hash both files. Review
   provenance manually; a self-declared `independent_holdout` split is not proof of
   independence. The scorer deliberately returns `independence: not independently
   verified`.
5. Run the fixed analyzer version against the fixed scope; retain raw outputs and
   timing. Match findings one-to-one by rule/path and overlapping lines; additional
   findings, including duplicates, count as false positives. Report TP, FP, FN,
   precision, recall on supported labeled cases, location, severity agreement,
   duplicate count, unsupported cases and all denominators. Separately report
   human usefulness ratings when obtained and uncertainty where sample sizes permit.
6. A future competitor comparison must use the same frozen cases, scope, review
   budget, tool versions and human adjudication. Report missing coverage and costs.
   Do not infer superiority from synthetic rule-authored fixtures.
