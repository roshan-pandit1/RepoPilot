# Proposed paid embedding budget design — not implemented

Paid generation and query embedding remain disabled. Approval of a future experiment must name
the repository, commit, model, dimensions, maximum price, token/request ceiling, and expiry.
The existing provider allow flag is not a budget and must not be treated as one.

Before enabling any provider, add a database-backed experiment with a fixed integer currency
budget and a pinned price schedule. Atomically reserve the worst-case charge for each request
under a row lock, including a documented upper bound for the input and one reservation for every
attempt. Reject calls before dispatch if available budget or token/request ceilings would be
exceeded. Bound simultaneous in-flight reservations and configure a provider/account hard limit
independently where available; do not assume an alert is a hard cap. The application must not
let a stale lease or a restarted worker bypass the same reservation ledger.

Count input tokens with the model's pinned tokenizer before calling, reject inputs exceeding model
limits, and reconcile the reservation against returned usage. Keep indeterminate timeout/network
attempts charged at their worst-case reservation until provider billing is reconciled: a request
may have been billed even without a response. Retries consume new reservations and stop when
any budget is exhausted. Accounting and retry outcomes must persist even if a worker crashes;
test concurrent claims, timeouts, recovery, duplicates, and price changes. Provider billing
may include charges outside this application, so the experiment ledger alone cannot guarantee
an account-wide ceiling.

Do not send source until its data-handling policy and incomplete secret filtering have been
reviewed. Existing cache keys and retrieval filters partition vectors by tenant, repository,
provider, model, model version and dimensions; keep those boundaries and test them. Paid query
embeddings need the same admission and cost accounting as document embeddings. The existing
adapter retries transient failures but currently has neither durable reservations nor a hard
budget, and the worker explicitly refuses non-fake providers.
