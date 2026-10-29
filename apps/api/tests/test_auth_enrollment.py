from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from app.core.config import get_settings
from app.domain.models import AuthSession, Installation, Repository
from app.main import app
from app.modules.github.client import GitHubFailure, get_github_client


class FakeGitHub:
    def __init__(self):
        self.fail = False
        self.include_repository = True
        self.account_id = 77
        self.user_id = 77

    def exchange_code(self, code, verifier):
        assert code == "valid-code"
        assert len(verifier) >= 43
        return {"access_token": "sensitive-github-token", "expires_in": 3600}

    def current_user(self, token):
        assert token == "sensitive-github-token"
        return {"id": self.user_id, "login": "alice"}

    def installations(self, token):
        if self.fail:
            raise GitHubFailure("private upstream detail")
        return [{"id": 901, "app_id": 123, "account": {"id": self.account_id,
                 "type": "User", "login": "alice"}, "suspended_at": None}]

    def issues(self, token, full_name):
        assert token == "sensitive-github-token"
        assert full_name == "alice/public"
        return [{"id": 990, "number": 5, "title": "Existing GitHub issue", "body": None,
                 "state": "open", "updated_at": "2026-01-01T00:00:00Z"}]

    def repositories(self, token, installation_id):
        assert installation_id == 901
        return ([{"id": 902, "full_name": "alice/public", "private": False},
                 {"id": 903, "full_name": "alice/private", "private": True}]
                if self.include_repository else [])


@pytest.fixture
def github_auth(client, monkeypatch):
    config = get_settings()
    monkeypatch.setattr(config, "github_oauth_enabled", True)
    monkeypatch.setattr(config, "github_app_id", 123)
    monkeypatch.setattr(config, "github_client_id", "client-id")
    monkeypatch.setattr(config, "github_client_secret", SecretStr("client-secret"))
    monkeypatch.setattr(config, "github_token_encryption_key", SecretStr(Fernet.generate_key().decode()))
    monkeypatch.setattr(config, "github_callback_url", "http://localhost:3000/api/auth/callback")
    monkeypatch.setattr(config, "web_origin", "http://localhost:3000")
    fake = FakeGitHub()
    app.dependency_overrides[get_github_client] = lambda: fake
    yield fake


def sign_in(client):
    response = client.get("/v1/auth/github/start", follow_redirects=False)
    assert response.status_code == 302
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["code_challenge_method"] == ["S256"]
    state = query["state"][0]
    callback = client.get("/v1/auth/github/callback", params={"state": state, "code": "valid-code"},
                          follow_redirects=False)
    assert callback.status_code == 303
    assert "sensitive-github-token" not in str(callback.headers)
    return state


def csrf(client):
    return {"Origin": "http://localhost:3000", "X-CSRF-Token": client.cookies.get("rp_csrf")}


def test_login_session_encrypted_state_replay_and_logout(client, factory, github_auth):
    state = sign_in(client)
    old_session = client.cookies.get("rp_session")
    assert client.get("/v1/auth/me").json()["user"]["login"] == "alice"
    with factory() as db:
        from sqlalchemy import select
        row = db.scalar(select(AuthSession))
        assert "sensitive-github-token" not in row.github_token_ciphertext
        assert client.cookies.get("rp_session") != row.id_hash
    client.cookies.set("rp_oauth", state)
    assert client.get("/v1/auth/github/callback", params={"state": state, "code": "valid-code"}).status_code == 400
    assert client.post("/v1/auth/logout").status_code == 403
    assert client.post("/v1/auth/logout", headers={**csrf(client), "Origin": "https://attacker.test"}).status_code == 403
    assert client.post("/v1/auth/logout", headers=csrf(client)).status_code == 200
    with factory() as db:
        from sqlalchemy import select
        row = db.scalar(select(AuthSession))
        assert row.github_token_ciphertext == "" and row.revoked_at is not None
    assert client.get("/v1/auth/me").status_code == 401
    client.cookies.set("rp_session", old_session)
    assert client.get("/v1/auth/me").status_code == 401


def test_state_mismatch_cannot_exchange_code(client, github_auth):
    client.get("/v1/auth/github/start", follow_redirects=False)
    response = client.get("/v1/auth/github/callback", params={"state": "wrong", "code": "valid-code"})
    assert response.status_code == 400


def test_verified_enrollment_selection_and_current_access(client, factory, github_auth):
    sign_in(client)
    assert client.get("/v1/installations/available").json() == [{"id": "901", "account": "alice"}]
    assert client.post("/v1/installations/901/enroll").status_code == 403
    response = client.post("/v1/installations/901/enroll", headers=csrf(client))
    assert response.status_code == 200
    assert response.json()["repositories"] == [{"id": "902", "full_name": "alice/public"}]
    assert client.post("/v1/installations/901/repositories/903/select", headers=csrf(client)).status_code == 404
    assert client.post("/v1/installations/901/repositories/902/select", headers=csrf(client)).status_code == 200
    assert [r["id"] for r in client.get("/v1/repositories").json()] == ["902"]
    github_auth.include_repository = False
    assert client.get("/v1/repositories").json() == []
    assert client.get("/v1/repositories/902/issues").status_code == 404
    github_auth.fail = True
    assert client.get("/v1/repositories").status_code == 503
    with factory() as db:
        assert db.get(Installation, 901).active
        assert db.get(Repository, 902).enabled


