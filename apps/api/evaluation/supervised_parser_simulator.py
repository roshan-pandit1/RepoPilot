"""Fixed failure scenarios for the test-only supervisor, using synthetic data only."""

import base64
import hashlib
import json
import os
import resource
import sys
import sysconfig
import time

resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
resource.setrlimit(resource.RLIMIT_CPU, (5, 6))
resource.setrlimit(resource.RLIMIT_FSIZE, (1_048_576, 1_048_576))
resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
mode = sys.argv[1]
request = json.loads(sys.stdin.buffer.read(150_001))
if mode == "exception":
    raise RuntimeError("synthetic error")
if mode == "exit":
    os._exit(41)
if mode == "signal":
    import signal

    os.kill(os.getpid(), signal.SIGTERM)
    os._exit(42)
if mode == "disappear":
    os._exit(0)
if mode == "init":
    os._exit(78)
if mode == "hang":
    time.sleep(60)
if mode == "truncated":
    print('{"version":1', end="", flush=True)
    os._exit(0)
if mode == "malformed":
    print("{not-json}", flush=True)
    os._exit(0)
if mode == "oversized":
    os.write(1, b"x" * 1_000_001)
    os._exit(0)
if mode == "parser_error":
    print(json.dumps({"version": 1, "request_id": request["request_id"], "error": "parser_error"}),
          flush=True)
    os._exit(0)
if mode == "isolation":
    import ctypes
    import socket
    from pathlib import Path

    try:
        (Path.cwd().parent / "guard.txt").read_text(encoding="utf-8")
        os._exit(2)
    except PermissionError:
        pass
    try:
        (Path.cwd().parent / "write-probe").write_text("synthetic", encoding="utf-8")
        os._exit(7)
    except PermissionError:
        pass
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.2)
        sock.connect(("127.0.0.1", 9))
        os._exit(3)
    except PermissionError:
        pass
    finally:
        if "sock" in locals():
            sock.close()
    if any(key in os.environ for key in ("GITHUB_TOKEN", "DATABASE_URL", "TEST_DATABASE_URL")):
        os._exit(4)
    check = ctypes.CDLL("/usr/lib/system/libsystem_sandbox.dylib").sandbox_check
    check.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
    check.restype = ctypes.c_int
    if check(os.getpid(), b"process-fork", 0) != 1:
        os._exit(5)
    if (resource.getrlimit(resource.RLIMIT_CORE) != (0, 0)
            or resource.getrlimit(resource.RLIMIT_CPU) != (5, 6)
            or resource.getrlimit(resource.RLIMIT_NOFILE) != (32, 32)):
        os._exit(8)
    try:
        # Controlled replacement canary: no fork, shell, repository code or arguments.
        os.execve("/usr/bin/true", ["/usr/bin/true"], {})
    except PermissionError:
        pass
    mode = "ok"
if mode == "reference":
    from pathlib import Path

    sys.path.insert(0, sysconfig.get_path("purelib"))
    sys.path.insert(0, str(Path(__file__).parent))
    from app.modules.ingestion.code_chunking import chunk_multilingual, chunk_python
    from app.modules.ingestion.language_analysis import LANGUAGES, analyze_source

    raw = base64.b64decode(request["source_b64"], validate=True)
    text = raw.decode("utf-8")
    info = analyze_source(request["path"], text, timeout_seconds=1)
    pieces = (chunk_python(text, max_lines=request["max_lines"]) if info.language == "python"
              else chunk_multilingual(text, info, max_lines=request["max_lines"]))
    lines = text.splitlines(keepends=True)
    offsets = [len("".join(lines[:index]).encode()) for index in range(len(lines) + 1)]
    registered = LANGUAGES[Path(request["path"]).suffix]
    response = {
        "version": 1, "request_id": request["request_id"], "worker_pid": os.getpid(),
        "language": info.language,
        "path": request["path"], "source_sha256": hashlib.sha256(raw).hexdigest(),
        "grammar": registered.module, "grammar_entrypoint": registered.entrypoint,
        "parser_version": info.parser_version, "parser_status": "fallback" if info.fallback_reason else "parsed",
        "fallback_reason": info.fallback_reason,
        "chunk_strategy": "python-ast" if info.language == "python" else "multilingual",
        "symbols": [{"name": s.name, "kind": s.kind, "parent": s.parent,
                     "start_line": s.start_line, "end_line": s.end_line} for s in info.symbols],
        "imports": [list(r) for r in info.import_lines],
        "chunks": [{"start_line": c.start_line, "end_line": c.end_line,
                    "start_byte": offsets[c.start_line - 1], "end_byte": offsets[c.end_line],
                    "content_sha256": hashlib.sha256(c.text.encode()).hexdigest(),
                    "symbol": c.symbol, "symbol_kind": c.symbol_kind} for c in pieces],
    }
    print(json.dumps(response, separators=(",", ":")), flush=True)
    os._exit(0)

raw = base64.b64decode(request["source_b64"])
assert raw == b"x\n"
response = {
    "version": 1, "request_id": request["request_id"], "worker_pid": os.getpid(),
    "language": request["language"],
    "path": request["path"], "source_sha256": request["source_sha256"],
    "grammar": "ast", "grammar_entrypoint": "language",
    "parser_version": "languages-v1:python-" + ".".join(map(str, sys.version_info[:3])),
    "parser_status": "parsed",
    "fallback_reason": None, "chunk_strategy": "python-ast", "symbols": [], "imports": [],
    "chunks": [{"start_line": 1, "end_line": 1, "start_byte": 0, "end_byte": len(raw),
                "content_sha256": hashlib.sha256(raw).hexdigest(), "symbol": None,
                "symbol_kind": None}],
}
if mode == "wrong_id":
    response["request_id"] = "f" * 32
elif mode == "wrong_hash":
    response["source_sha256"] = "0" * 64
elif mode == "wrong_pid":
    response["worker_pid"] = os.getpid() + 1
elif mode == "wrong_chunk_hash":
    response["chunks"][0]["content_sha256"] = "0" * 64
elif mode == "wrong_parser":
    response["parser_version"] = "languages-v1:python-0.0.0"
elif mode == "wrong_grammar":
    response["grammar"] = "not-ast"
elif mode == "wrong_range":
    response["chunks"][0]["end_line"] = 99
elif mode == "wrong_bytes":
    response["chunks"][0]["end_byte"] = 1
elif mode == "wrong_version":
    response["version"] = 2
elif mode == "incomplete":
    response["chunks"] = []
elif mode == "unavailable":
    response["parser_version"] = "unavailable"
    response["parser_status"] = "fallback"
    response["fallback_reason"] = "parser_unavailable"
elif mode == "ok":
    pass
else:
    raise ValueError("unknown fixed scenario")
print(json.dumps(response, separators=(",", ":")), flush=True)
