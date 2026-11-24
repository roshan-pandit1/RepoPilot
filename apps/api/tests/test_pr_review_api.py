"""In-process API contract tests; no GitHub network or repository execution."""
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.domain.models import PRReview, PRReviewFinding, PRReviewOutbox
from app.modules.pr_review.worker import process_pr_review
from app.workers.dispatcher import dispatch_once
from test_auth_enrollment import csrf, github_auth as github_auth, sign_in


@pytest.fixture
def enrolled(client, github_auth, monkeypatch):
    monkeypatch.setattr(get_settings(), "pr_reviews_enabled", True)
    sign_in(client)
    assert client.post("/v1/installations/901/enroll", headers=csrf(client)).status_code == 200
    assert client.post("/v1/installations/901/repositories/902/select", headers=csrf(client)).status_code == 200
    github_auth.pull = lambda token, repo, number: _pull()
    return github_auth


def _pull(head="b" * 40):
    return {"id": 101, "number": 7, "html_url": "https://github.com/alice/public/pull/7",
            "title": "Synthetic PR", "user": {"login": "alice"}, "changed_files": 0,
            "base": {"repo": {"id": 902, "full_name": "alice/public"}, "sha": "a" * 40},
            "head": {"repo": {"id": 902, "full_name": "alice/public"}, "sha": head}}


def test_create_requires_csrf_and_repository_url(client, factory, enrolled):
    root = "/v1/repositories/902/pr-reviews"
    valid = {"url": "https://github.com/alice/public/pull/7"}
    assert client.post(root, json=valid).status_code == 403
    for url in ["https://github.com/other/repo/pull/7", "https://github.com/alice/public/pull/0",
                "https://github.com/alice/public/pull/7?x=1", "http://github.com/alice/public/pull/7"]:
        assert client.post(root, json={"url": url}, headers=csrf(client)).status_code == 422
    created = client.post(root, json=valid, headers=csrf(client))
    assert created.status_code == 202
    review_id = created.json()["id"]
    assert client.post(root, json=valid, headers=csrf(client)).json()["id"] == review_id
    assert client.get(root).json()["items"][0]["id"] == review_id
    with factory() as db:
        assert db.get(PRReviewOutbox, review_id).status == "pending"
        assert len(db.scalars(select(PRReview)).all()) == 1


def test_outbox_publishes_and_duplicate_worker_delivery_is_idempotent(client, factory, enrolled):
    root = "/v1/repositories/902/pr-reviews"
    rid = client.post(root, json={"url": "https://github.com/alice/public/pull/7"}, headers=csrf(client)).json()["id"]
    sent = []
    dispatch_once(factory, publish=lambda _: None, publish_sync=lambda _: None, publish_index=lambda _: None,
        publish_embedding=lambda _: None, publish_investigation=lambda _: None, publish_report=lambda _: None,
        publish_patch=lambda _: None, publish_pr=sent.append)
    assert sent == [rid]
    class Source:
        def commit(self, token, repo, sha):
            return {"sha": sha}
    class Pull:
        def pull(self, token, repo, number):
            return _pull()
        def pull_files(self, token, repo, number):
            return []
    process_pr_review(rid, factory, enrolled, Pull(), Source())
    process_pr_review(rid, factory, enrolled, Pull(), Source())
    enrolled.pull = lambda token, repo, number: _pull()
    result = client.get(root + "/" + rid)
    assert result.status_code == 200
    assert result.json()["status"] == "completed" and result.json()["coverage"] == "partial"
    with factory() as db:
        assert db.get(PRReviewOutbox, rid).status == "processed"
        assert db.get(PRReview, rid).attempts == 1