def test_mismatched_account_and_revocation_cannot_be_enrolled(client, factory, github_auth):
    sign_in(client)
    github_auth.account_id = 999
    assert client.post("/v1/installations/901/enroll", headers=csrf(client)).status_code == 403
    github_auth.account_id = 77
    assert client.post("/v1/installations/901/enroll", headers=csrf(client)).status_code == 200
    with factory.begin() as db:
        db.get(Installation, 901).active = False
    assert client.post("/v1/installations/901/enroll", headers=csrf(client)).status_code == 409


def test_unknown_installation_removal_blocks_later_enrollment(client, factory, github_auth):
    from conftest import signed

    payload = {"action": "deleted", "installation": {"id": 901}}
    assert client.post("/v1/webhooks/github", **signed(payload, event="installation")).status_code == 202
    sign_in(client)
    assert client.post("/v1/installations/901/enroll", headers=csrf(client)).status_code == 409
    with factory() as db:
        assert db.get(Installation, 901) is None


def test_removed_repository_cannot_be_selected_after_stale_github_response(client, github_auth):
    from conftest import signed

    sign_in(client)
    assert client.post("/v1/installations/901/enroll", headers=csrf(client)).status_code == 200
    payload = {"action": "removed", "installation": {"id": 901},
               "repositories_removed": [{"id": 902}]}
    assert client.post("/v1/webhooks/github", **signed(payload, event="installation_repositories")).status_code == 202
    assert client.post("/v1/installations/901/repositories/902/select", headers=csrf(client)).status_code == 409


def test_changed_installation_permissions_disable_reads(client, github_auth):
    from conftest import signed

    sign_in(client)
    assert client.post("/v1/installations/901/enroll", headers=csrf(client)).status_code == 200
    assert client.post("/v1/installations/901/repositories/902/select", headers=csrf(client)).status_code == 200
    payload = {"action": "new_permissions_accepted", "installation": {"id": 901}}
    assert client.post("/v1/webhooks/github", **signed(payload, event="installation")).status_code == 202
    assert client.get("/v1/repositories").json() == []
    assert client.post("/v1/installations/901/enroll", headers=csrf(client)).status_code == 409


def test_initial_sync_is_durable_idempotent_and_honors_revocation(client, factory, github_auth):
    from app.domain.models import Issue, SyncJob
    from app.workers.dispatcher import dispatch_once
    from app.workers.tasks import process_sync

    sign_in(client)
    assert client.post("/v1/installations/901/enroll", headers=csrf(client)).status_code == 200
    result = client.post("/v1/installations/901/repositories/902/select", headers=csrf(client))
    job_id = result.json()["sync_job_id"]
    assert client.get(f"/v1/installations/sync/{job_id}").json()["status"] == "pending"
    sent = []
    dispatch_once(factory, lambda event_id: None, sent.append)
    assert sent == [job_id]
    process_sync(job_id, factory, github_auth)
    process_sync(job_id, factory, github_auth)
    with factory() as db:
        assert db.get(Issue, 990).title == "Existing GitHub issue"
        assert db.get(SyncJob, job_id).status == "processed"
    assert client.get("/v1/repositories/902/issues").json()["items"][0]["number"] == 5
    later = client.post("/v1/installations/901/repositories/902/select", headers=csrf(client)).json()["sync_job_id"]
    with factory.begin() as db:
        db.get(Installation, 901).active = False
    process_sync(later, factory, github_auth)
    with factory() as db:
        assert db.get(SyncJob, later).status == "ignored"


def test_distinct_user_cannot_read_or_claim_another_tenant_repository(client, github_auth):
    sign_in(client)
    assert client.post("/v1/installations/901/enroll", headers=csrf(client)).status_code == 200
    assert client.post("/v1/installations/901/repositories/902/select", headers=csrf(client)).status_code == 200
    assert client.post("/v1/auth/logout", headers=csrf(client)).status_code == 200
    github_auth.user_id = github_auth.account_id = 78
    sign_in(client)
    assert client.get("/v1/repositories").json() == []
    assert client.get("/v1/repositories/902/issues").status_code == 404
    assert client.post("/v1/installations/901/enroll", headers=csrf(client)).status_code == 409


def test_sync_fails_closed_when_session_is_logged_out(client, factory, github_auth):
    from app.domain.models import Issue, SyncJob
    from app.workers.tasks import process_sync

    sign_in(client)
    assert client.post("/v1/installations/901/enroll", headers=csrf(client)).status_code == 200
    result = client.post("/v1/installations/901/repositories/902/select", headers=csrf(client))
    job_id = result.json()["sync_job_id"]
    assert client.post("/v1/auth/logout", headers=csrf(client)).status_code == 200
    process_sync(job_id, factory, github_auth)
    with factory() as db:
        assert db.get(SyncJob, job_id).status == "ignored"
        assert db.get(Issue, 990) is None


