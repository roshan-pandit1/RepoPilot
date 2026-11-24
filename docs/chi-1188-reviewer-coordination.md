# chi #1188 — reviewer coordination drafts

**Status: reviewer and adjudicator identities have not been provided; no
invitations sent.**
The existing [blind review protocol](chi-1188-human-labeling.md) and its
private packets are ready. This coordinator note does not change either packet,
create judgments, or grant access to a reviewer.

The coordinator should select two independent people with relevant Go/routing
experience and a separate adjudicator. Ask each person privately, assign a
pseudonym only after they agree, and agree on a handoff and return time. Do not
share issue text, source, another person's identity or a packet through an
unapproved service. The owner-only packet folders are not isolation between
people using the same OS account. Use separately controlled accounts or a
protected offline handoff, include the pinned MIT notice, and retain each
submission separately until both are frozen. Confirm that sharing the retained
issue text is appropriate under its terms and privacy requirements.

## Draft to send separately to each prospective reviewer

> Would you be willing to independently review a small, partial-source Go
> routing case for a retrieval-evaluation pilot? Please identify any source
> ranges that help explain the reported behavior, give your reasoning and
> record uncertainty. You may mark ranges unjudged or abstain. Relevance does
> not imply a defect or verified root cause. Please do not consult another
> reviewer's answers, model rankings or prior suggested ranges. If you agree,
> I will provide your individual packet and instructions through a private
> channel and arrange a return time with you.

Use `reviewer-a` and `reviewer-b` from the existing private packet directory
for separate handoffs; do not expose the other copy or the prior audit. The
full issue comment is intentionally withheld from initial review, and the
source is only the retained five-file subset. Do not add newly collected
source to an in-progress review. The recipient's acceptance and actual
independence must be established by the coordinator, not inferred from the
template.

## Draft for the later adjudicator

> Would you be willing to adjudicate two independently completed reviews of a
> partial-source Go routing case? After both are frozen, please compare their
> reasoning and disagreements, record uncertainty, and explain any resolution.
> Relevance does not prove a defect or root cause. Please use a pseudonym in the
> record and do not use model rankings as a substitute for evidence.

Do not send this request with reviewer responses until both independent
submissions are complete and permission to share them has been established.
If only one reviewer is available, preserve the result as
`SINGLE_REVIEWER_EXPLORATORY`; do not describe it as adjudicated.

## Returning and validating submissions

Do not create placeholder submissions or fill in the blank templates. Once
people actually submit records, keep them private and provide their actual
paths to the coordinator; alternatively the user can upload the completed
files for inspection. The existing validator accepts owner-only JSON under
the approved private benchmark root, rechecks source and context identities,
and rejects invalid ranges or missing fields. Corrections must come from the
submitting reviewer. It checks self-attested metadata and cannot authenticate
the people or prove their independence. See the command and adjudication
schema in the [review protocol](chi-1188-human-labeling.md).