def test_feedback_rejects_stale_and_revoked_access(client, factory, enrolled):
    root = "/v1/repositories/902/pr-reviews"
    rid = client.post(root, json={"url": "https://github.com/alice/public/pull/7"}, headers=csrf(client)).json()["id"]
    fid = str(uuid4())
    with factory.begin() as db:
        item = db.get(PRReview, rid)
        item.status, item.github_pr_id, item.base_sha, item.head_sha = "completed", 101, "a" * 40, "b" * 40
        db.add(PRReviewFinding(id=fid, review_id=rid, repository_id=902, tenant_id=item.tenant_id,
            fingerprint="f" * 64, rule_id="PY-SHELL-001", category="SECURITY", severity="MEDIUM",
            confidence="MEDIUM", path="f.py", start_line=1, end_line=1, explanation="Check", recommendation="Review",
            evidence={"commit_sha": "b" * 40}))
    enrolled.pull = lambda token, repo, number: _pull()
    path = root + f"/{rid}/findings/{fid}/feedback"
    assert client.post(path, json={"state": "useful"}).status_code == 403
    assert client.post(path, json={"state": "useful", "reason": "helpful"}, headers=csrf(client)).status_code == 200
    assert client.get(root + "/" + rid).json()["findings"][0]["feedback_state"] == "useful"
    enrolled.pull = lambda token, repo, number: _pull("c" * 40)
    assert client.get(root + "/" + rid).json()["stale"] is True
    assert client.post(path, json={"state": "false_positive"}, headers=csrf(client)).status_code == 409
    enrolled.include_repository = False
    assert client.get(root + "/" + rid).status_code == 404
    assert client.post(path, json={"state": "useful"}, headers=csrf(client)).status_code == 404


def test_real_worker_scans_synthetic_changed_source_and_persists_evidence(client, factory, enrolled):
    from hashlib import sha1, sha256

    root = "/v1/repositories/902/pr-reviews"
    rid = client.post(root, json={"url": "https://github.com/alice/public/pull/7"}, headers=csrf(client)).json()["id"]
    before = b"import subprocess\n\ndef run(value):\n    return None\n"
    after = b"import subprocess\n\ndef run(value):\n    return subprocess.run(f\"echo {value}\", shell=True)\n"
    patch = "@@ -1,4 +1,4 @@\n import subprocess\n \n def run(value):\n-    return None\n+    return subprocess.run(f\"echo {value}\", shell=True)"
    def blob(data):
        return sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    class Source:
        def commit(self, token, repo, sha):
            return {"sha": sha}
        def tree_file(self, token, repo, sha, path):
            raw = before if sha == "a" * 40 else after
            return {"path": path, "sha": blob(raw), "size": len(raw)}
        def blob(self, token, repo, sha, size):
            return before if sha == blob(before) else after
    class Pull:
        def pull(self, token, repo, number):
            return {**_pull(), "changed_files": 1}
        def pull_files(self, token, repo, number):
            return [{"filename": "src/demo.py", "status": "modified", "additions": 1,
                     "deletions": 1, "patch": patch}]
    process_pr_review(rid, factory, enrolled, Pull(), Source())
    enrolled.pull = lambda token, repo, number: {**_pull(), "changed_files": 1}
    response = client.get(root + "/" + rid)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed" and body["coverage"] == "partial"
    assert len(body["findings"]) == 1
    finding = body["findings"][0]
    assert finding["path"] == "src/demo.py" and finding["start_line"] == 4
    assert finding["evidence"]["file_sha256"] == sha256(after).hexdigest()
    assert finding["evidence"]["commit_sha"] == "b" * 40
    assert client.post(root + f"/{rid}/findings/{finding['id']}/feedback",
                       json={"state": "useful"}, headers=csrf(client)).status_code == 200


def test_worker_persists_safe_rate_limit_failure_without_publishing_partial(client, factory, enrolled):
    from app.modules.github.client import GitHubFailure

    root = "/v1/repositories/902/pr-reviews"
    rid = client.post(root, json={"url": "https://github.com/alice/public/pull/7"}, headers=csrf(client)).json()["id"]
    class LimitedPull:
        def pull(self, token, name, number):
            raise GitHubFailure("github_rate_limited")
    process_pr_review(rid, factory, enrolled, LimitedPull(), object())
    process_pr_review(rid, factory, enrolled, LimitedPull(), object())
    result = client.get(root + "/" + rid)
    assert result.status_code == 200
    assert result.json()["status"] == "failed"
    assert result.json()["error_code"] == "github_rate_limited"
    assert result.json()["files"] == [] and result.json()["findings"] == []
    with factory() as db:
        assert db.get(PRReview, rid).attempts == 1
        assert db.get(PRReviewOutbox, rid).status == "processed"


