import json
import os
import pathlib
import secrets
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import urllib.parse
import httpx
from cryptography.fernet import Fernet

if os.environ.get("RP_E2E_ALLOW") != "1":
    raise SystemExit("Set RP_E2E_ALLOW=1 for this isolated test only")
root = pathlib.Path(
    tempfile.mkdtemp(
        prefix="rp-fullstack-", dir="/Users/roshan/Library/Application Support/RepoPilot"
    )
)
root.chmod(0o700)
data = root / "pg"
sock = root / "sock"
sock.mkdir(mode=0o700)
password = secrets.token_hex(24)
marker = secrets.token_hex(32)
dbname = "repopilot_p17_" + secrets.token_hex(8)
queue = "p17_race_" + secrets.token_hex(16)
pg = "/opt/homebrew/opt/postgresql@16/bin/"
redisbin = "/Users/roshan/Library/Application Support/RepoPilot/toolchains/redis-p14/redis-7.4.11/src/redis-server"
node = "/Users/roshan/Library/Application Support/RepoPilot/toolchains/p6/node-v24.18.0-darwin-arm64/bin"
api = pathlib.Path(__file__).resolve().parents[1]
web = api.parent / "web"
py = str(api / ".venv/bin/python")


def port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


mode = os.environ.get("RP_MODE", "")
assert mode in ("synthetic", "httpx"), "RP_MODE must be synthetic or httpx"
pgport, rport, apiport, webport = [port() for _ in range(4)]
assert len({pgport, rport, apiport, webport}) == 4
pw = root / "password"
pw.write_text(password)
pw.chmod(0o600)
rc = root / "redis.conf"
rc.write_text(
    f'bind 127.0.0.1\nport {rport}\nprotected-mode yes\nrequirepass {password}\nsave ""\nappendonly no\nmaxmemory 64mb\n'
)
rc.chmod(0o600)
children = []
started = False
try:
    subprocess.run(
        [
            pg + "initdb",
            "-D",
            str(data),
            "-U",
            "p17_admin",
            "--auth-local=trust",
            "--auth-host=scram-sha-256",
            "--pwfile=" + str(pw),
            "--no-instructions",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    subprocess.run(
        [
            pg + "pg_ctl",
            "-D",
            str(data),
            "-l",
            str(root / "pg.log"),
            "-o",
            f"-c listen_addresses=127.0.0.1 -c unix_socket_directories='{sock}' -c port={pgport}",
            "-w",
            "start",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    started = True
    pgenv = {
        "PATH": os.defpath,
        "PGHOST": str(sock),
        "PGPORT": str(pgport),
        "PGUSER": "p17_admin",
        "PGDATABASE": "postgres",
    }
    identity = subprocess.check_output(
        [
            pg + "psql",
            "-At",
            "-c",
            "select current_user,current_database(),current_setting('data_directory')",
        ],
        env=pgenv,
        text=True,
    ).strip()
    assert identity == f"p17_admin|postgres|{data}"
    subprocess.run([pg + "createdb", dbname], env=pgenv, check=True)
    subprocess.run(
        [pg + "psql", "-d", dbname, "-c", f"COMMENT ON DATABASE {dbname} IS 'p17:{marker}'"],
        env=pgenv,
        check=True,
        stdout=subprocess.DEVNULL,
    )

    def launch(cmd, name, cwd, env):
        out = open(root / (name + ".log"), "wb")
        p = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        out.close()
        children.append((name, p))
        return p

    broker = launch([redisbin, str(rc)], "redis", root, {"PATH": os.defpath})
    import redis

    client = redis.Redis(
        host="127.0.0.1", port=rport, password=password, socket_connect_timeout=1, socket_timeout=1
    )
    for _ in range(60):
        try:
            if client.ping():
                break
        except Exception:
            time.sleep(0.1)
    else:
        raise RuntimeError("redis startup")
    client.set("p17:disposable-marker", marker)
    client.close()
    dburl = f"postgresql+psycopg://p17_admin:{password}@127.0.0.1:{pgport}/{dbname}"
    redisurl = f"redis://:{password}@127.0.0.1:{rport}/0"
    origin = f"http://127.0.0.1:{webport}"
    env = {
        "PATH": os.defpath,
        "HOME": str(root),
        "PYTHONPATH": str(api),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
        "APP_ENV": "test",
        "DATABASE_URL": dburl,
        "REDIS_URL": redisurl,
        "PR_BROKER_TEST": "1",
        "RP_MODE": mode,
        "PR_FORK_TEST": os.environ.get("PR_FORK_TEST", "0"),
        "RP_REVOCATION_MARKER": str(root / "revoked") if os.environ.get("RP_REVOCATION_TEST") == "1" else "",
        "RP_PR_FIXTURE_DIR": os.environ.get("RP_PR_FIXTURE_DIR", ""),
        "P17_MARKER": marker,
        "P17_QUEUE": queue,
        "GITHUB_WEBHOOK_SECRET": "x" * 40,
        "GITHUB_OAUTH_ENABLED": "true",
        "GITHUB_APP_ID": "123",
        "GITHUB_CLIENT_ID": "fixture",
        "GITHUB_CLIENT_SECRET": "fixture",
        "GITHUB_TOKEN_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "GITHUB_CALLBACK_URL": origin + "/api/auth/callback",
        "WEB_ORIGIN": origin,
        "PR_REVIEWS_ENABLED": "true",
        "PATCH_LOCAL_MODEL_ENABLED": "false",
        "PATCH_PROPOSALS_ENABLED": "false",
        "EMBEDDING_PROVIDER": "disabled",
    }
    if os.environ.get("PR_TS_TEST") == "1":
        assert mode == "synthetic", "TypeScript fixture is synthetic only"
        env.update(PR_TS_TEST="1", PR_TYPESCRIPT_REVIEW_ENABLED="true",
            PR_TYPESCRIPT_NODE_PATH="/Users/roshan/Library/Application Support/RepoPilot/toolchains/p6/node-v24.18.0-darwin-arm64/bin/node",
            PR_TYPESCRIPT_NODE_SHA256="ee6fb0e015284d83a91e8ec5213f43a157f8a392b58555301682892ba928c04a",
            PR_TYPESCRIPT_COMPILER_PATH="/Volumes/;;;;;;;;;;;;;/Project/RepoPilot/apps/web/node_modules/typescript/lib/typescript.js",
            PR_TYPESCRIPT_COMPILER_SHA256="3ae902c92cc44dace175c0e69e13a4b0899f6983c6121d76b9ab8dd5795e7675")
    m = subprocess.run(
        [py, "-m", "alembic", "upgrade", "head"],
        cwd=api,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    assert m.returncode == 0, "migration failed"
    m = subprocess.run(
        [py, "-m", "alembic", "check"],
        cwd=api,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    assert m.returncode == 0, "drift check failed"
    print("migration head and drift passed", flush=True)
    worker = launch(
        [
            py,
            "-m",
            "celery",
            "-A",
            "evaluation.pr_review_fullstack_support:celery",
            "worker",
            "--pool=solo",
            "--concurrency=1",
            "-Q",
            queue,
            "--hostname=rpfull@localhost",
            "--loglevel=INFO",
            "--without-gossip",
            "--without-mingle",
        ],
        "worker",
        api,
        env,
    )
    dispatch = launch([py, "-m", "evaluation.pr_review_fullstack_support"], "dispatcher", api, env)
    server = launch(
        [
            py,
            "-m",
            "uvicorn",
            "evaluation.pr_review_fullstack_support:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(apiport),
            "--no-access-log",
        ],
        "api",
        api,
        env,
    )

    def until(fn, sec=45):
        end = time.monotonic() + sec
        while time.monotonic() < end:
            try:
                if fn():
                    return
            except (httpx.HTTPError, OSError):
                pass
            time.sleep(0.2)
        raise RuntimeError("service startup timed out")

    until(lambda: httpx.get(f"http://127.0.0.1:{apiport}/health", timeout=1).status_code == 200)
    until(
        lambda: (root / "worker.log").exists() and b"ready." in (root / "worker.log").read_bytes()
    )
    session = httpx.Client(
        base_url=f"http://127.0.0.1:{apiport}", follow_redirects=False, timeout=10
    )
    start = session.get("/v1/auth/github/start")
    assert start.status_code == 302
    state = urllib.parse.parse_qs(urllib.parse.urlparse(start.headers["location"]).query)["state"][
        0
    ]
    callback = session.get(
        "/v1/auth/github/callback", params={"state": state, "code": "fixture-code"}
    )
    assert callback.status_code == 303
    headers = {"Origin": origin, "X-CSRF-Token": session.cookies.get("rp_csrf")}
    assert session.post("/v1/installations/901/enroll", headers=headers).status_code == 200
    assert (
        session.post(
            "/v1/installations/901/repositories/"
            + ("179492861" if mode == "httpx" else "902")
            + "/select",
            headers=headers,
        ).status_code
        == 200
    )
    cookies = {
        "rp_session": session.cookies.get("rp_session"),
        "rp_csrf": session.cookies.get("rp_csrf"),
    }
    assert all(cookies.values())
    cfile = root / "cookies.json"
    cfile.write_text(json.dumps(cookies))
    cfile.chmod(0o600)
    session.close()
    webcopy = root / "web"
    shutil.copytree(
        web,
        webcopy,
        ignore=shutil.ignore_patterns("node_modules", ".next", "*.tsbuildinfo", ".env*"),
    )
    os.symlink(web / "node_modules", webcopy / "node_modules")
    nenv = {
        "PATH": node + ":" + os.defpath,
        "HOME": str(root),
        "API_INTERNAL_URL": f"http://127.0.0.1:{apiport}",
        "APP_ENV": "test",
        "NEXT_TELEMETRY_DISABLED": "1",
    }
    nextp = launch(
        [
            node + "/node",
            str(web / "node_modules/next/dist/bin/next"),
            "dev",
            "--webpack",
            "-H",
            "127.0.0.1",
            "-p",
            str(webport),
        ],
        "web",
        webcopy,
        nenv,
    )
    until(lambda: httpx.get(origin, timeout=2).status_code == 200, 90)
    print("disposable API web dispatcher and worker ready", flush=True)
    benv = {
        "PATH": os.defpath,
        "HOME": str(root),
        "RP_WEB_PORT": str(webport),
        "RP_COOKIES": str(cfile),
        "RP_MODE": mode,
        "PR_FORK_TEST": os.environ.get("PR_FORK_TEST", "0"),
        "PR_TS_TEST": os.environ.get("PR_TS_TEST", "0"),
        "RP_REVOCATION_MARKER": str(root / "revoked") if os.environ.get("RP_REVOCATION_TEST") == "1" else "",
        "RP_WIDTH": os.environ.get("RP_WIDTH", "1440"),
        "RP_HEIGHT": os.environ.get("RP_HEIGHT", "900"),
    }
    proc = subprocess.run(
        ["/usr/bin/swift", str(api / "evaluation/pr_review_fullstack_browser.swift")],
        cwd=root,
        env=benv,
        timeout=150,
    )
    print("webkit_exit", proc.returncode, flush=True)
    diagnostics = subprocess.check_output(
        [
            pg + "psql",
            "-d",
            dbname,
            "-At",
            "-c",
            "select status,coalesce(error_code,''),coalesce(coverage,''),coalesce(json_array_length(files),0) from pr_reviews order by created_at",
        ],
        env=pgenv,
        text=True,
    ).strip()
    print("review_db_status", diagnostics, flush=True)
    if proc.returncode:
        raise SystemExit(proc.returncode)
    query = "select r.id,coalesce(f.id,''),o.status,o.attempts,extract(epoch from (r.updated_at-r.created_at)),coalesce(fb.state,'') from pr_reviews r join pr_review_outbox o on o.review_id=r.id left join pr_review_findings f on f.review_id=r.id left join pr_finding_feedback fb on fb.finding_id=f.id order by r.created_at limit 1"
    fields = (
        subprocess.check_output(
            [pg + "psql", "-d", dbname, "-At", "-c", query], env=pgenv, text=True
        )
        .strip()
        .split("|")
    )
    assert len(fields) == 6 and fields[2] == "processed" and int(fields[3]) >= 1
    assert (mode == "httpx" and not fields[5]) or (mode == "synthetic" and fields[5] == "useful")
    print("database_lifecycle_seconds", fields[4], "feedback", fields[5] or "none", flush=True)
    receipt = ("Task process_pr_review[" + fields[0] + "] received").encode()
    assert receipt in (root / "worker.log").read_bytes(), "worker receipt missing"
    print(
        "review_id",
        fields[0],
        "outbox",
        fields[2],
        "dispatch_attempts",
        fields[3],
        "worker_receipt",
        True,
        flush=True,
    )
    other = httpx.Client(base_url=f"http://127.0.0.1:{apiport}", follow_redirects=False, timeout=10)
    start = other.get("/v1/auth/github/start")
    otherstate = urllib.parse.parse_qs(urllib.parse.urlparse(start.headers["location"]).query)[
        "state"
    ][0]
    assert (
        other.get(
            "/v1/auth/github/callback", params={"state": otherstate, "code": "fixture-code2"}
        ).status_code
        == 303
    )
    otherroot = (
        "/v1/repositories/"
        + ("179492861" if mode == "httpx" else "902")
        + "/pr-reviews/"
        + fields[0]
    )
    read = other.get(otherroot)
    assert read.status_code in (403, 404)
    if fields[1]:
        write = other.post(
            otherroot + "/findings/" + fields[1] + "/feedback",
            json={"state": "useful"},
            headers={"Origin": origin, "X-CSRF-Token": other.cookies.get("rp_csrf")},
        )
        assert write.status_code in (403, 404)
    other.close()
    print("cross_tenant_denied", read.status_code, flush=True)
finally:
    for name, p in reversed(children):
        if p.poll() is None:
            os.killpg(p.pid, signal.SIGTERM)
            try:
                p.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
                p.wait()
    if started:
        subprocess.run(
            [pg + "pg_ctl", "-D", str(data), "-m", "fast", "-w", "stop"],
            stdout=subprocess.DEVNULL,
            check=True,
        )
    shutil.rmtree(root)
    for value in (pgport, rport, apiport, webport):
        with socket.socket() as probe:
            probe.settimeout(0.25)
            assert probe.connect_ex(("127.0.0.1", value)) != 0, "temporary listener still active"
    print("owned services and test credentials removed; test ports closed", flush=True)
