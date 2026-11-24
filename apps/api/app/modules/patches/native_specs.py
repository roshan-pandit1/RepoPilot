"""Immutable original fixtures and result validation for the P9 macOS experiment.

This registry grants no authority to launch processes or to execute repository code.
"""
from dataclasses import dataclass
from hashlib import sha256
import re

from app.modules.patches.execution import TestResult, compare
from app.modules.patches.validation import PatchError, SourceFile, validate_patch

REPOSITORY = "repopilot-fixtures/patch-p8"
COMMIT = "a" * 40
SNAPSHOT = "22222222-2222-4222-8222-222222222222"
SOURCE_PATH = "src/arithmetic.py"
TEST_PATH = "test_arithmetic.py"
TEST_SOURCE = (b'import os, sys\nsys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))\n'
               b'from arithmetic import add\ntry:\n    assert add(2, 3) == 5\n'
               b'except AssertionError:\n    print("FAIL")\n    raise SystemExit(1)\nprint("PASS")\n')
TEST_SHA256 = "bb971465dc3e47b4c55cf5de0c1e3490f8980c7becfe1af37b3b761e970e8086"
BAD = b"def add(a: int, b: int) -> int:\n    return a - b\n"
GOOD = b"def add(a: int, b: int) -> int:\n    return a + b\n"
PATCH = ("--- a/src/arithmetic.py\n+++ b/src/arithmetic.py\n@@ -1,2 +1,2 @@\n"
         " def add(a: int, b: int) -> int:\n-    return a - b\n+    return a + b\n")
CONTROL_PATCH = ("--- a/src/arithmetic.py\n+++ b/src/arithmetic.py\n@@ -1,2 +1,2 @@\n"
                 " def add(a: int, b: int) -> int:\n-    return a + b\n+    return (a + b)\n")


@dataclass(frozen=True)
class NativeSpec:
    id: str
    source: bytes
    source_sha256: str
    patch: str
    patch_sha256: str
    patched_sha256: str
    timeout_seconds: int = 10
    output_bytes: int = 4096


SPECS = (
    NativeSpec("p9-add-reproducer-v1", BAD,
               "9445c47952abb8a7fc5d4a905d55b5be05771df1d69362ec597f9a50f7ede40d", PATCH,
               "8d74d6e35955c7e3c7068fc709b09b4d59b2b4efcd6f17076d9b032e159150e7",
               "b414e3e8a1cc84d091471727544c353f60db59fc2bea10ee562ece77410915be"),
    NativeSpec("p9-add-already-passes-v1", GOOD,
               "b414e3e8a1cc84d091471727544c353f60db59fc2bea10ee562ece77410915be", CONTROL_PATCH,
               "6c8a1aed8de593845a2c312253ad34d662a18ec43ea8fd8e66bcec1d40ac7c5f",
               "72010fc4f6886b0d84a4b2cd891f4febfe37b6a6b0b9901ce9b978b02f90c68a"),
)


def select_native_spec(repository, context, diff):
    """Accept only pinned synthetic bytes and exact patches; never caller commands."""
    if (repository != REPOSITORY or context.commit_sha != COMMIT or context.snapshot_id != SNAPSHOT
            or len(context.files) != 1 or context.files[0].path != SOURCE_PATH
            or sha256(TEST_SOURCE).hexdigest() != TEST_SHA256):
        raise PatchError("synthetic_fixture_not_allowed")
    file = context.files[0]
    for spec in SPECS:
        if (file.content == spec.source and file.sha256 == spec.source_sha256
                and sha256(file.content).hexdigest() == spec.source_sha256 and diff == spec.patch
                and sha256(diff.encode()).hexdigest() == spec.patch_sha256):
            changed = validate_patch(diff, context.files)
            if len(changed) != 1 or changed[0].after_sha256 != spec.patched_sha256:
                raise PatchError("synthetic_fixture_integrity")
            test = SourceFile(TEST_PATH, TEST_SOURCE, TEST_SHA256, "trusted-test", ("trusted-test",))
            return spec, (*context.files, test), changed
    raise PatchError("synthetic_fixture_not_allowed")


CONTROLS = ("network-denied", "file-access-restricted", "process-fork-denied", "exec-allowlisted",
            "environment-clean", "wall-timeout", "output-bounded", "workspace-private")


def validate_native_completed(report, repository, context, diff):
    """Fail closed on incomplete, inconsistent, or unbound native reports."""
    try:
        spec, _, _ = select_native_spec(repository, context, diff)
        required = {"version", "fixture_id", "snapshot_id", "commit", "source_sha256", "patch_sha256",
                    "patched_sha256", "test_sha256", "status", "outcome", "sandbox_used", "test_executed",
                    "tests_run", "baseline", "patched", "sandbox", "reason"}
        if not isinstance(report, dict) or set(report) != required:
            raise ValueError
        expected = {"version": "p9-macos-result-v1", "fixture_id": spec.id, "snapshot_id": SNAPSHOT,
                    "commit": COMMIT, "source_sha256": spec.source_sha256, "patch_sha256": spec.patch_sha256,
                    "patched_sha256": spec.patched_sha256, "test_sha256": TEST_SHA256, "status": "COMPLETED",
                    "sandbox_used": True, "test_executed": True, "tests_run": [spec.id], "reason": None}
        if (any(report[key] != value for key, value in expected.items())
                or report["sandbox_used"] is not True or report["test_executed"] is not True):
            raise ValueError
        sandbox = report["sandbox"]
        if (not isinstance(sandbox, dict) or set(sandbox) != {"preflight_id", "baseline_id", "patched_id", "controls", "cleanup"}
                or sandbox["controls"] != list(CONTROLS) or sandbox["cleanup"] != "confirmed"):
            raise ValueError
        ids = [sandbox[key] for key in ("preflight_id", "baseline_id", "patched_id")]
        if len(set(ids)) != 3 or any(not isinstance(v, str) or not re.fullmatch(r"[0-9a-f]{32}", v) for v in ids):
            raise ValueError
        for name in ("baseline", "patched"):
            item = report[name]
            if (not isinstance(item, dict) or set(item) != {"status", "exit_code", "duration_ms", "diagnostic"}
                    or type(item["exit_code"]) is not int
                    or (item["status"], item["exit_code"], item["diagnostic"]) not in {
                        ("passed", 0, "pass_marker"), ("failed", 1, "assertion_failed")}
                    or type(item["duration_ms"]) is not int or not 0 <= item["duration_ms"] <= 10000):
                raise ValueError
        if report["outcome"] != compare(TestResult(report["baseline"]["status"]), TestResult(report["patched"]["status"])):
            raise ValueError
    except (PatchError, KeyError, TypeError, ValueError):
        raise PatchError("invalid_test_result") from None