def test_expired_oauth_attempt_and_session_are_rejected(client, factory, github_auth):
    from datetime import timedelta

    from sqlalchemy import select

    from app.domain.models import OAuthAttempt, now

    response = client.get("/v1/auth/github/start", follow_redirects=False)
    state = parse_qs(urlparse(response.headers["location"]).query)["state"][0]
    with factory.begin() as db:
        attempt = db.scalar(select(OAuthAttempt))
        attempt.expires_at = now() - timedelta(seconds=1)
    assert client.get("/v1/auth/github/callback", params={"state": state, "code": "valid-code"}).status_code == 400
    sign_in(client)
    with factory.begin() as db:
        session = db.scalar(select(AuthSession))
        session.expires_at = now() - timedelta(seconds=1)
    assert client.get("/v1/auth/me").status_code == 401


def test_production_cookie_attributes_and_demo_disabled(client, github_auth, monkeypatch):
    monkeypatch.setattr(get_settings(), "app_env", "production")
    start = client.get("/v1/auth/github/start", follow_redirects=False)
    cookie = start.headers["set-cookie"].lower()
    assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie
    # The development bearer remains unusable in production.
    token = get_settings().demo_api_token.get_secret_value()
    assert client.get("/v1/repositories", headers={"Authorization": "Bearer " + token}).status_code == 401


def test_github_failure_does_not_leak_details(client, github_auth):
    sign_in(client)
    github_auth.fail = True
    response = client.get("/v1/installations/available")
    assert response.status_code == 503
    assert "private upstream detail" not in response.text


def test_postgres_guard_serializes_revocation(factory):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from app.modules.github.guards import installation_guard

    if factory.kw["bind"].dialect.name != "postgresql":
        pytest.skip("PostgreSQL row locks are required")
    with factory.begin() as db:
        installation_guard(db, 901)
    locked, attempted, release, acquired = Event(), Event(), Event(), Event()

    def revoke():
        with factory.begin() as db:
            guard = installation_guard(db, 901)
            guard.revoked = True
            locked.set()
            assert release.wait(5)

    def enroll_check():
        assert locked.wait(5)
        with factory.begin() as db:
            attempted.set()
            guard = installation_guard(db, 901)
            acquired.set()
            return guard.revoked

    with ThreadPoolExecutor(max_workers=2) as pool:
        revoker = pool.submit(revoke)
        contender = pool.submit(enroll_check)
        try:
            assert attempted.wait(5)
            assert not acquired.wait(0.2)
        finally:
            release.set()
        revoker.result(timeout=5)
        assert contender.result(timeout=5) is True


def test_sync_retries_upstream_failure_without_partial_database_effects(client, factory, github_auth):
    from app.domain.models import Issue, SyncJob
    from app.workers.tasks import TransientIngestionError, process_sync

    sign_in(client)
    assert client.post("/v1/installations/901/enroll", headers=csrf(client)).status_code == 200
    result = client.post("/v1/installations/901/repositories/902/select", headers=csrf(client))
    job_id = result.json()["sync_job_id"]
    github_auth.fail = True
    with pytest.raises(TransientIngestionError):
        process_sync(job_id, factory, github_auth)
    with factory() as db:
        assert db.get(SyncJob, job_id).status == "pending"
        assert db.get(Issue, 990) is None
    github_auth.fail = False
    process_sync(job_id, factory, github_auth)
    with factory() as db:
        assert db.get(SyncJob, job_id).status == "processed"
        assert db.get(Issue, 990) is not None


def test_sync_reports_first_page_limit_without_claiming_complete(client, factory, github_auth):
    from app.domain.models import SyncJob
    from app.workers.tasks import process_sync

    sign_in(client)
    assert client.post("/v1/installations/901/enroll", headers=csrf(client)).status_code == 200
    job_id = client.post("/v1/installations/901/repositories/902/select", headers=csrf(client)).json()["sync_job_id"]
    github_auth.issues = lambda token, full_name: [
        {"id": 10000 + n, "number": n + 1, "title": f"Issue {n}", "body": None,
         "state": "open", "updated_at": "2026-01-01T00:00:00Z"} for n in range(100)
    ]
    process_sync(job_id, factory, github_auth)
    with factory() as db:
        assert db.get(SyncJob, job_id).status == "partial"


def test_sync_discards_fetched_data_if_access_changes_in_flight(client, factory, github_auth):
    from app.domain.models import Issue, SyncJob
    from app.workers.tasks import process_sync

    sign_in(client)
    assert client.post("/v1/installations/901/enroll", headers=csrf(client)).status_code == 200
    job_id = client.post("/v1/installations/901/repositories/902/select", headers=csrf(client)).json()["sync_job_id"]
    original = github_auth.issues

    def change_access(token, full_name):
        records = original(token, full_name)
        github_auth.include_repository = False
        return records

    github_auth.issues = change_access
    process_sync(job_id, factory, github_auth)
    with factory() as db:
        assert db.get(SyncJob, job_id).status == "ignored"
        assert db.get(Issue, 990) is None