def test_request_pins_pr_before_outbox_and_changed_head_creates_new_job(client, factory, enrolled):
    root = "/v1/repositories/902/pr-reviews"
    data = {"url": "https://github.com/alice/public/pull/7"}
    first = client.post(root, json=data, headers=csrf(client))
    assert first.status_code == 202
    with factory() as db:
        job = db.get(PRReview, first.json()["id"])
        assert (job.github_pr_id, job.base_sha, job.head_sha) == (101, "a" * 40, "b" * 40)
        assert db.get(PRReviewOutbox, job.id).status == "pending"
    enrolled.pull = lambda token, repo, number: _pull("c" * 40)
    second = client.post(root, json=data, headers=csrf(client))
    assert second.status_code == 202 and second.json()["id"] != first.json()["id"]
    assert second.json()["head_sha"] == "c" * 40


def test_unavailable_pr_identity_cannot_enqueue(client, factory, enrolled):
    from app.modules.github.client import GitHubFailure
    enrolled.pull = lambda *args: (_ for _ in ()).throw(GitHubFailure("github_rate_limited"))
    response = client.post("/v1/repositories/902/pr-reviews", json={"url": "https://github.com/alice/public/pull/7"}, headers=csrf(client))
    assert response.status_code == 503
    with factory() as db:
        assert db.scalars(select(PRReview)).all() == []
        assert db.scalars(select(PRReviewOutbox)).all() == []


def test_changed_head_rejected_before_source_read(client, factory, enrolled):
    root = "/v1/repositories/902/pr-reviews"
    rid = client.post(root, json={"url": "https://github.com/alice/public/pull/7"}, headers=csrf(client)).json()["id"]
    class ChangedPull:
        def pull(self, token, repo, number):
            return _pull("c" * 40)
        def pull_files(self, *args):
            pytest.fail("changed review must not retrieve source")
    process_pr_review(rid, factory, enrolled, ChangedPull(), object())
    with factory() as db:
        job = db.get(PRReview, rid)
        assert job.status == "failed" and job.error_code == "pull_request_changed"
        assert job.head_sha == "b" * 40


def test_retryable_server_failure_is_delayed_and_stays_pinned(client, factory, enrolled, monkeypatch):
    from datetime import timedelta
    from app.modules.github.client import GitHubFailure
    from app.modules.pr_review import worker
    from app.modules.pr_review.worker import now as actual_now

    root = "/v1/repositories/902/pr-reviews"
    rid = client.post(root, json={"url": "https://github.com/alice/public/pull/7"}, headers=csrf(client)).json()["id"]
    class BrokenPull:
        def pull(self, *args):
            raise GitHubFailure("github_temporarily_unavailable")
    process_pr_review(rid, factory, enrolled, BrokenPull(), object())
    with factory() as db:
        job, event = db.get(PRReview, rid), db.get(PRReviewOutbox, rid)
        assert job.status == "queued" and job.attempts == 1 and job.head_sha == "b" * 40
        assert job.error_code == "github_temporarily_unavailable" and event.status == "pending"
        assert event.next_dispatch_at > job.updated_at
    process_pr_review(rid, factory, enrolled, BrokenPull(), object())
    with factory() as db:
        assert db.get(PRReview, rid).attempts == 1
    future = actual_now() + timedelta(seconds=31)
    monkeypatch.setattr(worker, "now", lambda: future)
    class Pull:
        def pull(self, *args): return _pull()
        def pull_files(self, *args): return []
    class Source:
        def commit(self, token, repo, sha): return {"sha": sha}
    process_pr_review(rid, factory, enrolled, Pull(), Source())
    with factory() as db:
        job = db.get(PRReview, rid)
        assert job.status == "completed" and job.attempts == 2 and job.head_sha == "b" * 40
        assert db.get(PRReviewOutbox, rid).status == "processed"


