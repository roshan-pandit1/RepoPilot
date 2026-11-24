"""Synthetic-only tests of the actual feature-flagged supervisor entry point."""

from hashlib import sha1, sha256
from importlib import metadata
from pathlib import PurePosixPath
import socket
import sys
from types import SimpleNamespace

import pytest

from app.modules.ingestion import supervised_parser as supervisor
from app.modules.ingestion.citations import github_citation
from app.modules.ingestion.code_collect import collect_source
from app.modules.ingestion.code_snapshot import Candidate, SnapshotPlan
from app.modules.ingestion.language_analysis import LANGUAGES
from app.modules.investigation.retrieval import fingerprint_chunk
from evaluation.fixtures.tree_sitter_0252_matrix_fixtures import VARIANTS, small

VERSIONS = {
    "tree-sitter": "0.25.2", "tree-sitter-javascript": "0.25.0",
    "tree-sitter-typescript": "0.23.2", "tree-sitter-java": "0.23.5",
    "tree-sitter-go": "0.25.0", "tree-sitter-rust": "0.24.2", "tree-sitter-c": "0.24.2",
    "tree-sitter-cpp": "0.23.4", "tree-sitter-c-sharp": "0.23.5",
}


@pytest.fixture(scope="session", autouse=True)
def verified_environment():
    assert supervisor.isolation_available(), "the actual run() gate must be available"
    assert {name: metadata.version(name) for name in VERSIONS} == VERSIONS


@pytest.fixture(autouse=True)
def deny_parent_python_network(monkeypatch):
    """The trusted pytest parent makes no IP connections; children use OS sandboxing."""
    original = socket.socket

    def guarded_socket(family=socket.AF_INET, *args, **kwargs):
        if family in (socket.AF_INET, socket.AF_INET6):
            raise AssertionError("native test parent must not use IP networking")
        return original(family, *args, **kwargs)

    monkeypatch.setattr(socket, "socket", guarded_socket)


class SyntheticBlob:
    def __init__(self, raw):
        self.raw = raw

    def blob(self, token, full_name, blob_sha, expected_size):
        assert (token, full_name, expected_size) == ("fixture", "fixture/repo", len(self.raw))
        assert blob_sha == sha1(b"blob " + str(len(self.raw)).encode() + b"\0" + self.raw).hexdigest()
        return self.raw


@pytest.mark.parametrize("extension", sorted(VARIANTS))
def test_actual_supervisor_and_collection_for_every_extension(extension, monkeypatch):
    source, _, expected_symbols = small(extension)
    raw = source.encode("utf-8")
    path = "synthetic/example" + extension
    language = VARIANTS[extension]
    expected_sha = sha256(raw).hexdigest()
    result = supervisor.run(raw, path=path, language=language, request_id="a" * 32,
                            expected_sha256=expected_sha)
    assert result.status == supervisor.Status.PARSED, (extension, result.status, result.exit_code)
    response = result.response
    registered = LANGUAGES[PurePosixPath(path).suffix]
    assert response["parser_status"] == "parsed" and response["fallback_reason"] is None
    assert response["source_sha256"] == expected_sha
    assert (response["grammar"], response["grammar_entrypoint"]) == (registered.module, registered.entrypoint)
    assert set(expected_symbols) <= {symbol["name"] for symbol in response["symbols"]}
    assert response["imports"]
    assert b"".join(raw[item["start_byte"]:item["end_byte"]] for item in response["chunks"]) == raw

    monkeypatch.setattr("app.modules.ingestion.code_collect.analyze_source",
                        lambda *_a, **_k: pytest.fail("in-process parser used"))
    blob = sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    plan = SnapshotPlan("b" * 40, (Candidate(path, blob, len(raw)),), multilingual=True)
    item = collect_source(SyntheticBlob(raw), "fixture", "fixture/repo", plan, supervised=True).files[0]
    assert item.content_hash == expected_sha and item.parser_version == response["parser_version"]
    assert item.parser_status == "parsed" and item.import_ranges == tuple(map(tuple, response["imports"]))
    assert [(c.start_line, c.end_line, c.symbol, c.symbol_kind, sha256(c.text.encode()).hexdigest())
            for c in item.chunks] == [(c["start_line"], c["end_line"], c["symbol"], c["symbol_kind"],
                                       c["content_sha256"]) for c in response["chunks"]]
    for n, chunk in enumerate(item.chunks):
        file = SimpleNamespace(snapshot_id="fixture-snapshot", path=path, content_hash=expected_sha)
        row = SimpleNamespace(id=f"fixture-chunk-{n}", file_id="fixture-file", symbol=chunk.symbol,
                              start_line=chunk.start_line, end_line=chunk.end_line, source_text=chunk.text)
        transport = response["chunks"][n]
        from_child = SimpleNamespace(id=row.id, file_id=row.file_id, symbol=transport["symbol"],
                                     start_line=transport["start_line"], end_line=transport["end_line"],
                                     source_text=raw[transport["start_byte"]:transport["end_byte"]].decode())
        assert fingerprint_chunk(row, file) == fingerprint_chunk(from_child, file)
        citation = github_citation("fixture/repo", plan.commit_sha, path, chunk.start_line, chunk.end_line)
        assert citation.endswith(f"/{path}#L{chunk.start_line}-L{chunk.end_line}")


