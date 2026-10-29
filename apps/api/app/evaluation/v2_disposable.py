"""Run v2 keyword evaluation in a freshly migrated, dedicated local test database."""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

COMMIT = "956a4f92983b222ce179891bbde39cb49a2022b2"
DATASET_HASH = "813414c2eece2fa42f57d75d9cc12b6dd77eb5d75d63999ad8cae14b65bdd2ba"


def main():
    url = make_url(os.environ["DATABASE_URL"])
    if (url.get_backend_name() != "postgresql" or url.host not in {"127.0.0.1", "localhost"}
            or not url.database or not url.database.startswith("repopilot_c3_disposable_")):
        raise SystemExit("Refusing non-dedicated local PostgreSQL target")
    os.environ.update(APP_ENV="test", DEMO_AUTH_ENABLED="false", EMBEDDING_PROVIDER="disabled",
                      EMBEDDING_ALLOW_PAID="false", GITHUB_OAUTH_ENABLED="true", GITHUB_APP_ID="123",
                      GITHUB_CLIENT_ID="fixture", GITHUB_CLIENT_SECRET="fixture",
                      GITHUB_CALLBACK_URL="http://localhost:3000/api/auth/callback",
                      WEB_ORIGIN="http://localhost:3000", GITHUB_WEBHOOK_SECRET="fixture-" + "x" * 40)
    from cryptography.fernet import Fernet
    os.environ["GITHUB_TOKEN_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
    from fastapi.testclient import TestClient
    from app.domain.models import CodeChunk, CodeSnapshot, IndexedFile, IndexJob, Installation
    from app.evaluation.git_source import GitSource
    from app.evaluation.retrieval import citation_valid, evaluate, markdown, match_label
    from app.infra.database import get_db
    from app.main import app
    from app.modules.github.client import get_github_client
    from app.workers.tasks import process_index

    repo = Path(os.environ["REPOPILOT_GIT_ROOT"]).resolve()
    dataset_path = Path("evaluation/repopilot-v2-956a4f9.json")
    raw = dataset_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != DATASET_HASH:
        raise SystemExit("Dataset hash mismatch")
    dataset = json.loads(raw)
    if dataset["commit_sha"] != COMMIT or len(dataset["queries"]) != 16:
        raise SystemExit("Unexpected benchmark dataset")
    source = GitSource(repo, COMMIT, dataset["repository"])
    engine = create_engine(url)
    with engine.connect() as conn:
        database, address, port = conn.execute(text("select current_database(), inet_server_addr()::text, inet_server_port()" )).one()
        revision = conn.execute(text("select version_num from alembic_version")).scalar_one()
        if database != url.database or revision != "0006":
            raise SystemExit("Wrong database or migration revision")
        if conn.execute(text("select count(*) from code_snapshots")).scalar_one() != 0:
            raise SystemExit("Database already contains snapshots")
        print(f"Database confirmed: {database}; server={address}:{port}; migration={revision}")
    factory = sessionmaker(engine, expire_on_commit=False)
    sys.path.insert(0, str(Path("tests").resolve()))
    from test_auth_enrollment import FakeGitHub, csrf, sign_in

    class FixtureGitHub(FakeGitHub):
        def repositories(self, token, installation_id):
            assert installation_id == 901
            return ([{"id": 902, "full_name": dataset["repository"], "private": False}]
                    if self.include_repository else [])

    github = FixtureGitHub()
    def get_session():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = get_session
    app.dependency_overrides[get_github_client] = lambda: github
    with TestClient(app) as client:
        assert client.get("/v1/auth/me").status_code == 401
        sign_in(client)
        assert client.post("/v1/installations/901/enroll", headers=csrf(client)).status_code == 200
        assert client.post("/v1/installations/901/repositories/902/select", headers=csrf(client)).status_code == 200
        created = client.post("/v1/repositories/902/index", headers=csrf(client))
        assert created.status_code == 202
        job_id = created.json()["job_id"]
        process_index(job_id, factory, github, source)
        with factory() as db:
            job = db.get(IndexJob, job_id)
            if job.status not in {"completed", "partial"}:
                raise RuntimeError(f"Index job did not publish: {job.status}, {job.error_code}")
            snapshot = db.scalar(select(CodeSnapshot).where(CodeSnapshot.published.is_(True)))
            assert snapshot.commit_sha == COMMIT and snapshot.repository_id == 902
            snapshot_id = snapshot.id
            rows = db.execute(select(CodeChunk, IndexedFile).join(IndexedFile, CodeChunk.file_id == IndexedFile.id)
                              .where(IndexedFile.snapshot_id == snapshot_id)).all()
            assert len(rows) == snapshot.chunk_count
            expected = {entry["path"]: entry for entry in source.entries}
            published = []
            for chunk, file in rows:
                entry = expected[file.path]
                contents = source.blob(None, dataset["repository"], entry["sha"], entry["size"])
                assert hashlib.sha256(contents).hexdigest() == file.content_hash
                lines = contents.decode("utf-8").splitlines(keepends=True)
                assert 1 <= chunk.start_line <= chunk.end_line <= len(lines)
                assert chunk.source_text == "".join(lines[chunk.start_line - 1:chunk.end_line])
                published.append({"path": file.path, "symbol": chunk.symbol,
                                  "start_line": chunk.start_line, "end_line": chunk.end_line})
            assert all(any(match_label(item, label) and item for item in published)
                       for q in dataset["queries"] for label in q["relevance"])
            counts = {"files": snapshot.file_count, "chunks": snapshot.chunk_count,
                      "skipped_files": snapshot.skipped_count}
        responses = {}
        for question in dataset["queries"]:
            start = time.perf_counter()
            response = client.post("/v1/repositories/902/search", headers=csrf(client),
                                   json={"query": question["question"], "limit": 10, "mode": "keyword"})
            elapsed = (time.perf_counter() - start) * 1000
            response.raise_for_status()
            data = response.json()
            for item in data["items"]:
                if not citation_valid(item, dataset["repository"], COMMIT):
                    raise ValueError("Invalid citation")
                if not any(item["path"] == chunk["path"] and item["symbol"] == chunk["symbol"]
                           and item["start_line"] == chunk["start_line"] and item["end_line"] == chunk["end_line"]
                           for chunk in published):
                    raise ValueError("Citation does not match a Git-verified published chunk")
            responses[("keyword", question["id"])] = (data, elapsed)
        with factory.begin() as db:
            db.get(CodeSnapshot, snapshot_id).published = False
        assert client.post("/v1/repositories/902/search", headers=csrf(client), json={"query": "test"}).status_code == 409
        with factory.begin() as db:
            db.get(CodeSnapshot, snapshot_id).published = True
        github.include_repository = False
        assert client.post("/v1/repositories/902/search", headers=csrf(client), json={"query": "test"}).status_code == 404
        github.include_repository = True
        with factory.begin() as db:
            db.get(Installation, 901).active = False
        assert client.post("/v1/repositories/902/search", headers=csrf(client), json={"query": "test"}).status_code == 404
        with factory.begin() as db:
            db.get(Installation, 901).active = True
        assert client.post("/v1/auth/logout", headers=csrf(client)).status_code == 200
        github.user_id = github.account_id = 78
        sign_in(client)
        assert client.post("/v1/repositories/902/search", headers=csrf(client), json={"query": "test"}).status_code == 404
    app.dependency_overrides.clear()
    metadata = {"provider": "disabled", "model": None, "dimensions": None, "limit": 10,
                "dataset_sha256": DATASET_HASH, "database": database, "snapshot_id": snapshot_id,
                "snapshot": counts, "migration": revision,
                "citations": "verified against local Git blobs; GitHub availability unverified",
                "negative_candidates": "two unscored", "semantic": "not measured",
                "authorization_checks": "unauthenticated 401; unpublished 409; revoked access and other tenant 404"}
    report = evaluate(dataset, responses, metadata, modes=("keyword",))
    prefix = Path(os.environ.get("REPOPILOT_V2_OUTPUT", "evaluation/v2-local"))
    prefix.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
    prefix.with_suffix(".md").write_text(markdown(report) + "\n\nLocal Git blob citation validation passed; remote commit availability is unverified. "
                                      "Two negative candidates remain unscored.\n")
    print(f"Published disposable snapshot {snapshot_id}: {counts}; reports: {prefix}.json/.md")


if __name__ == "__main__":
    main()
