"""Synthetic integration tests; the native worker transport is mocked here."""

import ast
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import sys
from uuid import UUID

import pytest
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.domain.models import CodeChunk, CodeSnapshot, IndexJob, IndexedFile
from app.modules.ingestion import supervised_parser as supervisor
from app.modules.ingestion.citations import github_citation
from app.modules.ingestion.code_collect import CollectionError, collect_source
from app.modules.ingestion.code_snapshot import Candidate, SnapshotPlan
from app.modules.ingestion.language_analysis import LANGUAGES
from app.modules.investigation.retrieval import fingerprint_chunk
from app.workers.tasks import process_index
from evaluation.fixtures.tree_sitter_0252_matrix_fixtures import VARIANTS, small
from test_auth_enrollment import csrf, github_auth as github_auth  # noqa: F401
from test_code_workflow import FakeSource, connect


class SyntheticBlob:
    def __init__(self, content):
        self.content = content
        self.calls = 0

    def blob(self, _token, _repository, _sha, _size):
        self.calls += 1
        return self.content


def plan_for(path, content, *, multilingual=True, commit="a" * 40, blob="b" * 40):
    return SnapshotPlan(commit, (Candidate(path, blob, len(content)),), multilingual=multilingual)


def response_for(request, source, *, fallback=None):
    """Build controlled protocol data, not a claim about language understanding."""
    language = LANGUAGES[PurePosixPath(request["path"]).suffix.lower()]
    version = ("languages-v1:python-" + ".".join(map(str, sys.version_info[:3]))
               if language.name == "python" else "languages-v1:ts-0.25.2:0.0-test")
    if fallback == "parser_unavailable":
        version = "unavailable"
    lines = source.decode().splitlines(keepends=True)
    chunks = [] if not lines else [{"start_line": 1, "end_line": len(lines), "start_byte": 0,
                                    "end_byte": len(source), "content_sha256": sha256(source).hexdigest(),
                                    "symbol": None, "symbol_kind": None}]
    return {"version": 1, "request_id": request["request_id"], "worker_pid": 123,
            "language": request["language"], "path": request["path"],
            "source_sha256": sha256(source).hexdigest(), "grammar": language.module,
            "grammar_entrypoint": language.entrypoint, "parser_version": version,
            "parser_status": "fallback" if fallback else "parsed", "fallback_reason": fallback,
            "chunk_strategy": "python-ast" if language.name == "python" else "multilingual",
            "symbols": [], "imports": [], "chunks": chunks}


@pytest.fixture
def controlled_transport(monkeypatch):
    """Use the real request/response validator with synthetic child responses."""
    monkeypatch.setattr(supervisor, "isolation_available", lambda: True)
    real_version = supervisor.metadata.version

    def version(name):
        if name == "tree-sitter":
            return "0.25.2"
        if name.startswith("tree-sitter-"):
            return "0.0-test"
        return real_version(name)

    monkeypatch.setattr(supervisor.metadata, "version", version)
    calls = []

    def execute(request, source, *, timeout):
        calls.append((request, source, timeout))
        response = response_for(request, source)
        wire = (json.dumps(response, ensure_ascii=True, separators=(",", ":")) + "\n").encode()
        return supervisor._validate(wire, request, source, 123)

    monkeypatch.setattr(supervisor, "_execute", execute)
    return calls


def test_flags_default_to_false_without_env_or_env_file(monkeypatch):
    monkeypatch.delenv("INDEX_MULTILINGUAL_ENABLED", raising=False)
    monkeypatch.delenv("INDEX_MULTILINGUAL_SUPERVISED_PARSER_ENABLED", raising=False)
    settings = Settings(_env_file=None, database_url="sqlite://", github_webhook_secret="x" * 40,
                        app_env="test", demo_auth_enabled=False)
    assert not settings.index_multilingual_enabled
    assert not settings.index_multilingual_supervised_parser_enabled


def test_supervisor_flag_uses_existing_environment_convention(monkeypatch):
    monkeypatch.setenv("INDEX_MULTILINGUAL_SUPERVISED_PARSER_ENABLED", "true")
    settings = Settings(_env_file=None, database_url="sqlite://", github_webhook_secret="x" * 40,
                        app_env="test", demo_auth_enabled=False)
    assert settings.index_multilingual_supervised_parser_enabled


