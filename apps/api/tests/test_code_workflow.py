import pytest
from sqlalchemy import select

from app.domain.models import CodeChunk, CodeSnapshot, IndexJob, Installation
from app.modules.github.client import GitHubFailure
from app.workers.dispatcher import dispatch_once
from app.workers.tasks import TransientIngestionError, process_index
from test_auth_enrollment import csrf, github_auth as github_auth, sign_in


class FakeSource:
    source = b"def calculate_total():\n    return 42\n"

    def repository(self, token, full_name):
        assert token == "sensitive-github-token"
        return {"private": False, "full_name": full_name, "default_branch": "main"}

    def commit(self, token, full_name, branch):
        return {"sha": "a" * 40}

    def tree(self, token, full_name, sha):
        return {"truncated": False, "tree": [{"path": "src/total.py", "type": "blob", "mode": "100644",
                                               "sha": "b" * 40, "size": len(self.source)}]}

    def blob(self, token, full_name, sha, expected_size):
        return self.source


def connect(client):
    sign_in(client)
    assert client.post("/v1/installations/901/enroll", headers=csrf(client)).status_code == 200
    assert client.post("/v1/installations/901/repositories/902/select", headers=csrf(client)).status_code == 200


def test_index_job_is_durable_deduplicated_and_processes(client, factory, github_auth):
    connect(client)
    assert client.post("/v1/repositories/902/index").status_code == 403
    first = client.post("/v1/repositories/902/index", headers=csrf(client))
    assert first.status_code == 202
    job_id = first.json()["job_id"]
    assert client.post("/v1/repositories/902/index", headers=csrf(client)).json()["job_id"] == job_id
    with factory() as db:
        assert db.get(IndexJob, job_id).status == "pending"
    sent = []
    dispatch_once(factory, lambda _: None, lambda _: None, sent.append)
    assert sent == [job_id]
    process_index(job_id, factory, github_auth, FakeSource())
    process_index(job_id, factory, github_auth, FakeSource())
    with factory() as db:
        job = db.get(IndexJob, job_id)
        assert (job.status, job.commit_sha, job.file_count, job.chunk_count) == ("completed", "a" * 40, 1, 1)
        assert db.scalar(select(CodeChunk)).symbol == "calculate_total"
        assert len(db.scalars(select(CodeSnapshot)).all()) == 1
    status = client.get("/v1/repositories/902/index-status").json()
    assert status["status"] == "completed"
    assert status["commit_sha"] == "a" * 40
    assert status["indexed_at"] is not None


def test_lifecycle_events_correlate_job_without_source_or_token(client, factory, github_auth, monkeypatch):
    events = []
    monkeypatch.setattr("app.core.index_logging.index_event", lambda name, **fields: events.append((name, fields)))
    monkeypatch.setattr("app.modules.ingestion.code_routes.index_event", lambda name, **fields: events.append((name, fields)))
    connect(client)
    job_id = client.post("/v1/repositories/902/index", headers=csrf(client)).json()["job_id"]
    process_index(job_id, factory, github_auth, FakeSource(), task_id="fixture-task")
    names = [name for name, _ in events]
    assert names == ["index_job_queued", "index_job_claimed", "index_source_started",
                     "index_source_collected", "index_publication_started", "index_snapshot_published",
                     "index_job_completed"]
    assert all(fields["job_id"] == job_id and fields["repository_id"] == 902 for _, fields in events)
    assert events[-1][1]["snapshot_id"]
    assert "sensitive-github-token" not in repr(events)
    assert "return 42" not in repr(events)


def test_index_cancelled_after_revocation_and_cross_tenant_denied(client, factory, github_auth):
    connect(client)
    job_id = client.post("/v1/repositories/902/index", headers=csrf(client)).json()["job_id"]
    with factory.begin() as db:
        db.get(Installation, 901).active = False
    process_index(job_id, factory, github_auth, FakeSource())
    with factory() as db:
        assert db.get(IndexJob, job_id).status == "cancelled"
        assert db.scalar(select(CodeSnapshot)) is None
    assert client.get("/v1/repositories/902/index-status").status_code == 404
    assert client.post("/v1/repositories/902/search", headers=csrf(client), json={"query": "total"}).status_code == 404


