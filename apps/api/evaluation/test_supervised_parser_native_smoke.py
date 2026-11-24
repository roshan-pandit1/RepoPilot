"""Synthetic Python and missing-grammar checks of the integrated child and transport.

Uses the existing interpreter's resolved executable without creating a venv.
This directly exercises the staged child and supervisor; it deliberately does
not bypass the production isolation-availability gate in `run`.
"""

from hashlib import sha256
from pathlib import Path
import os
import shutil
import signal
import subprocess
import sys
import tempfile

import pytest

from app.modules.ingestion import supervised_parser as supervisor


def simulated_child(mode):
    source = b"x\n"
    request = supervisor._request(source, "synthetic/example.py", "python", "a" * 32,
                                  120, sha256(source).hexdigest())
    with tempfile.TemporaryDirectory(prefix="repopilot-parser-failure-", dir="/private/tmp") as temporary:
        root = Path(temporary)
        os.chmod(root, 0o700)
        work = root / "work"
        work.mkdir(mode=0o700)
        simulator = work / "simulator.py"
        shutil.copyfile(Path(__file__).parent / "supervised_parser_simulator.py", simulator)
        if mode == "isolation":
            (root / "guard.txt").write_text("synthetic sentinel", encoding="utf-8")
            os.chmod(root / "guard.txt", 0o600)
        argv = [supervisor.SANDBOX, "-p", supervisor._profile(work), str(Path(sys.executable).resolve()),
                "-I", "-S", "-B", str(simulator), mode]
        env = {"PATH": "/usr/bin:/bin", "HOME": str(work), "TMPDIR": str(work),
               "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                cwd=work, env=env, start_new_session=True, close_fds=True)
        outcome = supervisor._supervise(proc, request, source, 1 if mode == "hang" else 10)
        assert proc.poll() is not None
        return outcome


@pytest.mark.parametrize(("mode", "expected"), [
    ("exception", supervisor.Status.WORKER_EXITED), ("exit", supervisor.Status.WORKER_EXITED),
    ("signal", supervisor.Status.WORKER_EXITED), ("disappear", supervisor.Status.OUTPUT_REJECTED),
    ("init", supervisor.Status.INITIALIZATION_FAILED), ("hang", supervisor.Status.TIMEOUT),
    ("truncated", supervisor.Status.OUTPUT_REJECTED), ("malformed", supervisor.Status.OUTPUT_REJECTED),
    ("oversized", supervisor.Status.OUTPUT_TOO_LARGE), ("parser_error", supervisor.Status.PARSER_ERROR),
    ("wrong_id", supervisor.Status.OUTPUT_REJECTED), ("wrong_hash", supervisor.Status.OUTPUT_REJECTED),
    ("wrong_pid", supervisor.Status.OUTPUT_REJECTED), ("wrong_chunk_hash", supervisor.Status.OUTPUT_REJECTED),
    ("wrong_parser", supervisor.Status.OUTPUT_REJECTED), ("wrong_grammar", supervisor.Status.OUTPUT_REJECTED),
    ("wrong_range", supervisor.Status.OUTPUT_REJECTED), ("wrong_bytes", supervisor.Status.OUTPUT_REJECTED),
    ("wrong_version", supervisor.Status.OUTPUT_REJECTED), ("incomplete", supervisor.Status.OUTPUT_REJECTED),
])
def test_integrated_transport_contains_synthetic_failures(mode, expected):
    if sys.platform != "darwin" or not Path(supervisor.SANDBOX).is_file():
        pytest.skip("reviewed macOS sandbox unavailable")
    result = simulated_child(mode)
    assert result.status == expected and result.response is None
    if mode == "signal":
        assert result.exit_code == -signal.SIGTERM
    assert simulated_child("ok").status == supervisor.Status.PARSED


def test_integrated_profile_synthetic_isolation_canary(monkeypatch):
    if sys.platform != "darwin" or not Path(supervisor.SANDBOX).is_file():
        pytest.skip("reviewed macOS sandbox unavailable")
    monkeypatch.setenv("GITHUB_TOKEN", "synthetic-canary")
    monkeypatch.setenv("DATABASE_URL", "synthetic-canary")
    assert simulated_child("isolation").status == supervisor.Status.PARSED


@pytest.mark.parametrize(("source", "path", "language", "status", "reason"), [
    ("import os\r\n# café\r\ndef fixture():\r\n    return 1\r\n",
     "synthetic/example.py", "python", supervisor.Status.PARSED, None),
    ("def broken(\n", "synthetic/example.py", "python", supervisor.Status.FALLBACK, "syntax_error"),
    ("def long_fn():\n" + "    x = 1\n" * 121 + "    return x\n",
     "synthetic/long.py", "python", supervisor.Status.PARSED, None),
    ("package demo\nfunc fixture() {}\n", "synthetic/example.go", "go",
     supervisor.Status.UNAVAILABLE, "parser_unavailable"),
])
def test_integrated_child_synthetic_transport(source, path, language, status, reason):
    if sys.platform != "darwin" or not Path(supervisor.SANDBOX).is_file():
        pytest.skip("reviewed macOS sandbox unavailable")
    raw = source.encode()
    request = supervisor._request(raw, path, language, "a" * 32,
                                  120, sha256(raw).hexdigest())
    with tempfile.TemporaryDirectory(prefix="repopilot-parser-smoke-", dir="/private/tmp") as temporary:
        root = Path(temporary)
        os.chmod(root, 0o700)
        work = root / "work"
        work.mkdir(mode=0o700)
        child = supervisor._stage(work)
        argv = [supervisor.SANDBOX, "-p", supervisor._profile(work), str(Path(sys.executable).resolve()),
                "-I", "-S", "-B", str(child)]
        env = {"PATH": "/usr/bin:/bin", "HOME": str(work), "TMPDIR": str(work),
               "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                cwd=work, env=env, start_new_session=True, close_fds=True)
        outcome = supervisor._supervise(proc, request, raw, 10)
    assert outcome.status == status and outcome.exit_code == 0
    assert outcome.response["fallback_reason"] == reason
    assert outcome.response["source_sha256"] == sha256(raw).hexdigest()
    assert b"".join(raw[item["start_byte"]:item["end_byte"]]
                    for item in outcome.response["chunks"]) == raw
    if reason is None and path.endswith("example.py"):
        assert outcome.response["imports"] == [[1, 1]]
        assert [item["name"] for item in outcome.response["symbols"]] == ["fixture"]
        assert outcome.response["chunks"][-1]["symbol"] == "fixture"
    elif reason is None:
        assert [item["symbol"] for item in outcome.response["chunks"]] == ["long_fn", "long_fn"]
    else:
        assert not outcome.response["symbols"]