def test_server_retry_stops_after_three_attempts(client, factory, enrolled, monkeypatch):
    from datetime import timedelta
    from app.modules.github.client import GitHubFailure
    from app.modules.pr_review import worker
    from app.modules.pr_review.worker import now as actual_now

    root = "/v1/repositories/902/pr-reviews"
    rid = client.post(root, json={"url": "https://github.com/alice/public/pull/7"}, headers=csrf(client)).json()["id"]
    class BrokenPull:
        def pull(self, *args): raise GitHubFailure("github_temporarily_unavailable")
    start = actual_now()
    for seconds in (0, 31, 92):
        monkeypatch.setattr(worker, "now", lambda seconds=seconds: start + timedelta(seconds=seconds))
        process_pr_review(rid, factory, enrolled, BrokenPull(), object())
    with factory() as db:
        job = db.get(PRReview, rid)
        assert job.status == "failed" and job.attempts == 3
        assert job.error_code == "github_temporarily_unavailable"
        assert db.get(PRReviewOutbox, rid).status == "processed"


@pytest.mark.parametrize("code,status", [
    ("github_authentication_failed", 401), ("github_permission_denied", 403),
    ("github_not_found", 404), ("github_rate_limited", 503),
    ("github_secondary_rate_limited", 503), ("github_temporarily_unavailable", 503),
])
def test_pinning_failure_is_classified_without_enqueuing(client, factory, enrolled, code, status):
    from app.modules.github.client import GitHubFailure
    enrolled.pull = lambda *args: (_ for _ in ()).throw(GitHubFailure(code))
    response = client.post("/v1/repositories/902/pr-reviews", json={"url": "https://github.com/alice/public/pull/7"}, headers=csrf(client))
    assert response.status_code == status
    assert code not in response.text
    with factory() as db:
        assert not db.scalars(select(PRReview)).all()
        assert not db.scalars(select(PRReviewOutbox)).all()


def test_rate_limit_deadline_survives_duplicate_and_keeps_pins(client, factory, enrolled, monkeypatch):
    from datetime import timedelta
    from app.modules.github.client import GitHubFailure
    from app.modules.pr_review import worker
    from app.modules.pr_review.worker import now as actual_now

    root = "/v1/repositories/902/pr-reviews"
    rid = client.post(root, json={"url": "https://github.com/alice/public/pull/7"}, headers=csrf(client)).json()["id"]
    start = actual_now()
    retry_at = start + timedelta(seconds=130)
    class LimitedPull:
        def pull(self, *args): raise GitHubFailure("github_rate_limited", retry_at=retry_at)
    process_pr_review(rid, factory, enrolled, LimitedPull(), object())
    with factory() as db:
        job, event = db.get(PRReview, rid), db.get(PRReviewOutbox, rid)
        assert job.status == "queued" and job.attempts == 1 and job.head_sha == "b" * 40
        assert job.next_retry_at is not None and event.status == "pending"
        assert job.next_retry_at == event.next_dispatch_at
    process_pr_review(rid, factory, enrolled, LimitedPull(), object())
    with factory() as db:
        assert db.get(PRReview, rid).attempts == 1
    monkeypatch.setattr(worker, "now", lambda: retry_at + timedelta(seconds=1))
    class ChangedPull:
        def pull(self, *args): return _pull("c" * 40)
        def pull_files(self, *args): pytest.fail("changed head source must not be read")
    process_pr_review(rid, factory, enrolled, ChangedPull(), object())
    with factory() as db:
        job = db.get(PRReview, rid)
        assert job.status == "failed" and job.error_code == "pull_request_changed"
        assert job.head_sha == "b" * 40 and job.next_retry_at is None


