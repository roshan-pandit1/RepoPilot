"""Guarded synthetic-only bootstrap for the opt-in real broker PR test."""
import os
import re
from hashlib import sha1
from urllib.parse import urlsplit
import psycopg
from redis import Redis
from sqlalchemy.engine import make_url


def require(value):
    if not value:
        raise RuntimeError("unsafe PR integration environment")


def guard():
    db = make_url(os.environ["DATABASE_URL"])
    broker = urlsplit(os.environ["REDIS_URL"])
    marker = os.environ["P17_MARKER"]
    require(os.environ.get("APP_ENV") == "test" and os.environ.get("PR_BROKER_TEST") == "1")
    require(re.fullmatch(r"[0-9a-f]{64}", marker) is not None)
    require(db.drivername == "postgresql+psycopg" and db.host == "127.0.0.1" and db.port not in (None, 5432))
    require(db.username == "p17_admin" and bool(db.password) and re.fullmatch(r"repopilot_p17_[0-9a-f]{16}", db.database or "") is not None)
    require(broker.scheme == "redis" and broker.hostname == "127.0.0.1" and broker.port not in (None, 6379) and bool(broker.password) and broker.path == "/0" and not broker.query and not broker.fragment)
    require(re.fullmatch(r"p17_race_[0-9a-f]{32}", os.environ["P17_QUEUE"]) is not None)
    with psycopg.connect(host=db.host, port=db.port, user=db.username, password=db.password, dbname=db.database, connect_timeout=2) as conn:
        row = conn.execute("select current_database(), current_user, shobj_description(oid,'pg_database') from pg_database where datname=current_database()").fetchone()
        require(row == (db.database, db.username, "p17:" + marker))
    broker_client = Redis.from_url(os.environ["REDIS_URL"], socket_connect_timeout=2, socket_timeout=2)
    try:
        require(broker_client.get("p17:disposable-marker") == marker.encode())
    finally:
        broker_client.close()


guard()
from app.modules.pr_review import worker  # noqa: E402
from app.workers.tasks import celery  # noqa: E402

if os.environ.get("PR_APP_TOKEN_TEST") == "1":
    import httpx
    from datetime import datetime, timedelta, timezone
    from app.modules.github import installation_token

    def token_response(request):
        require(request.url.host == "api.github.com" and request.method == "POST")
        return httpx.Response(201, json={"token": "synthetic-installation-token",
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=55)).isoformat(),
            "permissions": {"contents": "read", "pull_requests": "read", "metadata": "read"},
            "repositories": [{"id": 902}]})

    issuer = installation_token.InstallationTokenIssuer(123, os.environ["GITHUB_APP_PRIVATE_KEY"],
        transport=httpx.MockTransport(token_response))
    installation_token.get_installation_issuer = lambda: issuer

BEFORE = b"import subprocess\n\ndef run(value):\n    return None\n"
AFTER = b'import subprocess\n\ndef run(value):\n    return subprocess.run(f"echo {value}", shell=True)\n'
PATCH = '@@ -1,4 +1,4 @@\n import subprocess\n \n def run(value):\n-    return None\n+    return subprocess.run(f"echo {value}", shell=True)'

if os.environ.get("PR_TS_TEST") == "1":
    BEFORE = b"export function render(value: string) {\n  return value;\n}\n"
    AFTER = b"export function render(value: string) {\n  return eval(value);\n}\n"
    PATCH = "@@ -1,3 +1,3 @@\n export function render(value: string) {\n-  return value;\n+  return eval(value);\n }"


def blob(data):
    return sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


class Github:
    def installations(self, token):
        return [{"id": 901, "app_id": 123, "account": {"id": 77, "type": "User", "login": "alice"}, "suspended_at": None,
                 "permissions": {"contents": "read", "pull_requests": "read"}}]
    def repositories(self, token, installation):
        return [{"id": 902, "full_name": "alice/public", "private": False}]


class Pull:
    def __init__(self, *args, **kwargs):
        pass
    def pull(self, token, repo, number):
        if os.environ.get("PR_RATE_TEST") == "1":
            from datetime import datetime, timedelta, timezone
            from app.modules.github.client import GitHubFailure
            raise GitHubFailure("github_rate_limited", retry_at=datetime.now(timezone.utc) + timedelta(minutes=3))
        if os.environ.get("PR_APP_TOKEN_TEST") == "1":
            require(token == "synthetic-installation-token")
        head = ({"id": 903, "full_name": "contributor/public", "private": False}
                if os.environ.get("PR_FORK_TEST") == "1" else {"id": 902, "full_name": "alice/public"})
        return {"id": 101, "number": 7, "html_url": "https://github.com/alice/public/pull/7", "title": "Synthetic PR", "user": {"login": "alice"}, "changed_files": 1,
                "base": {"repo": {"id": 902, "full_name": "alice/public"}, "sha": "a" * 40}, "head": {"repo": head, "sha": "b" * 40}}
    def pull_files(self, token, repo, number):
        return [{"filename": "src/demo.ts" if os.environ.get("PR_TS_TEST") == "1" else "src/demo.py", "status": "modified", "additions": 1, "deletions": 1, "patch": PATCH}]


class Source:
    def repository(self, token, repo):
        require(os.environ.get("PR_FORK_TEST") == "1" and repo == "contributor/public")
        return {"id": 903, "full_name": repo, "private": False}
    def __init__(self, *args, **kwargs):
        pass
    def commit(self, token, repo, sha):
        require(repo == "alice/public")
        if os.environ.get("PR_APP_TOKEN_TEST") == "1":
            require(token == "synthetic-installation-token")
        return {"sha": sha}
    def tree_file(self, token, repo, sha, path):
        raw = BEFORE if sha == "a" * 40 else AFTER
        return {"path": path, "sha": blob(raw), "size": len(raw)}
    def blob(self, token, repo, sha, size):
        return BEFORE if sha == blob(BEFORE) else AFTER


worker.get_github_client = lambda: Github()
worker.PullClient = Pull
worker.GitHubSourceClient = Source
celery.conf.task_default_queue = os.environ["P17_QUEUE"]
if __name__ == "__main__":
    from app.workers.dispatcher import main
    main()
