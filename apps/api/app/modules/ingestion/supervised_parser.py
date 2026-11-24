"""Opt-in parser supervision using the reviewed macOS prototype boundary.

The boundary fails closed on unsupported platforms and unreviewed interpreter
locations. It is not yet approved for normal-service or real-source activation.
"""

from __future__ import annotations

import base64
import ctypes
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from importlib import metadata
import json
import os
from pathlib import Path, PurePosixPath
import re
import selectors
import shutil
import subprocess
import sys
import tempfile
from time import monotonic

from app.modules.ingestion.code_selection import eligible_source_path
from app.modules.ingestion.language_analysis import LANGUAGES

MAX_SOURCE = 100_000
MAX_RESPONSE = 1_000_000
MAX_ITEMS = 2_000
MAX_RSS_KIB = 768 * 1024
SANDBOX = "/usr/bin/sandbox-exec"
MODULE_DIR = Path(__file__).resolve().parent
MODULES = ("code_selection.py", "code_chunking.py", "language_analysis.py")
EXTENSIONS = {suffix: language.name for suffix, language in LANGUAGES.items()}
GRAMMARS = {language.name: (language.module, language.entrypoint) for language in LANGUAGES.values()}


class Status(StrEnum):
    PARSED = "parsed"
    FALLBACK = "fallback"
    UNAVAILABLE = "unavailable"
    INVALID_REQUEST = "invalid_request"
    INITIALIZATION_FAILED = "initialization_failed"
    ISOLATION_UNAVAILABLE = "isolation_unavailable"
    ISOLATION_OR_LAUNCH_FAILED = "isolation_or_launch_failed"
    PARSER_ERROR = "parser_error"
    WORKER_EXITED = "worker_exited"
    TIMEOUT = "timeout"
    RESOURCE_LIMIT = "resource_limit"
    MONITOR_FAILED = "monitor_failed"
    OUTPUT_TOO_LARGE = "output_too_large"
    OUTPUT_REJECTED = "output_rejected"
    CLEANUP_FAILED = "cleanup_failed"


@dataclass(frozen=True)
class Outcome:
    status: Status
    response: dict | None = None
    exit_code: int | None = None
    peak_rss_kib: int = 0


def _request(source: bytes, path: str, language: str, request_id: str,
             max_lines: int, expected_sha256: str) -> dict:
    if (not isinstance(source, bytes) or len(source) > MAX_SOURCE or b"\x00" in source
            or not isinstance(path, str) or len(path) > 200
            or not eligible_source_path(path, multilingual=True, exclude_generated=True)
            or any(ord(char) < 32 or ord(char) == 127 for char in path)
            or EXTENSIONS.get(PurePosixPath(path).suffix.lower()) != language
            or not isinstance(expected_sha256, str) or sha256(source).hexdigest() != expected_sha256
            or not isinstance(request_id, str) or not re.fullmatch(r"[0-9a-f]{32}", request_id)
            or type(max_lines) is not int or not 1 <= max_lines <= 120):
        raise ValueError("invalid_request")
    source.decode("utf-8")
    return {"version": 1, "request_id": request_id, "language": language, "path": path,
            "source_b64": base64.b64encode(source).decode("ascii"),
            "source_sha256": sha256(source).hexdigest(), "max_lines": max_lines}


def _no_duplicates(pairs):
    output = {}
    for key, value in pairs:
        if key in output:
            raise ValueError("duplicate_key")
        output[key] = value
    return output


def _valid_text(value, *, optional=False):
    return (optional and value is None) or (isinstance(value, str) and 0 < len(value) <= 512)


def _range(first, last, maximum):
    return type(first) is int and type(last) is int and 1 <= first <= last <= maximum


