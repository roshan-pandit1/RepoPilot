# Issue-to-report v1 review rubric

The fixture labels identify source locations a reviewer considers relevant. They are not an
exhaustive relevance set, verified defects, or answer keys for root causes. Review reports
against the same pinned commit and the complete context available for the case. A mock's
predetermined hypothesis is never evidence that the diagnosis is correct.

For a future evaluation of real reports, ask independent qualified reviewers to record a
short justification and evidence for each dimension. Mark **not assessable** when there is
not enough information; do not count that result as correct or incorrect.

| Dimension | 0 | 1 | 2 |
| --- | --- | --- | --- |
| Technical plausibility | Conflicts with available facts | Possible but weakly justified | Consistent with available facts and code |
| Supporting evidence | Missing, invalid, or does not support the claim | Some relevant support with a material gap | All major assertions have appropriate supporting source or observations |
| Contradictory evidence | Ignored or misrepresented | Mentioned without resolving implications | Correctly identified and its implications explained |
| Missing diagnostic information | Treats an unknown as known | Notes some unknowns | Identifies material unknowns and tests that distinguish alternatives |
| Next steps | Unsafe, irrelevant, or infeasible | Partly useful but incomplete | Specific, safe, feasible checks tied to uncertainty |
| Uncertainty | Presents speculation as fact | Acknowledges some uncertainty | Calibrated to evidence and avoids numerical confidence without validation |

Before publishing substantive scores, predefine the case selection, independent reference
judgments, reviewer qualifications, disagreement/adjudication procedure, denominators and
the handling of not-assessable items. Store review rationales without secrets. The rubric
is a plan; no human root-cause review or diagnostic-quality score has been conducted here.

Treat outcomes separately: **no retrieved evidence** is an observed empty result; **no
labeled hit** may still contain unlabeled relevant evidence; **insufficient issue detail**
prevents an informed causal conclusion; **conflicting evidence** needs explicit treatment;
**unauthorized** and **snapshot unavailable** are access/system outcomes, not relevance
judgments. The negative candidate remains unscored until independent, sufficiently complete
no-answer review has been performed for the pinned snapshot.