def test_transient_fetch_failure_keeps_pending_and_previous_snapshot(client, factory, github_auth):
    connect(client)
    first = client.post("/v1/repositories/902/index", headers=csrf(client)).json()["job_id"]
    process_index(first, factory, github_auth, FakeSource())
    second = client.post("/v1/repositories/902/index", headers=csrf(client)).json()["job_id"]

    class Failing(FakeSource):
        def tree(self, token, full_name, sha):
            raise GitHubFailure("github_request_failed")

    with pytest.raises(TransientIngestionError):
        process_index(second, factory, github_auth, Failing())
    with factory() as db:
        assert db.get(IndexJob, second).status == "pending"
        assert db.scalar(select(CodeSnapshot).where(CodeSnapshot.published.is_(True))).commit_sha == "a" * 40


def test_index_and_search_reject_other_tenant(client, factory, github_auth):
    connect(client)
    first = client.post("/v1/repositories/902/index", headers=csrf(client)).json()["job_id"]
    process_index(first, factory, github_auth, FakeSource())
    assert client.post("/v1/auth/logout", headers=csrf(client)).status_code == 200
    github_auth.user_id = github_auth.account_id = 78
    sign_in(client)
    assert client.get("/v1/repositories/902/index-status").status_code == 404
    assert client.post("/v1/repositories/902/index", headers=csrf(client)).status_code == 404
    assert client.post("/v1/repositories/902/search", headers=csrf(client), json={"query": "total"}).status_code == 404


def test_revocation_during_fetch_does_not_publish(client, factory, github_auth):
    connect(client)
    job_id = client.post("/v1/repositories/902/index", headers=csrf(client)).json()["job_id"]

    class Revoked(FakeSource):
        def blob(self, token, full_name, sha, expected_size):
            with factory.begin() as db:
                assert db.get(IndexJob, job_id).status == "running"
                db.get(Installation, 901).active = False
            return self.source

    process_index(job_id, factory, github_auth, Revoked())
    with factory() as db:
        assert db.get(IndexJob, job_id).status == "cancelled"
        assert db.scalar(select(CodeSnapshot)) is None


def test_stale_lease_cannot_publish(client, factory, github_auth):
    connect(client)
    job_id = client.post("/v1/repositories/902/index", headers=csrf(client)).json()["job_id"]

    class LostLease(FakeSource):
        def blob(self, token, full_name, sha, expected_size):
            with factory.begin() as db:
                db.get(IndexJob, job_id).lease_token = "another-worker"
            return self.source

    process_index(job_id, factory, github_auth, LostLease())
    with factory() as db:
        assert db.get(IndexJob, job_id).lease_token == "another-worker"
        assert db.scalar(select(CodeSnapshot)) is None


def test_changed_commit_during_fetch_is_not_published(client, factory, github_auth):
    connect(client)
    job_id = client.post("/v1/repositories/902/index", headers=csrf(client)).json()["job_id"]

    class Changed(FakeSource):
        def __init__(self):
            self.calls = 0

        def commit(self, token, full_name, branch):
            self.calls += 1
            return {"sha": ("a" if self.calls == 1 else "c") * 40}

    process_index(job_id, factory, github_auth, Changed())
    with factory() as db:
        assert db.get(IndexJob, job_id).error_code == "repository_changed"
        assert db.scalar(select(CodeSnapshot)) is None


def test_dispatch_reclaims_expired_lease_without_republishing_live_claim(client, factory, github_auth):
    from datetime import timedelta
    from app.domain.models import now

    connect(client)
    job_id = client.post("/v1/repositories/902/index", headers=csrf(client)).json()["job_id"]
    with factory.begin() as db:
        job = db.get(IndexJob, job_id)
        job.status = "running"
        job.lease_token = "dead-worker"
        job.lease_expires_at = now() + timedelta(minutes=1)
    sent = []
    dispatch_once(factory, lambda _: None, lambda _: None, sent.append)
    assert sent == []
    with factory.begin() as db:
        db.get(IndexJob, job_id).lease_expires_at = now() - timedelta(seconds=1)
    dispatch_once(factory, lambda _: None, lambda _: None, sent.append)
    assert sent == [job_id]
    process_index(job_id, factory, github_auth, FakeSource())
    with factory() as db:
        assert db.get(IndexJob, job_id).status == "completed"


