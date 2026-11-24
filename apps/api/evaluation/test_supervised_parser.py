"""Synthetic tests for the disconnected, test-only parser supervisor."""

from hashlib import sha256
from pathlib import Path
import signal
import sys
from types import SimpleNamespace

import pytest

API = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API))
sys.path.insert(0, str(API / "evaluation"))

import supervised_parser as supervisor  # noqa: E402
from app.modules.ingestion.citations import github_citation  # noqa: E402
from app.modules.ingestion.language_analysis import LANGUAGES  # noqa: E402
from app.modules.investigation.retrieval import fingerprint_chunk  # noqa: E402
from fixtures.tree_sitter_0252_matrix_fixtures import VARIANTS, small  # noqa: E402

IDENTITY = "a" * 32


def simulated(mode, *, timeout=5):
    source = b"x\n"
    request = supervisor._request(source, "synthetic/check.py", "python", IDENTITY, 120,
                                  sha256(source).hexdigest())
    return supervisor._execute(request, source, timeout=timeout, simulate=mode)


@pytest.fixture(scope="session", autouse=True)
def enforce_isolation():
    # Before parsing, verify network and out-of-workspace data-read denial.
    result = simulated("isolation")
    assert result.status == supervisor.Status.PARSED, (result.status, result.exit_code)


@pytest.mark.parametrize("extension", sorted(VARIANTS))
def test_synthetic_variants_match_direct_parser_and_chunker(extension):
    source, _, expected_symbols = small(extension)
    path = "synthetic/example" + extension
    language = VARIANTS[extension]
    outcome = supervisor.run(source.encode(), path=path, language=language, request_id=IDENTITY,
                             expected_sha256=sha256(source.encode()).hexdigest())
    assert outcome.status == supervisor.Status.PARSED, (extension, outcome.status, outcome.exit_code)
    result = outcome.response
    assert result["source_sha256"] == sha256(source.encode()).hexdigest()
    assert (result["grammar"], result["grammar_entrypoint"]) == (
        LANGUAGES[extension].module, LANGUAGES[extension].entrypoint)
    request = supervisor._request(source.encode(), path, language, IDENTITY, 120, sha256(source.encode()).hexdigest())
    direct = supervisor._execute(request, source.encode(), timeout=10, simulate="reference")
    assert direct.status == supervisor.Status.PARSED
    assert {k: v for k, v in result.items() if k != "worker_pid"} == {
        k: v for k, v in direct.response.items() if k != "worker_pid"}
    assert set(expected_symbols) <= {item["name"] for item in result["symbols"]}
    for returned, chunk in zip(result["chunks"], direct.response["chunks"], strict=True):
        assert returned == chunk
        source_bytes = source.encode()[chunk["start_byte"]:chunk["end_byte"]]
        assert returned["content_sha256"] == sha256(source_bytes).hexdigest()
        file = SimpleNamespace(snapshot_id="fixture-snapshot", path=path,
                               content_hash=result["source_sha256"])
        original = SimpleNamespace(id="fixture-chunk", file_id="fixture-file", symbol=chunk["symbol"],
                                   start_line=chunk["start_line"], end_line=chunk["end_line"],
                                   source_text=source_bytes.decode())
        copied = SimpleNamespace(**vars(original))
        copied.start_line, copied.end_line = returned["start_line"], returned["end_line"]
        copied.source_text = source.encode()[returned["start_byte"]:returned["end_byte"]].decode()
        assert fingerprint_chunk(original, file) == fingerprint_chunk(copied, file)
        assert github_citation("fixture/project", "b" * 40, path, chunk["start_line"], chunk["end_line"]).endswith(
            f"/{path}#L{chunk['start_line']}-L{chunk['end_line']}")


@pytest.mark.parametrize("extension", [".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go",
                                        ".rs", ".c", ".cpp", ".cs"])
