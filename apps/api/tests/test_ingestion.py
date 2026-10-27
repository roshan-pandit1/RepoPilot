from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from celery.exceptions import Retry
from sqlalchemy import event, func, select
from sqlalchemy.exc import OperationalError

from app.domain.models import Delivery, Installation, Issue, Outbox, Repository, Tenant, now
from app.workers.dispatcher import dispatch_once
from app.workers.tasks import ingest_issue, process_event
from conftest import signed

URL = "/v1/webhooks/github"


def count(factory, model):
    with factory() as db:
        return db.scalar(select(func.count()).select_from(model))


def test_signed_webhook_to_authorized_read(client, factory, payload, auth):
    response = client.post(URL, **signed(payload))
    assert response.status_code == 202
    assert count(factory, Delivery) == count(factory, Outbox) == 1
    assert count(factory, Issue) == 0
    process_event(response.json()["delivery_id"], factory)
    response = client.get("/v1/repositories/2001/issues", headers=auth)
    assert response.status_code == 200
    assert response.json()["items"][0]["title"] == payload["issue"]["title"]
    assert response.json()["ingestion"]["processed"] == 1


@pytest.mark.parametrize("signature", [None, "sha256=bad"])
def test_invalid_signature(client, factory, payload, signature):
    request = signed(payload)
    if signature is None:
        request["headers"].pop("X-Hub-Signature-256")
    else:
        request["headers"]["X-Hub-Signature-256"] = signature
    assert client.post(URL, **request).status_code == 401
    assert count(factory, Delivery) == 0


def test_changed_original_body_rejected(client, payload):
    request = signed(payload)
    request["content"] += b" "
    assert client.post(URL, **request).status_code == 401


def test_duplicate_and_conflicting_delivery(client, factory, payload):
    delivery = str(uuid4())
    request = signed(payload, delivery)
    assert client.post(URL, **request).status_code == 202
    assert client.post(URL, **request).status_code == 200
    payload["issue"]["title"] = "Conflict"
    assert client.post(URL, **signed(payload, delivery)).status_code == 409
    assert count(factory, Outbox) == 1


@pytest.mark.parametrize("body", [b"not-json", b"[]", b"null", b"{}", b'"str"', b'\xff'])
def test_malformed_body(client, factory, body):
    assert client.post(URL, **signed(body)).status_code == 400
    assert count(factory, Delivery) == 0


def test_overly_nested_json_is_rejected(client, factory):
    body = b"[" * 1100 + b"0" + b"]" * 1100
    assert client.post(URL, **signed(body)).status_code == 400
    assert count(factory, Delivery) == count(factory, Outbox) == 0


def test_unsupported_event_and_action(client, payload):
    assert client.post(URL, **signed(payload, event="push")).status_code == 400
    payload["action"] = "closed"
    assert client.post(URL, **signed(payload)).status_code == 400


def test_required_headers(client, payload):
    for header in ("X-GitHub-Event", "X-GitHub-Delivery", "Content-Type"):
        request = signed(payload)
        request["headers"].pop(header)
        assert client.post(URL, **request).status_code in (400, 415)


def test_streamed_body_limit(client):
    request = signed(b"x" * (1024 * 1024 + 1))
    request["content"] = iter([request["content"][:100], request["content"][100:]])
    assert client.post(URL, **request).status_code == 413