def test_installation_token_used_only_after_authorization(client, factory, enrolled, monkeypatch):
    from app.modules.github import installation_token

    class Issuer:
        def __init__(self): self.calls = []
        def token(self, installation, repository):
            self.calls.append((installation, repository))
            return "fixture-installation-token"
    issuer = Issuer()
    monkeypatch.setattr(get_settings(), "github_installation_auth_enabled", True)
    monkeypatch.setattr(installation_token, "get_installation_issuer", lambda: issuer)
    def pinned(token, repo, number):
        assert token == "fixture-installation-token"
        return _pull()
    enrolled.pull = pinned
    root = "/v1/repositories/902/pr-reviews"
    response = client.post(root, json={"url": "https://github.com/alice/public/pull/7"}, headers=csrf(client))
    assert response.status_code == 202 and issuer.calls == [(901, 902)]
    enrolled.include_repository = False
    response = client.post(root, json={"url": "https://github.com/alice/public/pull/7"}, headers=csrf(client))
    assert response.status_code == 404 and issuer.calls == [(901, 902)]


def test_installation_issuer_failure_never_falls_back_to_user_token(client, factory, enrolled, monkeypatch):
    from app.modules.github import installation_token
    from app.modules.github.client import GitHubFailure
    class Issuer:
        def token(self, *args): raise GitHubFailure("github_permission_denied")
        def invalidate(self, *args): pass
    monkeypatch.setattr(get_settings(), "github_installation_auth_enabled", True)
    monkeypatch.setattr(installation_token, "get_installation_issuer", lambda: Issuer())
    enrolled.pull = lambda *args: pytest.fail("no PR fetch after issuance failure")
    response = client.post("/v1/repositories/902/pr-reviews", json={"url": "https://github.com/alice/public/pull/7"}, headers=csrf(client))
    assert response.status_code == 403
    with factory() as db:
        assert not db.scalars(select(PRReview)).all() and not db.scalars(select(PRReviewOutbox)).all()


def test_worker_uses_scoped_installation_token_and_rechecks_access(client, factory, enrolled, monkeypatch):
    from app.modules.github import installation_token

    class Issuer:
        def __init__(self):
            self.calls = []
            self.invalidated = []
        def token(self, installation, repository):
            self.calls.append((installation, repository))
            return "fixture-installation-token"
        def invalidate(self, installation, repository):
            self.invalidated.append((installation, repository))
    issuer = Issuer()
    monkeypatch.setattr(get_settings(), "github_installation_auth_enabled", True)
    monkeypatch.setattr(installation_token, "get_installation_issuer", lambda: issuer)
    enrolled.pull = lambda token, repo, number: _pull()
    root = "/v1/repositories/902/pr-reviews"
    rid = client.post(root, json={"url": "https://github.com/alice/public/pull/7"}, headers=csrf(client)).json()["id"]
    class Pull:
        def __init__(self): self.calls = 0
        def pull(self, token, repo, number):
            assert token == "fixture-installation-token"
            self.calls += 1
            if self.calls == 2:
                enrolled.include_repository = False
            return _pull()
        def pull_files(self, token, repo, number):
            assert token == "fixture-installation-token"
            return []
    class Source:
        def commit(self, token, repo, sha):
            assert token == "fixture-installation-token"
            return {"sha": sha}
    process_pr_review(rid, factory, enrolled, Pull(), Source())
    with factory() as db:
        job = db.get(PRReview, rid)
        assert job.status == "failed" and job.coverage is None
        assert db.scalars(select(PRReviewFinding).where(PRReviewFinding.review_id == rid)).all() == []
    assert issuer.calls == [(901, 902), (901, 902)]
    assert issuer.invalidated == [(901, 902)]