def test_malformed_syntax_is_explicit_fallback(extension):
    _, broken, _ = small(extension)
    result = supervisor.run(broken.encode(), path="synthetic/broken" + extension,
                            language=VARIANTS[extension], request_id=IDENTITY,
                            expected_sha256=sha256(broken.encode()).hexdigest())
    assert result.status == supervisor.Status.FALLBACK
    assert result.response["parser_status"] == "fallback"
    assert result.response["fallback_reason"] == "syntax_error"
    assert result.response["symbols"] == []
    assert result.response["imports"] == []


@pytest.mark.parametrize(("mode", "expected"), [
    ("exception", supervisor.Status.WORKER_EXITED),
    ("exit", supervisor.Status.WORKER_EXITED),
    ("signal", supervisor.Status.WORKER_EXITED),
    ("disappear", supervisor.Status.OUTPUT_REJECTED),
    ("init", supervisor.Status.INITIALIZATION_FAILED),
    ("hang", supervisor.Status.TIMEOUT),
    ("truncated", supervisor.Status.OUTPUT_REJECTED),
    ("malformed", supervisor.Status.OUTPUT_REJECTED),
    ("oversized", supervisor.Status.OUTPUT_TOO_LARGE),
    ("parser_error", supervisor.Status.PARSER_ERROR),
    ("wrong_id", supervisor.Status.OUTPUT_REJECTED),
    ("wrong_hash", supervisor.Status.OUTPUT_REJECTED),
    ("wrong_pid", supervisor.Status.OUTPUT_REJECTED),
    ("wrong_chunk_hash", supervisor.Status.OUTPUT_REJECTED),
    ("wrong_parser", supervisor.Status.OUTPUT_REJECTED),
    ("wrong_grammar", supervisor.Status.OUTPUT_REJECTED),
    ("wrong_range", supervisor.Status.OUTPUT_REJECTED),
    ("wrong_bytes", supervisor.Status.OUTPUT_REJECTED),
    ("wrong_version", supervisor.Status.OUTPUT_REJECTED),
    ("incomplete", supervisor.Status.OUTPUT_REJECTED),
])
def test_failed_children_never_produce_partial_results_and_next_request_survives(mode, expected, monkeypatch):
    children = []
    real_popen = supervisor.subprocess.Popen

    def record_child(*args, **kwargs):
        child = real_popen(*args, **kwargs)
        if args[0][0] == supervisor.SANDBOX:
            children.append(child)
        return child

    monkeypatch.setattr(supervisor.subprocess, "Popen", record_child)
    result = simulated(mode, timeout=1 if mode == "hang" else 5)
    assert result.status == expected, (mode, result)
    assert result.response is None
    assert len(children) == 1 and children[0].poll() is not None
    if mode == "signal":
        assert result.exit_code == -signal.SIGTERM
    if mode == "exit":
        assert result.exit_code == 41
    assert simulated("ok").status == supervisor.Status.PARSED


def test_unavailable_parser_is_not_syntax_aware_success():
    result = simulated("unavailable")
    assert result.status == supervisor.Status.UNAVAILABLE
    assert result.response["parser_status"] == "fallback"
    assert result.response["fallback_reason"] == "parser_unavailable"


def test_parent_environment_credentials_are_not_inherited(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "synthetic-canary")
    monkeypatch.setenv("DATABASE_URL", "synthetic-canary")
    assert simulated("isolation").status == supervisor.Status.PARSED


