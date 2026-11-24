"""Opt-in genuine Celery/PostgreSQL lease fencing; never uses normal services.

A disposable PG database and Redis instance must be independently provisioned with the
same private random marker in the database comment and p17:disposable-marker key.
See docs/p17-local-closure-and-execution-handoff.md for the opt-in command.
"""
import os
import re
import signal
import shutil
import threading
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import psycopg
import pytest
from redis import Redis
from sqlalchemy import select, text
from sqlalchemy.engine import make_url

from app.domain.models import PatchOutbox, PatchProposal
from app.core.config import get_settings
from test_patch_proposals import SyntheticProvider, create, enable, github_auth, parent_setup  # noqa: F401


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def validate_targets(db_url, redis_url, marker):
    db = make_url(db_url)
    broker = urlsplit(redis_url)
    require(re.fullmatch(r"[0-9a-f]{64}", marker), "invalid marker")
    require(db.drivername == "postgresql+psycopg" and db.host == "127.0.0.1" and db.port not in (None, 5432), "invalid database endpoint")
    require(db.username == "p17_admin" and db.password and re.fullmatch(r"repopilot_p17_[0-9a-f]{16}", db.database or ""), "invalid database identity")
    require(broker.scheme == "redis" and broker.hostname == "127.0.0.1" and broker.port not in (None, 6379) and broker.password and broker.path == "/0" and not broker.query and not broker.fragment, "invalid broker endpoint")
    with psycopg.connect(host=db.host, port=db.port, user=db.username, password=db.password,
                         dbname=db.database, connect_timeout=2) as c:
        identity = c.execute("select current_database(),current_user,shobj_description(oid,'pg_database') from pg_database where datname=current_database()").fetchone()
        require(identity == (db.database, db.username, "p17:" + marker), "database marker mismatch")
    redis = Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
    try:
        require(redis.get("p17:disposable-marker") == marker.encode(), "broker marker mismatch")
    finally:
        redis.close()


@pytest.fixture
def p17_guard(monkeypatch):
    if os.environ.get("P17_ENABLE_CELERY_RACE") != "1":
        pytest.skip("P17 real worker test unavailable: explicit disposable integration opt-in required")
    required = ("P17_DATABASE_URL", "P17_REDIS_URL", "P17_MARKER")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        pytest.fail("P17 real worker test unavailable: missing " + ", ".join(missing), pytrace=False)
    db_url, redis_url, marker = (os.environ[name] for name in required)
    validate_targets(db_url, redis_url, marker)
    # The standard project's test fixture is destructive; only select it after both guards.
    monkeypatch.setenv("TEST_DATABASE_URL", db_url)
    return db_url, redis_url, marker


def test_p17_guard_rejects_invalid_targets_before_connecting(monkeypatch):
    def never_connect(*args, **kwargs):
        raise AssertionError("guard tried to connect before rejecting unsafe configuration")
    monkeypatch.setattr(psycopg, "connect", never_connect)
    with pytest.raises(RuntimeError, match="invalid marker"):
        validate_targets("postgresql+psycopg://p17_admin:pw@127.0.0.1:51475/repopilot_p17_0123456789abcdef", "redis://:pw@127.0.0.1:16417/0", "bad")
    with pytest.raises(RuntimeError, match="invalid database endpoint"):
        validate_targets("postgresql+psycopg://p17_admin:pw@localhost:5432/repopilot_p17_0123456789abcdef", "redis://:pw@127.0.0.1:16417/0", "a" * 64)
    with pytest.raises(RuntimeError, match="invalid broker endpoint"):
        validate_targets("postgresql+psycopg://p17_admin:pw@127.0.0.1:51475/repopilot_p17_0123456789abcdef", "redis://:pw@localhost:6379/0", "a" * 64)


def eventually(predicate, *, timeout=35, label="condition"):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = predicate()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError(f"Timed out waiting for {label}")


