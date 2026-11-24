"""Local-only TypeScript parse supervision; this is not a hardened sandbox."""
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
from time import monotonic

from app.modules.ingestion.supervised_parser import _rss_kib
from app.modules.patches.validation import safe_path

MAX_SOURCE = 100_000
MAX_OUTPUT = 32768
TIMEOUT = 10.0
MAX_RSS_KIB = 512 * 1024
RUNNER = Path(__file__).with_name("typescript_runner.cjs")


class TypeScriptAnalysisUnavailable(ValueError):
    """Analysis failed safely; no findings may be published for this file."""


def runner_digest():
    try:
        if RUNNER.is_symlink() or not RUNNER.is_file() or RUNNER.stat().st_size > 65536:
            return "unavailable"
        return sha256(RUNNER.read_bytes()).hexdigest()
    except OSError:
        return "unavailable"


def _copy_checked(source, target, digest, *, executable=False):
    source = Path(source)
    if not source.is_absolute() or not re.fullmatch(r"[0-9a-f]{64}", digest or ""):
        raise TypeScriptAnalysisUnavailable("typescript_configuration_invalid")
    if source.is_symlink() or not source.is_file() or source.stat().st_size > 150_000_000:
        raise TypeScriptAnalysisUnavailable("typescript_configuration_invalid")
    shutil.copyfile(source, target)
    h = sha256()
    with target.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            h.update(block)
    if h.hexdigest() != digest:
        raise TypeScriptAnalysisUnavailable("typescript_runtime_mismatch")
    target.chmod(0o700 if executable else 0o600)


def _profile(work):
    path = json.dumps(str(work.resolve()))
    executable = json.dumps(str((work / "node").resolve()))
    return (f'(version 1)(allow default)(deny network*)(deny process-fork)(deny mach-lookup)'
            f'(deny process-exec (require-not (literal {executable})))'
            f'(deny file-read* (subpath "/Users") (subpath "/Volumes") (subpath "/private/var/folders"))'
            f'(deny file-read-data (require-all (subpath "/private/tmp") (require-not (subpath {path}))))'
            f'(deny file-write* (require-not (literal "/dev/null")))')


def _supervise(proc, wire):
    output = bytearray()
    deadline = monotonic() + TIMEOUT
    try:
        with selectors.DefaultSelector() as selector:
            os.set_blocking(proc.stdin.fileno(), False)
            os.set_blocking(proc.stdout.fileno(), False)
            selector.register(proc.stdin, selectors.EVENT_WRITE)
            selector.register(proc.stdout, selectors.EVENT_READ)
            sent = 0
            while selector.get_map():
                if monotonic() >= deadline:
                    raise TypeScriptAnalysisUnavailable("typescript_timeout")
                if proc.poll() is None:
                    rss = _rss_kib(proc.pid)
                    if rss is None or rss > MAX_RSS_KIB:
                        raise TypeScriptAnalysisUnavailable("typescript_resource_limit")
                for key, _ in selector.select(0.05):
                    if key.fileobj is proc.stdin:
                        try:
                            sent += os.write(proc.stdin.fileno(), wire[sent:])
                        except BrokenPipeError:
                            sent = len(wire)
                        if sent == len(wire):
                            selector.unregister(proc.stdin)
                            proc.stdin.close()
                    else:
                        chunk = os.read(proc.stdout.fileno(), min(65536, MAX_OUTPUT + 1 - len(output)))
                        if not chunk:
                            selector.unregister(proc.stdout)
                            proc.stdout.close()
                        else:
                            output.extend(chunk)
                            if len(output) > MAX_OUTPUT:
                                raise TypeScriptAnalysisUnavailable("typescript_output_limit")
        if proc.wait(timeout=max(.01, deadline - monotonic())) != 0:
            raise TypeScriptAnalysisUnavailable("typescript_runner_failed")
        return bytes(output)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        if isinstance(exc, TypeScriptAnalysisUnavailable):
            raise
        raise TypeScriptAnalysisUnavailable("typescript_runner_failed") from None
    finally:
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        try:
            proc.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            raise TypeScriptAnalysisUnavailable("typescript_cleanup_failed") from None
        for pipe in (proc.stdin, proc.stdout):
            if pipe and not pipe.closed:
                pipe.close()


