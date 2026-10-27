# ADR 0001: Modular monolith with a transactional outbox

Status: accepted for Sprint 1 source implementation; runtime validation pending.

FastAPI, the dispatcher, and Celery import the same models and business modules. They are
separate processes so HTTP latency does not depend on issue processing, but remain one
application and one schema. Splitting into microservices would add deployment and consistency
work without solving a demonstrated scaling problem.

A webhook transaction writes both the delivery and its outbox row. Publishing directly to Redis
would create a gap: the database could commit while publishing fails. Polling durable rows closes
that gap. The worker owns completion; periodic republication also repairs a lost broker message.
Retries are bounded and dead events remain visible. This is at-least-once processing.

The worker locks an event and then its installation and repository. The repository lock serializes
issue upserts, while the unique repository/number key prevents duplicates and source timestamps
reject old updates. This trades throughput for simple correctness. All revocation paths use the
same installation-then-repository order. Equal timestamps retain the existing state.

Composite foreign keys prevent assigning issues/outbox rows to another repository's tenant.
Read queries check membership and active installation state. PostgreSQL RLS is deferred rather
than presenting untested RLS as a security guarantee. Production demo auth is forbidden.

Webhook lifecycle events can revoke authorization but never grant it. This avoids stale
reactivation and prevents signed events from granting access to an unverified tenant. Real
installation enrollment remains disabled until identity and ownership verification exist.

Reference documents describe the full product; this migration contains only the Sprint 1 subset.
GitHub numeric identifiers are used internally and serialized as strings in frontend-facing IDs
to avoid JavaScript precision loss. The reference UUID contract is not claimed as implemented.

SQLite is an optional fast service-test backend, not production storage or evidence of row-lock
correctness. PostgreSQL CI and a real broker/worker smoke test are the acceptance gates.