def test_worker_stops_before_blob_after_repository_deselection(client, factory, enrolled):
    from hashlib import sha1

    root = "/v1/repositories/902/pr-reviews"
    rid = client.post(root, json={"url": "https://github.com/alice/public/pull/7"},
                      headers=csrf(client)).json()["id"]
    raw = b"x = 1\n"
    object_id = sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    blob_calls = []

    class Source:
        def commit(self, token, repo, sha):
            return {"sha": sha}

        def tree_file(self, token, repo, sha, path):
            enrolled.include_repository = False
            return {"path": path, "sha": object_id, "size": len(raw)}

        def blob(self, *args):
            blob_calls.append(True)
            return raw

    class Pull:
        def pull(self, token, repo, number):
            return {**_pull(), "changed_files": 1}

        def pull_files(self, token, repo, number):
            return [{"filename": "src/demo.py", "status": "added", "additions": 1,
                     "deletions": 0, "patch": "@@ -0,0 +1,1 @@\n+x = 1"}]

    process_pr_review(rid, factory, enrolled, Pull(), Source())
    with factory() as db:
        job = db.get(PRReview, rid)
        assert job.status == "failed" and job.coverage is None
        assert job.error_code == "authorization_revoked"
        assert db.scalars(select(PRReviewFinding).where(PRReviewFinding.review_id == rid)).all() == []
    assert blob_calls == []


def test_public_fork_identity_persisted_and_changed_fork_creates_new_review(client, factory, enrolled):
    def pull(head_id=903, head_name="contributor/fork"):
        item = _pull()
        item["head"]["repo"] = {"id": head_id, "full_name": head_name, "private": False}
        return item
    enrolled.pull = lambda *args: pull()
    root = "/v1/repositories/902/pr-reviews"
    data = {"url": "https://github.com/alice/public/pull/7"}
    response = client.post(root, json=data, headers=csrf(client))
    assert response.status_code == 202
    rid = response.json()["id"]
    with factory() as db:
        job = db.get(PRReview, rid)
        assert (job.head_repository_id, job.head_repository_name) == (903, "contributor/fork")
        assert db.get(PRReviewOutbox, rid).status == "pending"
    enrolled.pull = lambda *args: pull(904, "other/fork")
    second = client.post(root, json=data, headers=csrf(client))
    assert second.status_code == 202 and second.json()["id"] != rid


def test_private_fork_is_rejected_before_enqueue(client, factory, enrolled):
    def pull(*args):
        item = _pull()
        item["head"]["repo"] = {"id": 903, "full_name": "private/fork", "private": True}
        return item
    enrolled.pull = pull
    response = client.post("/v1/repositories/902/pr-reviews", json={"url": "https://github.com/alice/public/pull/7"}, headers=csrf(client))
    assert response.status_code == 503
    with factory() as db:
        assert not db.scalars(select(PRReview)).all()


@pytest.mark.parametrize("head_id,head_name", [(None, "contributor/fork"), (903, None), (0, "contributor/fork")])
def test_database_rejects_incomplete_head_repository_identity(client, factory, enrolled, head_id, head_name):
    from sqlalchemy.exc import IntegrityError
    root = "/v1/repositories/902/pr-reviews"
    rid = client.post(root, json={"url": "https://github.com/alice/public/pull/7"}, headers=csrf(client)).json()["id"]
    with factory() as db:
        job = db.get(PRReview, rid)
        job.head_repository_id, job.head_repository_name = head_id, head_name
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_legacy_same_repository_queued_review_is_not_duplicated(client, factory, enrolled):
    root = "/v1/repositories/902/pr-reviews"
    data = {"url": "https://github.com/alice/public/pull/7"}
    rid = client.post(root, json=data, headers=csrf(client)).json()["id"]
    with factory.begin() as db:
        job = db.get(PRReview, rid)
        job.head_repository_id = job.head_repository_name = None
    assert client.post(root, json=data, headers=csrf(client)).json()["id"] == rid
    with factory() as db:
        assert len(db.scalars(select(PRReview)).all()) == 1