def _validate(raw: bytes, request: dict, source: bytes, expected_pid: int) -> Outcome:
    try:
        if not raw.endswith(b"\n") or raw.count(b"\n") != 1:
            raise ValueError("incomplete")
        obj = json.loads(raw, object_pairs_hook=_no_duplicates,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError("constant")))
        if (isinstance(obj, dict) and type(obj.get("version")) is int
                and obj == {"version": 1, "request_id": request["request_id"], "error": "parser_error"}):
            return Outcome(Status.PARSER_ERROR)
        required = {"version", "request_id", "worker_pid", "language", "path", "source_sha256", "parser_version",
                    "grammar", "grammar_entrypoint",
                    "parser_status", "fallback_reason", "chunk_strategy", "symbols", "imports", "chunks"}
        if (not isinstance(obj, dict) or set(obj) != required or type(obj["version"]) is not int
                or obj["version"] != 1 or type(obj["worker_pid"]) is not int or obj["worker_pid"] != expected_pid
                or any(obj[k] != request[k] for k in
                    ("request_id", "language", "path", "source_sha256"))
                or not _valid_text(obj["parser_version"])
                or (obj["grammar"], obj["grammar_entrypoint"]) != GRAMMARS[request["language"]]
                or obj["chunk_strategy"] != ("python-ast" if request["language"] == "python"
                                             else "multilingual")):
            raise ValueError("identity")
        reason = obj["fallback_reason"]
        allowed_reasons = {"syntax_error", "node_limit", "parser_unavailable", "parse_timeout",
                           "parser_error", "unsupported_line_endings"}
        if ((obj["parser_status"] == "parsed" and reason is not None)
                or (obj["parser_status"] == "fallback" and reason not in allowed_reasons)
                or obj["parser_status"] not in {"parsed", "fallback"}):
            raise ValueError("status")
        if reason in {"parser_unavailable", "unsupported_line_endings"}:
            expected_parser = "unavailable"
        elif request["language"] == "python":
            expected_parser = "languages-v1:python-" + ".".join(map(str, sys.version_info[:3]))
        else:
            expected_parser = ("languages-v1:ts-" + metadata.version("tree-sitter") + ":"
                               + metadata.version(obj["grammar"].replace("_", "-")))
        if obj["parser_version"] != expected_parser:
            raise ValueError("parser_identity")
        lines = source.decode("utf-8").splitlines(keepends=True)
        offsets = [0]
        for line in lines:
            offsets.append(offsets[-1] + len(line.encode("utf-8")))
        if any(not isinstance(obj[k], list) or len(obj[k]) > MAX_ITEMS
               for k in ("chunks", "symbols", "imports")):
            raise ValueError("items")
        for symbol in obj["symbols"]:
            if (not isinstance(symbol, dict) or set(symbol) != {"name", "kind", "parent", "start_line", "end_line"}
                    or not _valid_text(symbol["name"]) or not _valid_text(symbol["kind"])
                    or not _valid_text(symbol["parent"], optional=True)
                    or not _range(symbol["start_line"], symbol["end_line"], len(lines))):
                raise ValueError("symbol")
        for item in obj["imports"]:
            if not isinstance(item, list) or len(item) != 2 or not _range(*item, len(lines)):
                raise ValueError("import")
        if reason is not None and (obj["symbols"] or obj["imports"]):
            raise ValueError("fallback_metadata")
        symbol_ranges = {(item["name"], item["start_line"], item["kind"]) for item in obj["symbols"]}
        symbol_positions = {(name, first) for name, first, _ in symbol_ranges}
        cursor = 1
        for chunk in obj["chunks"]:
            if (not isinstance(chunk, dict) or set(chunk) != {"start_line", "end_line", "start_byte", "end_byte",
                                                               "content_sha256", "symbol", "symbol_kind"}
                    or not _range(chunk["start_line"], chunk["end_line"], len(lines))
                    or chunk["start_line"] != cursor
                    or chunk["end_line"] - chunk["start_line"] + 1 > request["max_lines"]
                    or type(chunk["start_byte"]) is not int or type(chunk["end_byte"]) is not int
                    or chunk["start_byte"] != offsets[chunk["start_line"] - 1]
                    or chunk["end_byte"] != offsets[chunk["end_line"]]
                    or chunk["content_sha256"] != sha256(source[chunk["start_byte"]:chunk["end_byte"]]).hexdigest()
                    or not _valid_text(chunk["symbol"], optional=True)
                    or not _valid_text(chunk["symbol_kind"], optional=True)
                    or (chunk["symbol"] is None and chunk["symbol_kind"] is not None)
                    or (reason is not None and request["language"] != "python"
                        and (chunk["symbol"] is not None or chunk["symbol_kind"] is not None))
                    or (reason == "syntax_error" and request["language"] == "python"
                        and (chunk["symbol"] is not None or chunk["symbol_kind"] is not None))
                    or (reason is None and request["language"] != "python" and chunk["symbol"] is not None
                        and (chunk["symbol"], chunk["start_line"]) not in symbol_positions)
                    or (reason is None and request["language"] == "python" and chunk["symbol"] is not None
                        and not any(item["name"] == chunk["symbol"]
                                    and item["start_line"] <= chunk["start_line"]
                                    and chunk["end_line"] <= item["end_line"] for item in obj["symbols"]))
                    or (reason is None and chunk["symbol_kind"] is not None
                        and (chunk["symbol"], chunk["start_line"], chunk["symbol_kind"]) not in symbol_ranges)):
                raise ValueError("chunk")
            cursor = chunk["end_line"] + 1
        if cursor != len(lines) + 1:
            raise ValueError("coverage")
        status = (Status.UNAVAILABLE if reason == "parser_unavailable" else
                  Status.FALLBACK if reason else Status.PARSED)
        return Outcome(status, obj)
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError, metadata.PackageNotFoundError):
        return Outcome(Status.OUTPUT_REJECTED)


