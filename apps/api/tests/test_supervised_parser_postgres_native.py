"""Disposable PostgreSQL checks using a test-only broker and real parser children."""

from hashlib import sha1, sha256
import json
import os
import socket

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.domain.models import CodeChunk, CodeSnapshot, IndexJob, IndexedFile
from app.modules.ingestion import supervised_parser as supervisor
from app.modules.ingestion.citations import github_citation
from app.modules.investigation.retrieval import fingerprint_chunk
from app.workers.tasks import process_index
from test_auth_enrollment import csrf, github_auth as github_auth  # noqa: F401
from test_code_workflow import FakeSource, connect


@pytest.fixture(scope="module")
def parser_channel():
    raw_fd = os.environ.get("REPOPILOT_PARSER_BROKER_FD", "")
    if not raw_fd.isdecimal():
        pytest.skip("reviewed disposable parser broker is required")
    channel = socket.socket(fileno=int(raw_fd))
    assert channel.family == socket.AF_UNIX and channel.type & socket.SOCK_STREAM
    channel.settimeout(30)
    with channel, channel.makefile("rb") as reader:
        yield channel, reader


@pytest.fixture
def real_parser_broker(parser_channel, monkeypatch):
    channel, reader = parser_channel

    def execute(request, source, *, timeout):
        assert timeout == 10 and request["source_sha256"] == sha256(source).hexdigest()
        wire = (json.dumps({"action": "parse", "request": request},
                           ensure_ascii=True, separators=(",", ":")) + "\n").encode()
        assert len(wire) <= 150_000
        channel.sendall(wire)
        line = reader.readline(supervisor.MAX_RESPONSE + 4097)
        assert line.endswith(b"\n") and len(line) <= supervisor.MAX_RESPONSE + 4096
        data = json.loads(line, object_pairs_hook=supervisor._no_duplicates)
        assert set(data) == {"status", "response", "exit_code", "peak_rss_kib"}
        status = supervisor.Status(data["status"])
        if data["response"] is not None:
            encoded = (json.dumps(data["response"], ensure_ascii=True, separators=(",", ":")) + "\n").encode()
            validated = supervisor._validate(encoded, request, source, data["response"]["worker_pid"])
            assert validated.status == status and validated.response == data["response"]
        return supervisor.Outcome(status, data["response"], data["exit_code"], data["peak_rss_kib"])

    monkeypatch.setattr(supervisor, "_execute", execute)
    return execute


class SyntheticMultilingualSource(FakeSource):
    files = {
        "src/main.go": b'package demo\nimport "fmt"\nfunc GoValue() { fmt.Println("synthetic") }\n',
        "src/total.py": b"import os\ndef python_total():\n    return 1\n",
        "src/view.tsx": b"import React from 'react';\nfunction View() { return <p/>; }\n",
    }

    def tree(self, token, full_name, sha):
        assert (token, full_name, sha) == ("sensitive-github-token", "alice/public", "a" * 40)
        return {"truncated": False, "tree": [
            {"path": path, "type": "blob", "mode": "100644", "size": len(raw),
             "sha": sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()}
            for path, raw in sorted(self.files.items())
        ]}

    def blob(self, token, full_name, blob_sha, expected_size):
        assert (token, full_name) == ("sensitive-github-token", "alice/public")
        for raw in self.files.values():
            if sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == blob_sha:
                assert len(raw) == expected_size
                return raw
        raise AssertionError("unknown synthetic blob")


def test_postgres_supervised_real_children_publish_and_cite(client, factory, github_auth, real_parser_broker,
                                                            monkeypatch):
    assert factory.kw["bind"].dialect.name == "postgresql"
    connect(client)
    monkeypatch.setattr(get_settings(), "index_multilingual_enabled", True)
    monkeypatch.setattr(get_settings(), "index_multilingual_supervised_parser_enabled", True)
    job_id = client.post("/v1/repositories/902/index", headers=csrf(client)).json()["job_id"]
    with factory() as db:
        assert db.get(IndexJob, job_id).indexing_mode == "multi_supervised"
    process_index(job_id, factory, github_auth, SyntheticMultilingualSource())
    process_index(job_id, factory, github_auth, SyntheticMultilingualSource())
    with factory() as db:
        job = db.get(IndexJob, job_id)
        snapshot = db.scalar(select(CodeSnapshot).where(CodeSnapshot.published.is_(True)))
        files = db.scalars(select(IndexedFile).where(IndexedFile.snapshot_id == snapshot.id)).all()
        assert job.status == "completed" and snapshot.commit_sha == "a" * 40
        assert snapshot.indexing_mode == "multilingual" and len(files) == 3
        assert len(db.scalars(select(CodeSnapshot)).all()) == 1
        for item in files:
            raw = SyntheticMultilingualSource.files[item.path]
            chunks = db.scalars(select(CodeChunk).where(CodeChunk.file_id == item.id).order_by(CodeChunk.start_line)).all()
            assert item.parser_status == "parsed" and item.content_hash == sha256(raw).hexdigest()
            assert item.repository_id == snapshot.repository_id == job.repository_id
            assert item.tenant_id == snapshot.tenant_id == job.tenant_id
            assert "".join(chunk.source_text for chunk in chunks).encode() == raw
            assert item.import_ranges and any(chunk.symbol for chunk in chunks)
            for chunk in chunks:
                assert chunk.repository_id == item.repository_id and chunk.tenant_id == item.tenant_id
                assert len(fingerprint_chunk(chunk, item)) == 64
                assert github_citation("alice/public", snapshot.commit_sha, item.path,
                                       chunk.start_line, chunk.end_line).endswith(
                                           f"/{item.path}#L{chunk.start_line}-L{chunk.end_line}")


def test_postgres_supervised_real_child_syntax_fallback_is_labeled(client, factory, github_auth,
                                                                  real_parser_broker, monkeypatch):
    assert factory.kw["bind"].dialect.name == "postgresql"
    connect(client)
    monkeypatch.setattr(get_settings(), "index_multilingual_enabled", True)
    monkeypatch.setattr(get_settings(), "index_multilingual_supervised_parser_enabled", True)

    class BrokenSource(SyntheticMultilingualSource):
        files = {"src/broken.ts": b"function broken( {\n"}

    job_id = client.post("/v1/repositories/902/index", headers=csrf(client)).json()["job_id"]
    process_index(job_id, factory, github_auth, BrokenSource())
    with factory() as db:
        job = db.get(IndexJob, job_id)
        item = db.scalar(select(IndexedFile))
        chunks = db.scalars(select(CodeChunk).where(CodeChunk.file_id == item.id)).all()
        assert job.status == "completed" and item.parser_status == "syntax_error"
        assert not any(chunk.symbol for chunk in chunks)
    assert client.get("/v1/repositories/902/index-status").json()["parser_fallback_count"] == 1