def test_expected_source_fingerprint_is_required(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("worker must not start")

    monkeypatch.setattr(supervisor, "_execute", forbidden)
    result = supervisor.run(b"x\n", path="synthetic/x.py", language="python", request_id=IDENTITY,
                            expected_sha256="0" * 64)
    assert result.status == supervisor.Status.INVALID_REQUEST


@pytest.mark.parametrize(("reading", "expected"), [(None, supervisor.Status.MONITOR_FAILED),
                                                 (supervisor.MAX_RSS_KIB + 1, supervisor.Status.RESOURCE_LIMIT)])
def test_monitor_failures_stop_and_reap_child(reading, expected, monkeypatch):
    monkeypatch.setattr(supervisor, "_rss_kib", lambda _pid: reading)
    result = simulated("hang")
    assert result.status == expected
    assert result.response is None and result.exit_code is not None


def test_pipe_monitor_error_reaps_child(monkeypatch):
    def broken_selector():
        raise OSError("synthetic monitor failure")

    monkeypatch.setattr(supervisor.selectors, "DefaultSelector", broken_selector)
    result = simulated("hang")
    assert result.status == supervisor.Status.MONITOR_FAILED
    assert result.response is None and result.exit_code is not None


def test_temporary_directory_failure_is_typed(monkeypatch):
    def no_temporary_directory(**_kwargs):
        raise OSError("synthetic temporary storage failure")

    monkeypatch.setattr(supervisor.tempfile, "TemporaryDirectory", no_temporary_directory)
    assert simulated("ok").status == supervisor.Status.INITIALIZATION_FAILED


def test_wait_failure_is_typed_and_child_is_reaped(monkeypatch):
    real_popen = supervisor.subprocess.Popen
    children = []

    def broken_wait_once(*args, **kwargs):
        child = real_popen(*args, **kwargs)
        if args[0][0] == supervisor.SANDBOX:
            original_wait = child.wait
            attempts = 0

            def wait(timeout=None):
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise OSError("synthetic wait failure")
                return original_wait(timeout=timeout)

            child.wait = wait
            children.append(child)
        return child

    monkeypatch.setattr(supervisor.subprocess, "Popen", broken_wait_once)
    result = simulated("ok")
    assert result.status == supervisor.Status.MONITOR_FAILED and result.response is None
    assert len(children) == 1 and children[0].poll() is not None


def test_cleanup_failure_is_reported_without_accepting_chunks(monkeypatch):
    real_kill = supervisor._kill

    def simulate_cleanup_failure(proc):
        assert real_kill(proc)  # Reap the real synthetic child before simulating the error.
        return False

    monkeypatch.setattr(supervisor, "_kill", simulate_cleanup_failure)
    result = simulated("hang", timeout=1)
    assert result.status == supervisor.Status.CLEANUP_FAILED
    assert result.response is None and result.exit_code is not None


@pytest.mark.parametrize(("source", "path", "language", "request_id"), [
    (b"x", "../x.py", "python", IDENTITY),
    (b"x", "/synthetic/x.py", "python", IDENTITY),
    (b"x", "synthetic/../x.py", "python", IDENTITY),
    (b"x", "synthetic/x.go", "python", IDENTITY),
    (b"x", "synthetic/x.py", "python", "bad"),
    (b"\xff", "synthetic/x.py", "python", IDENTITY),
    (b"\x00", "synthetic/x.py", "python", IDENTITY),
    (b"x" * (supervisor.MAX_SOURCE + 1), "synthetic/x.py", "python", IDENTITY),
], ids=["relative-traversal", "absolute", "nested-traversal", "wrong-language", "wrong-id",
        "invalid-utf8", "binary", "oversized"])
def test_invalid_requests_fail_before_start(source, path, language, request_id, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("worker must not start")

    monkeypatch.setattr(supervisor, "_execute", forbidden)
    assert supervisor.run(source, path=path, language=language, request_id=request_id,
                          expected_sha256=sha256(source).hexdigest()).status == (
        supervisor.Status.INVALID_REQUEST)


def test_protocol_rejects_duplicate_keys_and_wrong_error_identity():
    source = b"x\n"
    request = supervisor._request(source, "synthetic/check.py", "python", IDENTITY, 120,
                                  sha256(source).hexdigest())
    duplicate = b'{"version":1,"version":1,"error":"parser_error"}\n'
    wrong = b'{"version":1,"request_id":"wrong","error":"parser_error"}\n'
    assert supervisor._validate(duplicate, request, source, 1).status == supervisor.Status.OUTPUT_REJECTED
    assert supervisor._validate(wrong, request, source, 1).status == supervisor.Status.OUTPUT_REJECTED