def _profile(work: Path) -> str:
    # macOS must read system libraries. Deny home, mounted projects, and other
    # temporary files; allow only the disposable environment and staged copy.
    work_path = json.dumps(str(work.resolve()))
    venv_path = json.dumps(str(Path(sys.prefix).resolve()))
    executables = {Path(sys.executable).absolute(), Path(sys.executable).resolve(),
                   Path(sys.executable).parent / "python3.14",
                   Path(sys.base_prefix).resolve() / "Resources/Python.app/Contents/MacOS/Python",
                   Path("/opt/homebrew/opt/python@3.14/bin/python3.14")}
    executable_rules = " ".join(f"(literal {json.dumps(str(path))})" for path in sorted(executables))
    writable = f'(subpath {json.dumps(str(work.resolve()))}) (literal "/dev/null")'
    return (f'(version 1)(allow default)(deny network*)(deny process-fork)(deny mach-lookup)'
            f'(deny process-exec (require-not (require-any {executable_rules})))'
            f'(deny file-read* (subpath "/Users") (subpath "/Volumes")'
            f' (subpath "/private/var/folders"))'
            f'(deny file-read-data (require-all (subpath "/private/tmp")'
            f' (require-not (require-any (subpath {work_path}) (subpath {venv_path})))))'
            f'(deny file-write* (require-not (require-any {writable})))')


def _stage(work: Path) -> Path:
    package = work / "app" / "modules" / "ingestion"
    package.mkdir(parents=True, mode=0o700)
    for directory in (work / "app", work / "app" / "modules", package):
        (directory / "__init__.py").write_text("", encoding="utf-8")
    for name in MODULES:
        src = MODULE_DIR / name
        if src.is_symlink() or not src.is_file():
            raise OSError("invalid_adapter")
        shutil.copyfile(src, package / name)
    child = "supervised_parser_child.py"
    src = MODULE_DIR / child
    if src.is_symlink() or not src.is_file():
        raise OSError("invalid_child")
    target = work / child
    shutil.copyfile(src, target)
    return target


def _rss_kib(pid: int) -> int | None:
    try:
        # Darwin PROC_PIDTASKINFO: the second uint64 is resident size in bytes.
        library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        query = library.proc_pidinfo
        query.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]
        query.restype = ctypes.c_int
        buffer = ctypes.create_string_buffer(4096)
        returned = query(pid, 4, 0, buffer, len(buffer))
        return int.from_bytes(buffer.raw[8:16], sys.byteorder) // 1024 if returned >= 16 else None
    except (AttributeError, OSError, ValueError):
        return None


def _kill(proc):
    if proc.poll() is None:
        try:
            # The sandbox forbids forks, so only this owned child needs a signal.
            proc.kill()
        except ProcessLookupError:
            pass
        except OSError:
            if proc.poll() is None:
                return False
    try:
        proc.wait(timeout=2)
        return True
    except (subprocess.TimeoutExpired, OSError):
        return False