def test_isolation_and_transport_remain_identical_to_reviewed_prototype():
    api = Path(__file__).resolve().parents[1]
    original = ast.parse((api / "evaluation/supervised_parser.py").read_text(encoding="utf-8"))
    integrated = ast.parse(Path(supervisor.__file__).read_text(encoding="utf-8"))
    def functions(tree):
        return {node.name: ast.dump(node) for node in tree.body if isinstance(node, ast.FunctionDef)}
    before, after = functions(original), functions(integrated)
    for name in ("_profile", "_rss_kib", "_kill", "_supervise"):
        assert before[name] == after[name]
    prototype_child = ast.parse((api / "evaluation/supervised_parser_child.py").read_text(encoding="utf-8"))
    integrated_child = ast.parse((api / "app/modules/ingestion/supervised_parser_child.py").read_text(encoding="utf-8"))
    assert ast.dump(ast.Module(body=prototype_child.body[1:], type_ignores=[])) == ast.dump(
        ast.Module(body=integrated_child.body[1:], type_ignores=[]))


def test_disabled_supervision_preserves_python_ast_and_starts_no_child(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("disabled supervisor must not run")

    monkeypatch.setattr(supervisor, "run", forbidden)
    monkeypatch.setattr(supervisor.subprocess, "Popen", forbidden)
    raw = b"def fixture():\n    return 1\n"
    collection = collect_source(SyntheticBlob(raw), "fixture", "demo/repo", plan_for("src/x.py", raw))
    assert collection.files[0].parser_status == "parsed"
    assert collection.files[0].chunks[0].symbol == "fixture"


def test_python_only_plan_does_not_use_supervisor_even_if_requested(monkeypatch):
    monkeypatch.setattr(supervisor, "run", lambda *_a, **_k: pytest.fail("unexpected supervised subprocess"))
    raw = b"def fixture():\n    return 1\n"
    file = collect_source(SyntheticBlob(raw), "fixture", "demo/repo",
                          plan_for("src/x.py", raw, multilingual=False), supervised=True).files[0]
    assert file.chunks[0].symbol == "fixture" and file.parser_status == "parsed"


def test_unsupervised_multilingual_path_keeps_existing_fallback(monkeypatch):
    def unavailable(_name):
        raise ImportError("synthetic unavailable grammar")

    monkeypatch.setattr("app.modules.ingestion.language_analysis.import_module", unavailable)
    monkeypatch.setattr(supervisor, "run", lambda *_a, **_k: pytest.fail("unexpected supervisor"))
    raw = b"package demo\nfunc fixture() {}\n"
    item = collect_source(SyntheticBlob(raw), "fixture", "demo/repo", plan_for("src/x.go", raw)).files[0]
    assert item.parser_status == "parser_unavailable"
    assert "".join(chunk.text for chunk in item.chunks).encode() == raw


@pytest.mark.parametrize("extension", sorted(VARIANTS))
def test_each_registered_extension_dispatches_with_source_identity(extension, controlled_transport, monkeypatch):
    monkeypatch.setattr("app.modules.ingestion.code_collect.analyze_source",
                        lambda *_a, **_k: pytest.fail("unsafe in-process parser called"))
    text, _, _ = small(extension)
    raw = text.encode()
    path = "synthetic/example" + extension
    result = collect_source(SyntheticBlob(raw), "fixture", "demo/repo", plan_for(path, raw), supervised=True)
    item = result.files[0]
    request, source, timeout = controlled_transport[-1]
    assert request["language"] == VARIANTS[extension] and request["path"] == path
    assert request["source_sha256"] == item.content_hash == sha256(raw).hexdigest()
    assert source == raw and timeout == 10
    assert item.language == VARIANTS[extension] and item.parser_status == "parsed"
    assert item.parser_version == response_for(request, raw)["parser_version"]
    assert "".join(chunk.text for chunk in item.chunks).encode() == raw
    chunk = item.chunks[0]
    citation = github_citation("demo/repo", "a" * 40, path, chunk.start_line, chunk.end_line)
    assert citation.endswith(f"/{path}#L{chunk.start_line}-L{chunk.end_line}")


@pytest.mark.parametrize("reason", ["syntax_error", "parser_unavailable"])
def test_supported_fallback_is_not_labeled_parsed(reason, controlled_transport, monkeypatch):
    def execute(request, source, *, timeout):
        response = response_for(request, source, fallback=reason)
        return supervisor._validate((json.dumps(response) + "\n").encode(), request, source, 123)

    monkeypatch.setattr(supervisor, "_execute", execute)
    raw = b"function broken( {\n"
    item = collect_source(SyntheticBlob(raw), "fixture", "demo/repo", plan_for("src/x.js", raw),
                          supervised=True).files[0]
    assert item.parser_status == reason
    assert not item.import_ranges and not any(chunk.symbol for chunk in item.chunks)


def test_symbols_and_imports_survive_validated_transport(controlled_transport, monkeypatch):
    def execute(request, source, *, timeout):
        response = response_for(request, source)
        response["imports"] = [[1, 1]]
        response["symbols"] = [{"name": "fixture", "kind": "function", "parent": None,
                                "start_line": 2, "end_line": 2}]
        split = source.index(b"\n") + 1
        response["chunks"] = [
            {"start_line": 1, "end_line": 1, "start_byte": 0, "end_byte": split,
             "content_sha256": sha256(source[:split]).hexdigest(), "symbol": None, "symbol_kind": None},
            {"start_line": 2, "end_line": 2, "start_byte": split, "end_byte": len(source),
             "content_sha256": sha256(source[split:]).hexdigest(), "symbol": "fixture", "symbol_kind": None},
        ]
        return supervisor._validate((json.dumps(response) + "\n").encode(), request, source, 123)

    monkeypatch.setattr(supervisor, "_execute", execute)
    raw = b"import os\ndef fixture(): pass\n"
    item = collect_source(SyntheticBlob(raw), "fixture", "demo/repo", plan_for("src/x.py", raw),
                          supervised=True).files[0]
    assert item.import_ranges == ((1, 1),) and item.chunks[1].symbol == "fixture"


@pytest.mark.parametrize("status", [supervisor.Status.INVALID_REQUEST, supervisor.Status.INITIALIZATION_FAILED,
    supervisor.Status.ISOLATION_UNAVAILABLE, supervisor.Status.ISOLATION_OR_LAUNCH_FAILED,
    supervisor.Status.PARSER_ERROR, supervisor.Status.WORKER_EXITED, supervisor.Status.TIMEOUT,
    supervisor.Status.RESOURCE_LIMIT, supervisor.Status.MONITOR_FAILED, supervisor.Status.OUTPUT_TOO_LARGE,
    supervisor.Status.OUTPUT_REJECTED, supervisor.Status.CLEANUP_FAILED])
def test_failure_never_returns_collection_or_falls_back_in_process(status, controlled_transport, monkeypatch):
    monkeypatch.setattr(supervisor, "_execute", lambda *_a, **_k: supervisor.Outcome(status))
    monkeypatch.setattr("app.modules.ingestion.code_collect.analyze_source",
                        lambda *_a, **_k: pytest.fail("unsafe fallback"))
    raw = b"function fixture() {}\n"
    with pytest.raises(CollectionError, match="^supervised_parser_" + status.value + "$"):
        collect_source(SyntheticBlob(raw), "fixture", "demo/repo", plan_for("src/x.js", raw), supervised=True)


def test_signaled_child_preserves_sanitized_signal_code(controlled_transport, monkeypatch):
    monkeypatch.setattr(supervisor, "_execute", lambda *_a, **_k: supervisor.Outcome(
        supervisor.Status.WORKER_EXITED, exit_code=-15))
    raw = b"function fixture() {}\n"
    with pytest.raises(CollectionError, match="^supervised_parser_worker_signal_15$"):
        collect_source(SyntheticBlob(raw), "fixture", "demo/repo", plan_for("src/x.js", raw), supervised=True)


@pytest.mark.parametrize("field", ["request_id", "source_sha256", "path", "start_line", "end_byte"])
def test_mismatched_or_malformed_response_fails_closed(field, controlled_transport, monkeypatch):
    def execute(request, source, *, timeout):
        response = response_for(request, source)
        if field in {"request_id", "source_sha256", "path"}:
            response[field] = "wrong"
        else:
            response["chunks"][0][field] = 9999
        return supervisor._validate((json.dumps(response) + "\n").encode(), request, source, 123)

    monkeypatch.setattr(supervisor, "_execute", execute)
    raw = b"function fixture() {}\n"
    with pytest.raises(CollectionError, match="supervised_parser_output_rejected"):
        collect_source(SyntheticBlob(raw), "fixture", "demo/repo", plan_for("src/x.js", raw), supervised=True)


def test_fabricated_chunk_symbol_is_rejected(controlled_transport, monkeypatch):
    def execute(request, source, *, timeout):
        response = response_for(request, source)
        response["chunks"][0]["symbol"] = "invented"
        return supervisor._validate((json.dumps(response) + "\n").encode(), request, source, 123)

    monkeypatch.setattr(supervisor, "_execute", execute)
    raw = b"function fixture() {}\n"
    with pytest.raises(CollectionError, match="supervised_parser_output_rejected"):
        collect_source(SyntheticBlob(raw), "fixture", "demo/repo", plan_for("src/x.js", raw), supervised=True)


def test_collection_revalidates_even_a_forged_success(controlled_transport, monkeypatch):
    def forged(source, *, path, language, request_id, expected_sha256):
        request = supervisor._request(source, path, language, request_id, 120, expected_sha256)
        response = response_for(request, source)
        response["request_id"] = "0" * 32
        return supervisor.Outcome(supervisor.Status.PARSED, response)

    monkeypatch.setattr(supervisor, "run", forged)
    raw = b"def fixture(): pass\n"
    with pytest.raises(CollectionError, match="supervised_parser_output_rejected"):
        collect_source(SyntheticBlob(raw), "fixture", "demo/repo", plan_for("src/x.py", raw), supervised=True)


def test_success_without_response_is_not_reported_as_parsed(controlled_transport, monkeypatch):
    monkeypatch.setattr(supervisor, "_execute", lambda *_a, **_k: supervisor.Outcome(supervisor.Status.PARSED))
    raw = b"def fixture(): pass\n"
    with pytest.raises(CollectionError, match="^supervised_parser_output_rejected$"):
        collect_source(SyntheticBlob(raw), "fixture", "demo/repo", plan_for("src/x.py", raw), supervised=True)


def test_request_identity_binds_commit_and_is_not_reused(controlled_transport, monkeypatch):
    monkeypatch.setattr("app.modules.ingestion.code_collect.uuid4", lambda: type("Nonce", (), {"hex": "1" * 32})())
    raw = b"def fixture(): pass\n"
    for commit in ("a" * 40, "b" * 40):
        collect_source(SyntheticBlob(raw), "fixture", "demo/repo", plan_for("src/x.py", raw, commit=commit),
                       supervised=True)
    assert controlled_transport[0][0]["request_id"] != controlled_transport[1][0]["request_id"]


def test_missing_isolation_fails_before_blob_read_or_subprocess(monkeypatch):
    monkeypatch.setattr(supervisor, "isolation_available", lambda: False)
    monkeypatch.setattr(supervisor.subprocess, "Popen", lambda *_a, **_k: pytest.fail("child started"))
    source = SyntheticBlob(b"def fixture(): pass\n")
    with pytest.raises(CollectionError, match="supervised_parser_isolation_unavailable"):
        collect_source(source, "fixture", "demo/repo", plan_for("src/x.py", source.content), supervised=True)
    assert source.calls == 0


@pytest.mark.parametrize(("commit", "blob"), [("bad", "b" * 40), ("a" * 40, "bad")])
def test_invalid_pinned_identity_never_reaches_worker(commit, blob, controlled_transport):
    raw = b"def fixture(): pass\n"
    with pytest.raises(CollectionError, match="supervised_parser_snapshot_invalid"):
        collect_source(SyntheticBlob(raw), "fixture", "demo/repo",
                       plan_for("src/x.py", raw, commit=commit, blob=blob), supervised=True)
    assert controlled_transport == []


def test_linux_is_explicitly_unsupported(monkeypatch):
    monkeypatch.setattr(supervisor, "sys", type("OS", (), {"platform": "linux"})())
    assert not supervisor.isolation_available()
    assert supervisor._execute({}, b"", timeout=1).status == supervisor.Status.ISOLATION_UNAVAILABLE


def test_realistic_relative_path_is_inert_metadata():
    raw = b"def fixture(): pass\n"
    path = "src/é space$(ignored).py"
    request = supervisor._request(raw, path, "python", "a" * 32, 120, sha256(raw).hexdigest())
    assert request["path"] == path


def test_child_environment_and_argv_exclude_credentials(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "synthetic-token")
    monkeypatch.setenv("DATABASE_URL", "synthetic-database")
    monkeypatch.setattr(supervisor, "isolation_available", lambda: True)
    captured = {}

    def popen(argv, **kwargs):
        captured.update(argv=argv, kwargs=kwargs)
        return object()

    monkeypatch.setattr(supervisor.subprocess, "Popen", popen)
    monkeypatch.setattr(supervisor, "_supervise", lambda *_a: supervisor.Outcome(supervisor.Status.TIMEOUT))
    raw = b"def fixture(): pass\n"
    result = supervisor.run(raw, path="src/x.py", language="python", request_id="a" * 32,
                            expected_sha256=sha256(raw).hexdigest())
    assert result.status == supervisor.Status.TIMEOUT
    assert captured["argv"][0] == supervisor.SANDBOX and "-I" in captured["argv"]
    assert "-S" in captured["argv"] and "-B" in captured["argv"]
    assert captured["kwargs"].get("shell", False) is False
    assert "GITHUB_TOKEN" not in captured["kwargs"]["env"]
    assert "DATABASE_URL" not in captured["kwargs"]["env"]
    assert "synthetic-token" not in repr(captured) and "synthetic-database" not in repr(captured)


def test_temporary_cleanup_error_is_typed(monkeypatch):
    real_temporary = supervisor.tempfile.TemporaryDirectory

    class FailedCleanup:
        def __init__(self, **kwargs):
            self.temporary = real_temporary(**kwargs)

        def __enter__(self):
            return self.temporary.__enter__()

        def __exit__(self, *args):
            self.temporary.__exit__(*args)
            raise OSError("synthetic cleanup failure")

    monkeypatch.setattr(supervisor, "isolation_available", lambda: True)
    monkeypatch.setattr(supervisor.tempfile, "TemporaryDirectory", FailedCleanup)
    monkeypatch.setattr(supervisor.subprocess, "Popen", lambda *_a, **_k: object())
    monkeypatch.setattr(supervisor, "_supervise", lambda *_a: supervisor.Outcome(supervisor.Status.TIMEOUT))
    raw = b"def fixture(): pass\n"
    result = supervisor.run(raw, path="src/x.py", language="python", request_id="a" * 32,
                            expected_sha256=sha256(raw).hexdigest())
    assert result.status == supervisor.Status.CLEANUP_FAILED and result.response is None


@pytest.mark.parametrize(("code", "expected"), [
    (71, supervisor.Status.ISOLATION_OR_LAUNCH_FAILED),
    (78, supervisor.Status.INITIALIZATION_FAILED),
])
def test_sandbox_launch_and_child_initialization_are_distinct(code, expected, monkeypatch):
    monkeypatch.setattr(supervisor, "isolation_available", lambda: True)
    monkeypatch.setattr(supervisor.subprocess, "Popen", lambda *_a, **_k: object())
    monkeypatch.setattr(supervisor, "_supervise", lambda *_a: supervisor.Outcome(
        supervisor.Status.INITIALIZATION_FAILED, exit_code=code))
    raw = b"def fixture(): pass\n"
    result = supervisor.run(raw, path="src/x.py", language="python", request_id="a" * 32,
                            expected_sha256=sha256(raw).hexdigest())
    assert result.status == expected and result.exit_code == code


def test_worker_ignores_supervised_flag_for_python_only_job(client, factory, github_auth, monkeypatch):
    connect(client)
    monkeypatch.setattr(get_settings(), "index_multilingual_enabled", False)
    monkeypatch.setattr(get_settings(), "index_multilingual_supervised_parser_enabled", True)
    monkeypatch.setattr(supervisor, "run", lambda *_a, **_k: pytest.fail("supervisor unexpectedly called"))
    job_id = client.post("/v1/repositories/902/index", headers=csrf(client)).json()["job_id"]
    process_index(job_id, factory, github_auth, FakeSource())
    with factory() as db:
        job = db.get(IndexJob, job_id)
        assert job.indexing_mode == "python" and job.status == "completed"
        assert db.scalar(select(CodeChunk)).symbol == "calculate_total"


def test_failed_supervised_job_keeps_previous_publication(client, factory, github_auth, controlled_transport,
                                                          monkeypatch):
    connect(client)
    first = client.post("/v1/repositories/902/index", headers=csrf(client)).json()["job_id"]
    process_index(first, factory, github_auth, FakeSource())
    with factory() as db:
        previous = db.scalar(select(CodeSnapshot).where(CodeSnapshot.published.is_(True)))
        previous_id = previous.id
        previous_chunks = len(db.scalars(select(CodeChunk)).all())
    monkeypatch.setattr(get_settings(), "index_multilingual_enabled", True)
    monkeypatch.setattr(get_settings(), "index_multilingual_supervised_parser_enabled", True)
    second = client.post("/v1/repositories/902/index", headers=csrf(client)).json()["job_id"]
    successful_execute = supervisor._execute

    def fail_second(request, source, *, timeout):
        if request["path"].endswith("beta.py"):
            return supervisor.Outcome(supervisor.Status.TIMEOUT)
        return successful_execute(request, source, timeout=timeout)

    class TwoFiles(FakeSource):
        def tree(self, token, full_name, sha):
            return {"truncated": False, "tree": [
                {"path": "src/alpha.py", "type": "blob", "mode": "100644", "sha": "b" * 40,
                 "size": len(self.source)},
                {"path": "src/beta.py", "type": "blob", "mode": "100644", "sha": "c" * 40,
                 "size": len(self.source)},
            ]}

    monkeypatch.setattr(supervisor, "_execute", fail_second)
    process_index(second, factory, github_auth, TwoFiles())
    process_index(second, factory, github_auth, TwoFiles())
    assert len(controlled_transport) == 1
    with factory() as db:
        job = db.get(IndexJob, second)
        assert job.status == "failed" and job.error_code == "supervised_parser_timeout"
        assert db.scalar(select(CodeSnapshot).where(CodeSnapshot.published.is_(True))).id == previous_id
        assert len(db.scalars(select(CodeChunk)).all()) == previous_chunks
    status = client.get("/v1/repositories/902/index-status").json()
    assert status["status"] == "failed" and status["error_code"] == "supervised_parser_timeout"
    assert "sensitive-github-token" not in repr(status)


def test_successful_supervised_synthetic_publication_preserves_identity(client, factory, github_auth,
                                                                        controlled_transport, monkeypatch):
    connect(client)
    monkeypatch.setattr(get_settings(), "index_multilingual_enabled", True)
    monkeypatch.setattr(get_settings(), "index_multilingual_supervised_parser_enabled", True)
    job_id = client.post("/v1/repositories/902/index", headers=csrf(client)).json()["job_id"]
    process_index(job_id, factory, github_auth, FakeSource())
    with factory() as db:
        job = db.get(IndexJob, job_id)
        snapshot = db.scalar(select(CodeSnapshot).where(CodeSnapshot.published.is_(True)))
        item = db.scalar(select(IndexedFile).where(IndexedFile.snapshot_id == snapshot.id))
        chunk = db.scalar(select(CodeChunk).where(CodeChunk.file_id == item.id))
        assert job.status == "completed" and snapshot.commit_sha == "a" * 40
        assert snapshot.tenant_id == item.tenant_id == chunk.tenant_id == job.tenant_id
        assert snapshot.repository_id == item.repository_id == chunk.repository_id == job.repository_id
        assert item.content_hash == sha256(FakeSource.source).hexdigest()
        assert chunk.source_text.encode() == FakeSource.source


def test_existing_multilingual_job_remains_supervised_when_admission_disabled(
        client, factory, github_auth, controlled_transport, monkeypatch):
    connect(client)
    monkeypatch.setattr(get_settings(), "index_multilingual_enabled", True)
    monkeypatch.setattr(get_settings(), "index_multilingual_supervised_parser_enabled", True)
    job_id = client.post("/v1/repositories/902/index", headers=csrf(client)).json()["job_id"]
    monkeypatch.setattr(get_settings(), "index_multilingual_enabled", False)
    process_index(job_id, factory, github_auth, FakeSource())
    with factory() as db:
        assert db.get(IndexJob, job_id).status == "completed"
        assert db.get(IndexJob, job_id).indexing_mode == "multi_supervised"
    assert len(controlled_transport) == 1


def test_queued_supervised_job_fails_closed_if_flag_is_disabled(client, factory, github_auth, monkeypatch):
    connect(client)
    monkeypatch.setattr(get_settings(), "index_multilingual_enabled", True)
    monkeypatch.setattr(get_settings(), "index_multilingual_supervised_parser_enabled", True)
    job_id = client.post("/v1/repositories/902/index", headers=csrf(client)).json()["job_id"]
    monkeypatch.setattr(get_settings(), "index_multilingual_supervised_parser_enabled", False)
    monkeypatch.setattr("app.modules.ingestion.code_collect.analyze_source",
                        lambda *_a, **_k: pytest.fail("unsafe in-process fallback"))
    monkeypatch.setattr(supervisor, "run", lambda *_a, **_k: pytest.fail("disabled supervisor called"))
    process_index(job_id, factory, github_auth, FakeSource())
    with factory() as db:
        job = db.get(IndexJob, job_id)
        assert (job.status, job.error_code, job.indexing_mode) == (
            "failed", "supervised_parser_disabled", "multi_supervised")
        assert db.scalar(select(CodeSnapshot)) is None


def test_legacy_queued_multilingual_job_uses_supervisor_if_enabled(
        client, factory, github_auth, controlled_transport, monkeypatch):
    connect(client)
    monkeypatch.setattr(get_settings(), "index_multilingual_enabled", True)
    monkeypatch.setattr(get_settings(), "index_multilingual_supervised_parser_enabled", False)
    job_id = client.post("/v1/repositories/902/index", headers=csrf(client)).json()["job_id"]
    monkeypatch.setattr(get_settings(), "index_multilingual_supervised_parser_enabled", True)
    process_index(job_id, factory, github_auth, FakeSource())
    with factory() as db:
        assert db.get(IndexJob, job_id).status == "completed"
        assert db.get(IndexJob, job_id).indexing_mode == "multilingual"
    assert len(controlled_transport) == 1


def test_supervised_republication_has_distinct_uuid_and_fingerprints(client, factory, github_auth,
                                                                    controlled_transport, monkeypatch):
    connect(client)
    monkeypatch.setattr(get_settings(), "index_multilingual_enabled", True)
    monkeypatch.setattr(get_settings(), "index_multilingual_supervised_parser_enabled", True)
    snapshot_ids = []
    for _ in range(2):
        job_id = client.post("/v1/repositories/902/index", headers=csrf(client)).json()["job_id"]
        process_index(job_id, factory, github_auth, FakeSource())
        with factory() as db:
            assert db.get(IndexJob, job_id).status == "completed"
            snapshot_ids.append(db.scalar(select(CodeSnapshot.id).where(CodeSnapshot.published.is_(True))))
    with factory() as db:
        snapshots = [db.get(CodeSnapshot, snapshot_id) for snapshot_id in snapshot_ids]
        files = [db.scalar(select(IndexedFile).where(IndexedFile.snapshot_id == item.id)) for item in snapshots]
        chunks = [db.scalar(select(CodeChunk).where(CodeChunk.file_id == item.id)) for item in files]
        ids = [item.id for item in snapshots + files + chunks]
        assert len(ids) == len(set(ids)) and all(UUID(value).version == 4 for value in ids)
        assert files[0].content_hash == files[1].content_hash == sha256(FakeSource.source).hexdigest()
        assert chunks[0].source_text == chunks[1].source_text
        assert fingerprint_chunk(chunks[0], files[0]) != fingerprint_chunk(chunks[1], files[1])