def test_real_two_worker_expiry_and_stale_completions(p17_guard, monkeypatch, request, tmp_path):
    # Resolve these only after guarding both endpoints and pinning TEST_DATABASE_URL.
    client = request.getfixturevalue("client")
    factory = request.getfixturevalue("factory")
    github = request.getfixturevalue("github_auth")
    parent, _, _ = parent_setup(client, factory, github, monkeypatch)
    enable(monkeypatch, SyntheticProvider())
    db_url, redis_url, marker = p17_guard
    settings = get_settings()
    api_dir = Path(__file__).resolve().parents[1]
    queue = "p17_race_" + uuid4().hex
    race_dir = tmp_path / "race"
    race_dir.mkdir(mode=0o700)
    base_env = {
        "PATH": os.defpath, "HOME": str(tmp_path), "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": str(api_dir), "APP_ENV": "test", "P17_RUN": "1", "P17_MARKER": marker,
        "P17_QUEUE": queue, "P17_RACE_DIR": str(race_dir), "DATABASE_URL": db_url, "REDIS_URL": redis_url,
        "GITHUB_WEBHOOK_SECRET": "p17-test-webhook-" + "x" * 40,
        "GITHUB_OAUTH_ENABLED": "true", "GITHUB_APP_ID": "123", "GITHUB_CLIENT_ID": "fixture",
        "GITHUB_CLIENT_SECRET": "fixture-secret", "GITHUB_TOKEN_ENCRYPTION_KEY": settings.github_token_encryption_key.get_secret_value(),
        "GITHUB_CALLBACK_URL": "http://localhost:3000/api/auth/callback", "WEB_ORIGIN": "http://localhost:3000",
        "PATCH_PROPOSALS_ENABLED": "true", "PATCH_GENERATION_PROVIDER": "unavailable",
        "PATCH_LOCAL_MODEL_ENABLED": "false", "PATCH_WORKER_LEASE_SECONDS": "5",
    }
    children = []
    readers = []

    def drain(pipe, path):
        with path.open("ab", buffering=0) as output:
            remaining = 65536
            while block := os.read(pipe.fileno(), 4096):
                if remaining:
                    part = block[:remaining]
                    output.write(part)
                    remaining -= len(part)
        pipe.close()

    def launch(role):
        env = {**base_env, "P17_ROLE": role}
        path = race_dir / (role + ".log")
        if role == "dispatcher":
            args = [sys.executable, "-m", "evaluation.p17_celery_race_support"]
        else:
            args = [sys.executable, "-m", "celery", "-A", "evaluation.p17_celery_race_support:celery", "worker",
                    "--pool=solo", "--concurrency=1", "-Q", queue, "--hostname=p17-" + role.lower() + "@localhost",
                    "--loglevel=INFO", "--without-gossip", "--without-mingle"]
        process = subprocess.Popen(args, cwd=api_dir, env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        children.append(process)
        reader = threading.Thread(target=drain, args=(process.stdout, path), daemon=True)
        reader.start()
        readers.append(reader)
        if role != "dispatcher":
            eventually(lambda: path.exists() and b"ready." in path.read_bytes() or process.poll() is not None,
                       label=f"worker {role} startup")
            assert process.poll() is None, f"worker {role} exited; inspect {path}"
        return process, path

    def terminate(process):
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=5)

    def state(pid):
        with factory() as db:
            task = db.scalar(select(PatchProposal).where(PatchProposal.id == pid))
            outbox = db.get(PatchOutbox, pid)
            return (task.status, task.review_state, task.lease_token, task.lease_expires_at,
                    task.diff, task.error_code, outbox.status, outbox.attempts, db.scalar(text("select clock_timestamp()")))

    try:
        a, a_log = launch("A")
        dispatcher, _ = launch("dispatcher")
        for mode in ("late-success", "late-error"):
            for name in ("A.entered", "A.release", "B.entered", "B.release", "late-error"):
                (race_dir / name).unlink(missing_ok=True)
            if mode == "late-error":
                (race_dir / "late-error").touch(mode=0o600)
            pid = create(client, parent)
            eventually(lambda: (race_dir / "A.entered").exists() or a.poll() is not None, label="worker A pause")
            assert a.poll() is None, f"worker A exited; inspect {a_log}"
            first = state(pid)
            assert first[0] == "generating" and first[2] and first[3] and first[6] == "pending"
            b, b_log = launch("B")
            try:
                eventually(lambda: (race_dir / "B.entered").exists() or b.poll() is not None, label="worker B reclaim")
                assert b.poll() is None, f"worker B exited; inspect {b_log}"
                second = state(pid)
                assert second[0] == "generating" and second[2] and second[2] != first[2]
                assert first[3] <= second[8]
                assert second[6] == "pending"
                (race_dir / "B.release").touch(mode=0o600)
                final = eventually(lambda: (x if (x := state(pid))[0] == "static_validated" and x[6] == "processed" else None),
                                   timeout=15, label="worker B completion")
                assert final[1] == "unreviewed" and final[4] and final[5] is None
                (race_dir / "A.release").touch(mode=0o600)
                needle = f"Task process_patch_proposal[{pid}] succeeded".encode()
                eventually(lambda: needle in a_log.read_bytes() or a.poll() is not None, label="worker A finalization")
                assert a.poll() is None
                assert state(pid)[:8] == final[:8], f"stale {mode} changed persisted proposal/outbox"
            finally:
                terminate(b)
    finally:
        for process in reversed(children):
            terminate(process)
        for reader in readers:
            reader.join(timeout=3)
        # Queue name is unique to this guarded test; never purge shared broker namespaces.
        redis = Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
        try:
            require(re.fullmatch(r"p17_race_[0-9a-f]{32}", queue), "unsafe cleanup queue")
            require(redis.get("p17:disposable-marker") == marker.encode(), "broker marker changed before cleanup")
            redis.delete(queue)
        finally:
            redis.close()
            if sys.exc_info()[0] is not None:
                for path in sorted(race_dir.glob("*.log")):
                    content = path.read_text(errors="replace")[-4000:]
                    content = re.sub(r"redis://[^@\s]+@", "redis://<redacted>@", content)
                    print(f"P17 bounded {path.name} diagnostics:\n{content}")
            shutil.rmtree(race_dir)