def scan_typescript(path, source, added_lines, settings):
    if (sys.platform != "darwin" or not Path("/usr/bin/sandbox-exec").is_file()
            or not settings.pr_typescript_review_enabled or settings.app_env == "production"):
        raise TypeScriptAnalysisUnavailable("typescript_isolation_unavailable")
    if (not isinstance(path, str) or not safe_path(path) or not path.endswith((".ts", ".tsx"))
            or not isinstance(source, str) or not isinstance(added_lines, set)
            or any(type(line) is not int or line < 1 for line in added_lines)):
        raise TypeScriptAnalysisUnavailable("typescript_input_invalid")
    try:
        raw = source.encode("utf-8", errors="strict")
    except UnicodeError:
        raise TypeScriptAnalysisUnavailable("typescript_input_invalid") from None
    if len(raw) > MAX_SOURCE:
        raise TypeScriptAnalysisUnavailable("typescript_input_too_large")
    digest = sha256(raw).hexdigest()
    request = {"version": 1, "path": path, "source": source, "source_sha256": digest}
    wire = json.dumps(request, ensure_ascii=True, separators=(",", ":")).encode()
    if len(wire) > 220_000:
        raise TypeScriptAnalysisUnavailable("typescript_input_too_large")
    try:
        with tempfile.TemporaryDirectory(prefix="repopilot-ts-", dir="/private/tmp") as temp:
            work = Path(temp)
            work.chmod(0o700)
            _copy_checked(settings.pr_typescript_node_path, work / "node", settings.pr_typescript_node_sha256, executable=True)
            _copy_checked(settings.pr_typescript_compiler_path, work / "typescript.js", settings.pr_typescript_compiler_sha256)
            _copy_checked(str(RUNNER), work / "runner.cjs", runner_digest())
            proc = subprocess.Popen(["/usr/bin/sandbox-exec", "-p", _profile(work), str(work / "node"),
                "--max-old-space-size=128", "--no-addons", str(work / "runner.cjs")],
                cwd=work, env={"PATH": "/usr/bin:/bin", "HOME": str(work), "TMPDIR": str(work)},
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                close_fds=True, start_new_session=True)
            output = _supervise(proc, wire)
            pid = proc.pid
    except TypeScriptAnalysisUnavailable:
        raise
    except (OSError, ValueError):
        raise TypeScriptAnalysisUnavailable("typescript_runner_unavailable") from None
    seen = _validate_output(output, path, digest, source, pid)

    return [{"rule_id": "TS-EVAL-001", "category": "SECURITY", "severity": "LOW",
             "confidence": "MEDIUM", "path": path, "start_line": line, "end_line": line,
             "explanation": "A direct eval call receives a runtime value. If the value is a string, it can execute as code; the value's origin is not established by this check.",
             "recommendation": "Avoid eval where possible. Use a data parser or an explicit set of allowed operations."}
            for line in sorted(seen & added_lines)]


def _validate_output(output, path, digest, source, pid):
    try:
        result = json.loads(output)
        if (not isinstance(result, dict) or set(result) != {"version", "path", "source_sha256", "pid", "findings"}
                or type(result["version"]) is not int or result["version"] != 1 or result["path"] != path or result["source_sha256"] != digest
                or type(result["pid"]) is not int or result["pid"] != pid
                or not isinstance(result["findings"], list) or len(result["findings"]) > 500):
            raise ValueError
        seen = set()
        for finding in result["findings"]:
            if (not isinstance(finding, dict) or set(finding) != {"rule", "line"}
                    or finding["rule"] != "TS-EVAL-001" or type(finding["line"]) is not int
                    or not 1 <= finding["line"] <= len(source.splitlines()) or finding["line"] in seen
                    or not re.search(r"\beval\b", source.splitlines()[finding["line"] - 1])):
                raise ValueError
            seen.add(finding["line"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        raise TypeScriptAnalysisUnavailable("typescript_output_invalid") from None
    return seen
