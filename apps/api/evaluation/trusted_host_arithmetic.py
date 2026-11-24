"""One-off trusted synthetic arithmetic demo; this is NOT an execution sandbox.

Nothing in application dispatch imports this module. Only these exact locally authored
bytes may execute. Never use this runner for user content or a repository checkout.
"""
from hashlib import sha256
import os
from pathlib import Path
import selectors
import subprocess
import sys
import time

from app.modules.patches.execution import TestResult, compare
from app.modules.patches.native_specs import BAD, GOOD, PATCH, SNAPSHOT, SOURCE_PATH
from app.modules.patches.validation import ChangedFile, PatchError, SourceFile, validate_patch
from app.modules.patches.workspace import workspace_pair

TEST = b"assert add(2, 3) == 5\n"
SOURCE_HASH = "9445c47952abb8a7fc5d4a905d55b5be05771df1d69362ec597f9a50f7ede40d"
PATCHED_HASH = "b414e3e8a1cc84d091471727544c353f60db59fc2bea10ee562ece77410915be"
PATCH_HASH = "8d74d6e35955c7e3c7068fc709b09b4d59b2b4efcd6f17076d9b032e159150e7"
TEST_HASH = "a6494aeead1e3538048fb31199d96215cf5d03ec0dd9a6462973f73d2c81aaff"
RETAINED_PATCH = (Path.home() / "Library/Application Support/RepoPilot/toolchains/ollama-p71"
                  / "p8-20261115T060900Z-fe2ea1f6/attempt-1-accepted.diff")
LIMIT = 4096
TIMEOUT = 10


def _hash(data):
    return sha256(data).hexdigest()


def _verify_fixed_bytes():
    if (BAD != b"def add(a: int, b: int) -> int:\n    return a - b\n"
            or GOOD != b"def add(a: int, b: int) -> int:\n    return a + b\n"
            or TEST != b"assert add(2, 3) == 5\n"
            or _hash(BAD) != SOURCE_HASH or _hash(GOOD) != PATCHED_HASH
            or _hash(TEST) != TEST_HASH or _hash(PATCH.encode()) != PATCH_HASH):
        raise PatchError("trusted_fixture_mismatch")
    try:
        retained = RETAINED_PATCH.read_bytes()
    except FileNotFoundError:
        return "deterministic_fixture"
    if retained != PATCH.encode() or _hash(retained) != PATCH_HASH:
        raise PatchError("retained_patch_mismatch")
    return "retained_p8_patch"


def _execute(directory, source):
    path = directory / SOURCE_PATH
    raw = path.read_bytes()
    if raw != source or _hash(raw) != _hash(source) or source not in (BAD, GOOD):
        raise PatchError("trusted_source_mismatch")
    program = directory / "arithmetic_assertion.py"
    expected = source + TEST
    program.write_bytes(expected)
    if program.read_bytes() != expected:
        raise PatchError("trusted_test_mismatch")
    command = [sys.executable, "-I", "-S", "-B", str(program)]
    started = time.monotonic()
    proc = subprocess.Popen(command, cwd=directory, env={"PATH": "/usr/bin:/bin", "HOME": str(directory),
                                                        "LANG": "C"},
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            shell=False, close_fds=True)
    outputs = {"stdout": bytearray(), "stderr": bytearray()}
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(proc.stdout, selectors.EVENT_READ, "stdout")
            selector.register(proc.stderr, selectors.EVENT_READ, "stderr")
            while selector.get_map():
                remaining = TIMEOUT - (time.monotonic() - started)
                if remaining <= 0:
                    raise PatchError("trusted_test_timeout")
                for key, _ in selector.select(remaining):
                    chunk = os.read(key.fileobj.fileno(), LIMIT + 1)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    outputs[key.data].extend(chunk)
                    if sum(len(value) for value in outputs.values()) > LIMIT:
                        raise PatchError("trusted_test_output_limit")
            remaining = max(0, TIMEOUT - (time.monotonic() - started))
            try:
                code = proc.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                raise PatchError("trusted_test_timeout") from None
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        proc.stdout.close()
        proc.stderr.close()
    stderr = bytes(outputs["stderr"])
    if bytes(outputs["stdout"]) or not ((code == 0 and not stderr) or
            (code == 1 and stderr.endswith(b"AssertionError\n") and b"assert add(2, 3) == 5" in stderr)):
        raise PatchError("trusted_test_unexpected_exit")
    return {"status": "passed" if code == 0 else "failed", "exit_code": code,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "diagnostic": "pass" if code == 0 else "AssertionError: add(2, 3) != 5",
            "source_sha256": _hash(raw), "test_sha256": TEST_HASH,
            "invocation": [sys.executable, "-I", "-S", "-B", "<workspace>/arithmetic_assertion.py"]}


def run_trusted(*, control=False):
    """Run two exact fixtures on the host; callable only from explicit evaluation tests."""
    if type(control) is not bool:
        raise PatchError("trusted_fixture_mismatch")
    provenance = _verify_fixed_bytes()
    original = GOOD if control else BAD
    file = SourceFile(SOURCE_PATH, original, _hash(original), "synthetic", ("synthetic",))
    if control:
        # An unchanged copy is deliberately used: both authorized GOOD programs pass.
        changed = (ChangedFile(SOURCE_PATH, file.file_id, PATCHED_HASH, PATCHED_HASH, GOOD, file.evidence_ids),)
    else:
        changed = validate_patch(PATCH, (file,))
        if len(changed) != 1 or changed[0].content != GOOD or changed[0].after_sha256 != PATCHED_HASH:
            raise PatchError("trusted_patch_mismatch")
    with workspace_pair((file,), changed) as (baseline, patched):
        before = _execute(baseline, original)
        after = _execute(patched, GOOD)
        if (baseline / SOURCE_PATH).read_bytes() != original or (patched / SOURCE_PATH).read_bytes() != GOOD:
            raise PatchError("trusted_workspace_changed")
        root = baseline.parent
    if root.exists():
        raise PatchError("trusted_cleanup_failed")
    return {"status": "COMPLETED", "version": "p9-trusted-host-v1", "sandbox_used": False,
            "test_executed": True, "tests_run": ["trusted-add-assertion-v1"], "baseline": before,
            "patched": after, "outcome": compare(TestResult(before["status"]), TestResult(after["status"])),
            "snapshot_id": SNAPSHOT, "source_sha256": file.sha256, "patched_sha256": PATCHED_HASH,
            "patch_sha256": None if control else PATCH_HASH, "patch_provenance": "unchanged_control" if control else provenance,
            "cleanup": "confirmed", "reason": None}