@pytest.mark.parametrize("extension", [".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go",
                                        ".rs", ".c", ".cpp", ".cs"])
def test_actual_supervisor_explicit_syntax_fallback(extension):
    _, broken, _ = small(extension)
    raw = broken.encode()
    result = supervisor.run(raw, path="synthetic/broken" + extension, language=VARIANTS[extension],
                            request_id="b" * 32, expected_sha256=sha256(raw).hexdigest())
    assert result.status == supervisor.Status.FALLBACK
    assert result.response["fallback_reason"] == "syntax_error"
    assert not result.response["symbols"] and not result.response["imports"]


def test_actual_go_run_gate_reports_locked_parser_and_grammar():
    source, _, expected = small(".go")
    raw = source.encode()
    result = supervisor.run(raw, path="synthetic/gate.go", language="go", request_id="c" * 32,
                            expected_sha256=sha256(raw).hexdigest())
    assert result.status == supervisor.Status.PARSED
    assert result.response["grammar"] == "tree_sitter_go"
    assert result.response["parser_version"] == "languages-v1:ts-0.25.2:0.25.0"
    assert set(expected) <= {symbol["name"] for symbol in result.response["symbols"]}


def test_invalid_source_hash_fails_before_child(monkeypatch):
    monkeypatch.setattr(supervisor.subprocess, "Popen", lambda *_a, **_k: pytest.fail("child started"))
    result = supervisor.run(b"package p\n", path="synthetic/a.go", language="go", request_id="d" * 32,
                            expected_sha256="0" * 64)
    assert result.status == supervisor.Status.INVALID_REQUEST and result.response is None


def test_missing_sandbox_fails_closed_before_child(monkeypatch):
    monkeypatch.setattr(supervisor, "SANDBOX", "/nonexistent/repopilot-sandbox")
    monkeypatch.setattr(supervisor.subprocess, "Popen", lambda *_a, **_k: pytest.fail("child started"))
    raw = b"package p\n"
    result = supervisor.run(raw, path="synthetic/a.go", language="go", request_id="e" * 32,
                            expected_sha256=sha256(raw).hexdigest())
    assert result.status == supervisor.Status.ISOLATION_UNAVAILABLE and result.response is None


def test_unreviewed_interpreter_environment_fails_closed(monkeypatch):
    fake = SimpleNamespace(platform="darwin", prefix="/nonexistent/not-reviewed", base_prefix="/system")
    monkeypatch.setattr(supervisor, "sys", fake)
    monkeypatch.setattr(supervisor.subprocess, "Popen", lambda *_a, **_k: pytest.fail("child started"))
    raw = b"package p\n"
    result = supervisor.run(raw, path="synthetic/a.go", language="go", request_id="f" * 32,
                            expected_sha256=sha256(raw).hexdigest())
    assert result.status == supervisor.Status.ISOLATION_UNAVAILABLE and result.response is None


def test_missing_interpreter_fails_closed_through_actual_run(monkeypatch, tmp_path):
    missing = tmp_path / "missing-python"
    assert not missing.exists()
    fake = SimpleNamespace(platform=sys.platform, prefix=sys.prefix, base_prefix=sys.base_prefix,
                           executable=str(missing), byteorder=sys.byteorder,
                           version_info=sys.version_info)
    monkeypatch.setattr(supervisor, "sys", fake)
    raw = b"package p\n"
    result = supervisor.run(raw, path="synthetic/a.go", language="go", request_id="9" * 32,
                            expected_sha256=sha256(raw).hexdigest())
    assert result.status == supervisor.Status.ISOLATION_OR_LAUNCH_FAILED
    assert result.response is None