def test_database_failure_rolls_back_both_records(client, factory, payload):
    engine = factory.kw["bind"]
    def fail_outbox(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO outbox_events"):
            raise OperationalError("redacted", {}, Exception("failure"))
    event.listen(engine, "before_cursor_execute", fail_outbox)
    try:
        response = client.post(URL, **signed(payload))
        assert response.status_code == 503
        assert response.json() == {"detail": "Service temporarily unavailable"}
    finally:
        event.remove(engine, "before_cursor_execute", fail_outbox)
    assert count(factory, Delivery) == count(factory, Outbox) == 0


def test_worker_idempotency_and_stale_updates(client, factory, payload):
    newer = client.post(URL, **signed(payload)).json()["delivery_id"]
    process_event(newer, factory)
    process_event(newer, factory)
    payload["action"] = "edited"
    payload["issue"].update(title="Stale", updated_at="2026-01-01T12:00:00Z")
    older = client.post(URL, **signed(payload)).json()["delivery_id"]
    process_event(older, factory)
    with factory() as db:
        assert db.get(Issue, 3001).title == "Signed demo issue"
    payload["issue"].update(title="Latest", updated_at="2026-01-03T12:00:00Z")
    latest = client.post(URL, **signed(payload)).json()["delivery_id"]
    process_event(latest, factory)
    with factory() as db:
        assert db.get(Issue, 3001).title == "Latest"
    assert count(factory, Issue) == 1


def test_equal_timestamp_keeps_first_applied_state(client, factory, payload):
    first = client.post(URL, **signed(payload)).json()["delivery_id"]
    process_event(first, factory)
    payload["issue"]["title"] = "Ambiguous same timestamp"
    second = client.post(URL, **signed(payload)).json()["delivery_id"]
    process_event(second, factory)
    with factory() as db:
        assert db.get(Issue, 3001).title == "Signed demo issue"


def test_celery_retry_on_transient_failure(monkeypatch):
    def fail(event_id):
        raise OperationalError("redacted", {}, Exception("failure"))
    monkeypatch.setattr("app.workers.tasks.process_event", fail)
    with pytest.raises(Retry):
        ingest_issue.apply(args=[str(uuid4())], throw=True)


def test_publish_failure_and_broker_loss_are_recoverable(client, factory, payload):
    delivery = client.post(URL, **signed(payload)).json()["delivery_id"]
    def unavailable(event_id):
        raise ConnectionError("broker down")
    dispatch_once(factory, unavailable)
    with factory.begin() as db:
        row = db.get(Outbox, delivery)
        assert row.status == "pending" and row.attempts == 1
        row.next_dispatch_at = now() - timedelta(seconds=1)
    published = []
    dispatch_once(factory, published.append)
    assert published == [delivery]
    # Simulate a successful publish followed by message loss; dispatcher republishes.
    with factory.begin() as db:
        db.get(Outbox, delivery).next_dispatch_at = now() - timedelta(seconds=1)
    dispatch_once(factory, published.append)
    assert published == [delivery, delivery]
    process_event(delivery, factory)
    process_event(delivery, factory)
    assert count(factory, Issue) == 1


def test_dispatch_budget_exhaustion(client, factory, payload):
    delivery = client.post(URL, **signed(payload)).json()["delivery_id"]
    with factory.begin() as db:
        db.get(Outbox, delivery).attempts = 20
    calls = []
    dispatch_once(factory, calls.append)
    assert calls == []
    with factory() as db:
        assert db.get(Outbox, delivery).status == "failed"


@pytest.mark.parametrize("kind,action", [("installation", "deleted"),
                                         ("installation", "suspend"),
                                         ("installation_repositories", "removed")])
def test_revocation_blocks_reads_and_pending_jobs(client, factory, payload, auth, kind, action):
    delivery = client.post(URL, **signed(payload)).json()["delivery_id"]
    lifecycle = {"action": action, "installation": {"id": 1001},
                 "repositories_removed": [{"id": 2001}]}
    assert client.post(URL, **signed(lifecycle, event=kind)).status_code == 202
    process_event(delivery, factory)
    assert count(factory, Issue) == 0
    assert client.get("/v1/repositories", headers=auth).json() == []
    assert client.get("/v1/repositories/2001/issues", headers=auth).status_code == 404
    assert client.post(URL, **signed(payload)).status_code == 403


def test_lifecycle_cannot_enroll_or_reactivate(client, factory):
    with factory.begin() as db:
        db.get(Installation, 1001).active = False
    for installation_id in (1001, 9999):
        response = client.post(URL, **signed({"action": "created", "installation": {
            "id": installation_id}}, event="installation"))
        assert response.status_code == 202
    with factory() as db:
        assert not db.get(Installation, 1001).active
        assert db.get(Installation, 9999) is None


def test_unknown_private_and_mismatched_repos(client, payload):
    payload["repository"]["private"] = True
    assert client.post(URL, **signed(payload)).status_code == 403
    payload["repository"].update(private=False, id=9999)
    assert client.post(URL, **signed(payload)).status_code == 403
    payload["repository"]["id"] = 2001
    payload["installation"]["id"] = 9999
    assert client.post(URL, **signed(payload)).status_code == 403


def test_tenant_isolation_and_missing_auth(client, factory, auth):
    with factory.begin() as db:
        db.add(Tenant(id=2, name="Other tenant"))
        db.flush()
        db.add(Installation(id=1002, tenant_id=2, active=True))
        db.flush()
        db.add(Repository(id=2002, tenant_id=2, installation_id=1002,
                          full_name="other/repository", enabled=True))
    assert client.get("/v1/repositories").status_code == 401
    assert client.get("/v1/repositories", headers={"Authorization": "Bearer wrong"}).status_code == 401
    # HTTP headers are decoded as Latin-1. Reject non-ASCII tokens without a 500.
    assert client.get("/v1/repositories", headers=[(b"Authorization", b"Bearer \xe9")]).status_code == 401
    assert [r["id"] for r in client.get("/v1/repositories", headers=auth).json()] == ["2001"]
    assert client.get("/v1/repositories/2002/issues", headers=auth).status_code == 404


def test_concurrent_workers_postgres(client, factory, payload):
    if factory.kw["bind"].dialect.name != "postgresql":
        pytest.skip("Row-lock concurrency requires PostgreSQL; CI runs this test")
    deliveries = [client.post(URL, **signed(payload)).json()["delivery_id"] for _ in range(4)]
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda key: process_event(key, factory), deliveries * 2))
    assert count(factory, Issue) == 1


def test_worker_failure_rolls_back_issue_and_remains_retryable(client, factory, payload):
    delivery = client.post(URL, **signed(payload)).json()["delivery_id"]
    engine = factory.kw["bind"]

    def fail_completion(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE outbox_events"):
            raise OperationalError("redacted", {}, Exception("failure"))

    event.listen(engine, "before_cursor_execute", fail_completion)
    try:
        with pytest.raises(OperationalError):
            process_event(delivery, factory)
    finally:
        event.remove(engine, "before_cursor_execute", fail_completion)
    assert count(factory, Issue) == 0
    with factory() as db:
        assert db.get(Outbox, delivery).status == "pending"
    process_event(delivery, factory)
    assert count(factory, Issue) == 1