def test_superseded_pr_worker_cannot_publish_or_consume_outbox(client, factory, enrolled):
    root = "/v1/repositories/902/pr-reviews"
    rid = client.post(root, json={"url": "https://github.com/alice/public/pull/7"}, headers=csrf(client)).json()["id"]
    newer_lease = str(uuid4())
    class Pull:
        calls = 0
        def pull(self, token, repo, number):
            self.calls += 1
            if self.calls == 2:
                with factory.begin() as db:
                    job = db.get(PRReview, rid)
                    job.lease_token = newer_lease
            return _pull()
        def pull_files(self, *args):
            return []
    class Source:
        def commit(self, token, repo, sha):
            return {"sha": sha}
    process_pr_review(rid, factory, enrolled, Pull(), Source())
    with factory() as db:
        job, outbox = db.get(PRReview, rid), db.get(PRReviewOutbox, rid)
        assert job.status == "running" and job.lease_token == newer_lease
        assert outbox.status == "pending"
        assert db.scalars(select(PRReviewFinding).where(PRReviewFinding.review_id == rid)).all() == []


def test_review_metrics_are_aggregate_and_do_not_expose_source(client, factory, enrolled):
    root = "/v1/repositories/902/pr-reviews"
    rid = client.post(root, json={"url": "https://github.com/alice/public/pull/7"}, headers=csrf(client)).json()["id"]
    with factory.begin() as db:
        item = db.get(PRReview, rid)
        item.status = "completed"
        item.files = [{"path": "private-path.py", "coverage": "complete", "patch": "secret-source"},
                      {"path": "unsupported.ts", "coverage": "partial"}]
    detail = client.get(root + "/" + rid)
    assert detail.status_code == 200
    metrics = detail.json()["pilot_metrics"]
    assert metrics["recorded_files_checked"] == 1 and metrics["recorded_files_not_fully_checked"] == 1
    assert metrics["findings_returned"] == 0 and metrics["time_to_result_seconds"] >= 0
    assert metrics["model_invocations"] is None and metrics["compute_cost"] is None
    assert "secret-source" not in str(metrics) and "private-path.py" not in str(metrics)
    enrolled.include_repository = False
    assert client.get(root + "/" + rid).status_code == 404


@pytest.mark.parametrize("permissions", [None, {}, {"contents": "read"},
                                         {"contents": "write", "pull_requests": "read"},
                                         {"contents": "read", "pull_requests": "write"}])
def test_pr_review_requires_current_read_only_installation_permissions(client, factory, enrolled, permissions):
    enrolled.permissions = permissions
    response = client.post("/v1/repositories/902/pr-reviews",
        json={"url": "https://github.com/alice/public/pull/7"}, headers=csrf(client))
    assert response.status_code == 404
    with factory() as db:
        assert db.scalars(select(PRReview)).all() == []


def test_permission_downgrade_before_blob_stops_worker(client, factory, enrolled):
    from hashlib import sha1
    root = "/v1/repositories/902/pr-reviews"
    rid = client.post(root, json={"url": "https://github.com/alice/public/pull/7"}, headers=csrf(client)).json()["id"]
    raw = b"x = 1\n"
    object_id = sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    calls = []
    class Source:
        def commit(self, token, repo, sha): return {"sha": sha}
        def tree_file(self, token, repo, sha, path):
            enrolled.permissions = {"contents": "read"}
            return {"path": path, "sha": object_id, "size": len(raw)}
        def blob(self, *args):
            calls.append(True)
            return raw
    class Pull:
        def pull(self, *args): return {**_pull(), "changed_files": 1}
        def pull_files(self, *args):
            return [{"filename": "src/demo.py", "status": "added", "additions": 1,
                     "deletions": 0, "patch": "@@ -0,0 +1,1 @@\n+x = 1"}]
    process_pr_review(rid, factory, enrolled, Pull(), Source())
    with factory() as db:
        assert db.get(PRReview, rid).status == "failed"
        assert db.get(PRReview, rid).error_code == "authorization_revoked"
        assert db.scalars(select(PRReviewFinding).where(PRReviewFinding.review_id == rid)).all() == []
    assert calls == []