def test_postgres_concurrent_requests_share_one_active_job(client, factory, github_auth):
    if factory.kw["bind"].dialect.name != "postgresql":
        pytest.skip("PostgreSQL row locks are required")
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from fastapi.testclient import TestClient
    from app.main import app

    connect(client)
    cookies = dict(client.cookies)
    headers = csrf(client)
    gate = Barrier(2)

    def start():
        with TestClient(app, cookies=cookies) as other:
            gate.wait(timeout=10)
            response = other.post("/v1/repositories/902/index", headers=headers)
            return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: start(), range(2)))
    assert [status for status, _ in results] == [202, 202]
    assert results[0][1]["job_id"] == results[1][1]["job_id"]
    with factory() as db:
        assert len(db.scalars(select(IndexJob)).all()) == 1


def test_postgres_search_returns_commit_citation(client, factory, github_auth):
    if factory.kw["bind"].dialect.name != "postgresql":
        pytest.skip("PostgreSQL full-text search is required")
    connect(client)
    job_id = client.post("/v1/repositories/902/index", headers=csrf(client)).json()["job_id"]
    process_index(job_id, factory, github_auth, FakeSource())
    response = client.post("/v1/repositories/902/search", headers=csrf(client), json={"query": "calculate_total"})
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert (item["path"], item["symbol"], item["start_line"], item["end_line"]) == ("src/total.py", "calculate_total", 1, 2)
    assert item["url"] == "https://github.com/alice/public/blob/" + "a" * 40 + "/src/total.py#L1-L2"


def test_postgres_keyword_search_handles_natural_language_and_identifiers(client, factory, github_auth):
    if factory.kw['bind'].dialect.name != 'postgresql':
        pytest.skip('PostgreSQL full-text search is required')
    from app.domain.models import Repository

    connect(client)
    job_id = client.post('/v1/repositories/902/index', headers=csrf(client)).json()['job_id']
    process_index(job_id, factory, github_auth, FakeSource())
    for query in ('calculate_total', 'Where is calculate total implemented?', 'src/total.py'):
        response = client.post('/v1/repositories/902/search', headers=csrf(client), json={'query': query})
        assert response.status_code == 200
        assert response.json()['items'][0]['symbol'] == 'calculate_total'
        assert response.json()['items'][0]['url'].endswith('/src/total.py#L1-L2')
    assert client.post('/v1/repositories/902/search', headers=csrf(client), json={'query': '   '}).status_code == 422
    stopwords = client.post('/v1/repositories/902/search', headers=csrf(client), json={'query': 'the and of'})
    assert stopwords.status_code == 200 and stopwords.json()['items'] == []
    injection = client.post('/v1/repositories/902/search', headers=csrf(client),
                            json={'query': "'; DROP TABLE repositories; --"})
    assert injection.status_code == 200
    with factory() as db:
        assert db.get(Repository, 902) is not None


def test_postgres_keyword_camelcase_and_bounded_results(client, factory, github_auth):
    if factory.kw['bind'].dialect.name != 'postgresql':
        pytest.skip('PostgreSQL full-text search is required')

    class ManySymbols(FakeSource):
        source = ('def GitHubWebhookVerifier():\n    return "verified"\n\n' + ''.join(
            f'def operation_{i}():\n    return "operation"\n\n' for i in range(70))).encode()

    connect(client)
    job_id = client.post('/v1/repositories/902/index', headers=csrf(client)).json()['job_id']
    process_index(job_id, factory, github_auth, ManySymbols())
    camel = client.post('/v1/repositories/902/search', headers=csrf(client),
                        json={'query': 'GitHubWebhookVerifier'})
    assert camel.status_code == 200
    assert camel.json()['items'][0]['symbol'] == 'GitHubWebhookVerifier'
    responses = [client.post('/v1/repositories/902/search', headers=csrf(client),
                             json={'query': 'operation', 'limit': 50}) for _ in range(2)]
    assert all(response.status_code == 200 for response in responses)
    assert len(responses[0].json()['items']) == 50
    assert [item['symbol'] for item in responses[0].json()['items']] == [
        item['symbol'] for item in responses[1].json()['items']]
    for body in ({'query': ''}, {'query': 'x' * 201}, {'query': 'operation', 'limit': 51}):
        assert client.post('/v1/repositories/902/search', headers=csrf(client), json=body).status_code == 422
    punctuation = client.post('/v1/repositories/902/search', headers=csrf(client), json={'query': '!!!'})
    assert punctuation.status_code == 200 and punctuation.json()['items'] == []