def _supervise(proc, request: dict, source: bytes, timeout: float) -> Outcome:
    wire = (json.dumps(request, separators=(",", ":")) + "\n").encode()
    output = bytearray()
    deadline = monotonic() + timeout
    peak = 0
    next_sample = 0.0
    failure = None
    try:
        with selectors.DefaultSelector() as selector:
            os.set_blocking(proc.stdin.fileno(), False)
            os.set_blocking(proc.stdout.fileno(), False)
            selector.register(proc.stdin, selectors.EVENT_WRITE)
            selector.register(proc.stdout, selectors.EVENT_READ)
            sent = 0
            while selector.get_map():
                now = monotonic()
                if now >= deadline:
                    failure = Status.TIMEOUT
                    break
                if now >= next_sample and proc.poll() is None:
                    rss = _rss_kib(proc.pid)
                    if rss is None and proc.poll() is None:
                        failure = Status.MONITOR_FAILED
                        break
                    if rss is not None:
                        peak = max(peak, rss)
                        if rss > MAX_RSS_KIB:
                            failure = Status.RESOURCE_LIMIT
                            break
                    next_sample = monotonic() + 0.1
                for key, _ in selector.select(min(0.05, max(0, deadline - monotonic()))):
                    if key.fileobj is proc.stdin:
                        try:
                            sent += os.write(proc.stdin.fileno(), wire[sent:])
                        except BrokenPipeError:
                            sent = len(wire)
                        if sent == len(wire):
                            selector.unregister(proc.stdin)
                            proc.stdin.close()
                    else:
                        data = os.read(proc.stdout.fileno(), min(65_536, MAX_RESPONSE + 1 - len(output)))
                        if not data:
                            selector.unregister(proc.stdout)
                            proc.stdout.close()
                        else:
                            output.extend(data)
                            if len(output) > MAX_RESPONSE:
                                failure = Status.OUTPUT_TOO_LARGE
                                break
                if failure:
                    break
    except (OSError, ValueError):
        failure = Status.MONITOR_FAILED
    if failure:
        cleaned = _kill(proc)
        for pipe in (proc.stdin, proc.stdout):
            if not pipe.closed:
                pipe.close()
        return Outcome(failure if cleaned else Status.CLEANUP_FAILED,
                       exit_code=proc.returncode, peak_rss_kib=peak)
    remaining = max(0, deadline - monotonic())
    try:
        code = proc.wait(timeout=remaining)
    except subprocess.TimeoutExpired:
        cleaned = _kill(proc)
        return Outcome(Status.TIMEOUT if cleaned else Status.CLEANUP_FAILED,
                       exit_code=proc.returncode, peak_rss_kib=peak)
    except OSError:
        cleaned = _kill(proc)
        return Outcome(Status.MONITOR_FAILED if cleaned else Status.CLEANUP_FAILED,
                       exit_code=proc.returncode, peak_rss_kib=peak)
    if code:
        return Outcome(Status.INITIALIZATION_FAILED if code in {71, 78} else Status.WORKER_EXITED,
                       exit_code=code, peak_rss_kib=peak)
    result = _validate(bytes(output), request, source, proc.pid)
    return Outcome(result.status, result.response, code, peak)


def isolation_available() -> bool:
    """Only the reviewed macOS disposable-venv profile is available so far."""
    try:
        return (sys.platform == "darwin" and Path(SANDBOX).is_file()
                and Path(sys.prefix).resolve().is_relative_to(Path("/private/tmp"))
                and sys.prefix != sys.base_prefix)
    except OSError:
        return False


def _execute(request: dict, source: bytes, *, timeout: float) -> Outcome:
    if not isolation_available():
        return Outcome(Status.ISOLATION_UNAVAILABLE)
    try:
        temporary = tempfile.TemporaryDirectory(prefix="repopilot-parser-prototype-", dir="/private/tmp")
    except OSError:
        return Outcome(Status.INITIALIZATION_FAILED)
    try:
        result = _execute_staged(temporary, request, source, timeout)
        if result.status == Status.INITIALIZATION_FAILED and result.exit_code == 71:
            return Outcome(Status.ISOLATION_OR_LAUNCH_FAILED, exit_code=71, peak_rss_kib=result.peak_rss_kib)
        return result
    except OSError:
        return Outcome(Status.CLEANUP_FAILED)


def _execute_staged(temporary, request: dict, source: bytes, timeout: float) -> Outcome:
    with temporary as temp:
        try:
            root = Path(temp)
            os.chmod(root, 0o700)
            work = root / "work"
            work.mkdir(mode=0o700)
            os.chmod(work, 0o700)
            child = _stage(work)
            argv = [SANDBOX, "-p", _profile(work), sys.executable, "-I", "-S", "-B", str(child)]
            env = {"PATH": "/usr/bin:/bin", "HOME": str(work), "TMPDIR": str(work),
                   "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
            proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, cwd=work, env=env,
                                    start_new_session=True, close_fds=True)
        except OSError:
            return Outcome(Status.INITIALIZATION_FAILED)
        return _supervise(proc, request, source, timeout)


def run(source: bytes, *, path: str, language: str, request_id: str,
        expected_sha256: str, max_lines: int = 120, timeout: float = 10) -> Outcome:
    """Run one bounded request with no retries; failures never return chunks."""
    try:
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 0 < timeout <= 30:
            raise ValueError("timeout")
        request = _request(source, path, language, request_id, max_lines, expected_sha256)
    except (ValueError, TypeError, UnicodeError):
        return Outcome(Status.INVALID_REQUEST)
    return _execute(request, source, timeout=float(timeout))
