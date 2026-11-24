"""Opt-in PR outbox delivery through real Redis, Celery and disposable PostgreSQL."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest
from celery import Celery
from redis import Redis
from sqlalchemy import select
from app.core.config import get_settings
from app.domain.models import PRReview, PRReviewFinding, PRReviewOutbox
from test_auth_enrollment import csrf, github_auth, sign_in  # noqa: F401
from test_p17_celery_race import p17_guard  # noqa: F401


def wait_for(test, timeout=35):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        result = test()
        if result:
            return result
        time.sleep(.05)
    raise AssertionError("timed out waiting for PR worker")


@pytest.mark.parametrize("mode", ["user", "app", "rate", "fork", "typescript"], ids=["user-token", "mock-installation-token", "rate-limit", "public-fork", "typescript"])
def test_real_synthetic_pr_delivery(monkeypatch, request, tmp_path, mode):
    app_mode = mode == "app"
    db_url, redis_url, marker = request.getfixturevalue("p17_guard")
    client = request.getfixturevalue("client")
    factory = request.getfixturevalue("factory")
    github = request.getfixturevalue("github_auth")
    from test_pr_review_api import _pull
    def pinned_pull():
        item = _pull()
        if mode == "fork":
            item["head"]["repo"] = {"id": 903, "full_name": "contributor/public", "private": False}
        return item
    github.pull = lambda token, repo, number: pinned_pull()
    monkeypatch.setattr(get_settings(), "pr_reviews_enabled", True)
    if mode == "typescript":
        for name, value in {
            "pr_typescript_review_enabled": True,
            "pr_typescript_node_path": "/Users/roshan/Library/Application Support/RepoPilot/toolchains/p6/node-v24.18.0-darwin-arm64/bin/node",
            "pr_typescript_node_sha256": "ee6fb0e015284d83a91e8ec5213f43a157f8a392b58555301682892ba928c04a",
            "pr_typescript_compiler_path": "/Volumes/;;;;;;;;;;;;;/Project/RepoPilot/apps/web/node_modules/typescript/lib/typescript.js",
            "pr_typescript_compiler_sha256": "3ae902c92cc44dace175c0e69e13a4b0899f6983c6121d76b9ab8dd5795e7675",
        }.items():
            monkeypatch.setattr(get_settings(), name, value)
    private_key = None
    if app_mode:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from app.modules.github import installation_token
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_key = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                        serialization.NoEncryption()).decode()
        class Issuer:
            def token(self, installation, repository):
                assert (installation, repository) == (901, 902)
                return "synthetic-installation-token"
        monkeypatch.setattr(get_settings(), "github_installation_auth_enabled", True)
        monkeypatch.setattr(installation_token, "get_installation_issuer", lambda: Issuer())
    sign_in(client)
    assert client.post("/v1/installations/901/enroll", headers=csrf(client)).status_code == 200
    assert client.post("/v1/installations/901/repositories/902/select", headers=csrf(client)).status_code == 200
    root = "/v1/repositories/902/pr-reviews"
    created = client.post(root, json={"url": "https://github.com/alice/public/pull/7"}, headers=csrf(client))
    assert created.status_code == 202
    rid = created.json()["id"]
    queue = "p17_race_" + uuid4().hex
    api_dir = Path(__file__).resolve().parents[1]
    env = {"PATH": os.defpath, "HOME": str(tmp_path), "PYTHONPATH": str(api_dir), "PYTHONUNBUFFERED": "1",
           "APP_ENV": "test", "PR_BROKER_TEST": "1", "P17_MARKER": marker, "P17_QUEUE": queue,
           "DATABASE_URL": db_url, "REDIS_URL": redis_url, "GITHUB_WEBHOOK_SECRET": "test-" + "x" * 40,
           "GITHUB_OAUTH_ENABLED": "true", "GITHUB_APP_ID": "123", "GITHUB_CLIENT_ID": "fixture",
           "GITHUB_CLIENT_SECRET": "fixture", "GITHUB_TOKEN_ENCRYPTION_KEY": get_settings().github_token_encryption_key.get_secret_value(),
           "GITHUB_CALLBACK_URL": "http://localhost:3000/api/auth/callback", "WEB_ORIGIN": "http://localhost:3000",
           "PR_REVIEWS_ENABLED": "true", "PATCH_LOCAL_MODEL_ENABLED": "false", "PATCH_PROPOSALS_ENABLED": "false"}
    if app_mode:
        env.update(PR_APP_TOKEN_TEST="1", GITHUB_INSTALLATION_AUTH_ENABLED="true", GITHUB_APP_PRIVATE_KEY=private_key)
    if mode == "rate":
        env.update(PR_RATE_TEST="1")
    if mode == "fork":
        env.update(PR_FORK_TEST="1")
    if mode == "typescript":
        config = get_settings()
        env.update(PR_TS_TEST="1", PR_TYPESCRIPT_REVIEW_ENABLED="true",
            PR_TYPESCRIPT_NODE_PATH=config.pr_typescript_node_path,
            PR_TYPESCRIPT_NODE_SHA256=config.pr_typescript_node_sha256,
            PR_TYPESCRIPT_COMPILER_PATH=config.pr_typescript_compiler_path,
            PR_TYPESCRIPT_COMPILER_SHA256=config.pr_typescript_compiler_sha256)
    workers = []
    log = tmp_path / "worker.log"
    def launch(args, name):
        output = open(tmp_path / name, "wb")
        process = subprocess.Popen(args, cwd=api_dir, env=env, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        output.close()
        workers.append(process)
        return process
    try:
        child = launch([sys.executable, "-m", "celery", "-A", "evaluation.pr_review_celery_support:celery", "worker", "--pool=solo", "--concurrency=1", "-Q", queue, "--hostname=prtest@localhost", "--loglevel=INFO", "--without-gossip", "--without-mingle"], "worker.log")
        wait_for(lambda: log.exists() and b"ready." in log.read_bytes() or child.poll() is not None)
        assert child.poll() is None
        launch([sys.executable, "-m", "evaluation.pr_review_celery_support"], "dispatcher.log")
        if mode == "rate":
            def scheduled():
                with factory() as db:
                    job, event = db.get(PRReview, rid), db.get(PRReviewOutbox, rid)
                    return (job.status == "queued" and job.error_code == "github_rate_limited"
                            and job.next_retry_at and event.status == "pending" and event.attempts > 0)
            wait_for(scheduled)
            sender = Celery("pr-rate-sender", broker=redis_url)
            try:
                needle = b"Task process_pr_review[" + rid.encode() + b"] received"
                success = b"Task process_pr_review[" + rid.encode() + b"] succeeded"
                wait_for(lambda: log.read_bytes().count(success) >= 1)
                received_before, succeeded_before = log.read_bytes().count(needle), log.read_bytes().count(success)
                sender.send_task("process_pr_review", args=[rid], task_id=rid, queue=queue, retry=False)
                wait_for(lambda: log.read_bytes().count(needle) > received_before)
                wait_for(lambda: log.read_bytes().count(success) > succeeded_before)
            finally:
                sender.close()
            with factory() as db:
                job, event = db.get(PRReview, rid), db.get(PRReviewOutbox, rid)
                assert job.status == "queued" and job.attempts == 1 and job.head_sha == "b" * 40
                assert job.next_retry_at == event.next_dispatch_at and event.status == "pending"
                assert db.scalars(select(PRReviewFinding).where(PRReviewFinding.review_id == rid)).all() == []
            return
        def completed():
            with factory() as db:
                job = db.get(PRReview, rid)
                event = db.get(PRReviewOutbox, rid)
                return job.status == "completed" and event.status == "processed" and event.attempts > 0
        wait_for(completed)
        assert b"Task process_pr_review[" + rid.encode() + b"] received" in log.read_bytes()
        with factory() as db:
            findings = db.scalars(select(PRReviewFinding).where(PRReviewFinding.review_id == rid)).all()
            assert len(findings) == 1
            assert findings[0].path == ("src/demo.ts" if mode == "typescript" else "src/demo.py")
            if mode == "typescript":
                assert findings[0].rule_id == "TS-EVAL-001" and findings[0].start_line == 2
            fid = findings[0].id
            assert db.get(PRReview, rid).coverage == "partial"
            if mode == "fork":
                assert db.get(PRReview, rid).head_repository_id == 903
                assert findings[0].evidence["head_repository_id"] == "903"
        # Exercise duplicate delivery through the real broker, then confirm it did
        # not create another finding or claim a second attempt.
        sender = Celery("pr-integration-sender", broker=redis_url)
        try:
            needle = b"Task process_pr_review[" + rid.encode() + b"] received"
            success = b"Task process_pr_review[" + rid.encode() + b"] succeeded"
            wait_for(lambda: log.read_bytes().count(success) >= 1)
            received_before = log.read_bytes().count(needle)
            succeeded_before = log.read_bytes().count(success)
            sender.send_task("process_pr_review", args=[rid], task_id=rid, queue=queue, retry=False)
            wait_for(lambda: log.read_bytes().count(needle) > received_before)
            wait_for(lambda: log.read_bytes().count(success) > succeeded_before)
        finally:
            sender.close()
        with factory() as db:
            assert len(db.scalars(select(PRReviewFinding).where(PRReviewFinding.review_id == rid)).all()) == 1
            assert db.get(PRReview, rid).attempts == 1
        github.pull = lambda token, repo, number: {**pinned_pull(), "changed_files": 1}
        feedback = root + f"/{rid}/findings/{fid}/feedback"
        assert client.post(feedback, json={"state": "useful"}).status_code == 403
        assert client.post(feedback, json={"state": "useful"}, headers=csrf(client)).status_code == 200
        detail = client.get(root + "/" + rid)
        assert detail.status_code == 200 and detail.json()["findings"][0]["feedback_state"] == "useful"
        assert client.get(root + "/" + rid).json()["findings"][0]["feedback_state"] == "useful"
    finally:
        for process in reversed(workers):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
        broker = Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
        try:
            assert broker.get("p17:disposable-marker") == marker.encode()
            broker.delete(queue)
        finally:
            broker.close()
