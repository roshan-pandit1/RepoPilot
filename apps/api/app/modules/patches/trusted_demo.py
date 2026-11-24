"""Validate and present retained trusted synthetic host evidence only."""
from hashlib import sha256
import json

from app.modules.patches.execution import TestResult, compare
from app.modules.patches.native_specs import BAD, GOOD, PATCH
from app.modules.patches.validation import PatchError

DEMONSTRATION_ID = "p9-trusted-arithmetic-host-v1"
TEST_ID = "trusted-add-assertion-v1"
SOURCE_SHA = "9445c47952abb8a7fc5d4a905d55b5be05771df1d69362ec597f9a50f7ede40d"
GOOD_SHA = "b414e3e8a1cc84d091471727544c353f60db59fc2bea10ee562ece77410915be"
PATCH_SHA = "8d74d6e35955c7e3c7068fc709b09b4d59b2b4efcd6f17076d9b032e159150e7"
TEST_SHA = "a6494aeead1e3538048fb31199d96215cf5d03ec0dd9a6462973f73d2c81aaff"


def validate_and_present(raw: bytes) -> dict:
    """Require the retained evidence bytes; return a non-production presentation object."""
    try:
        if type(raw) is not bytes or not raw or len(raw) > 16384:
            raise ValueError
        doc = json.loads(raw)
        if set(doc) != {"baseline_patch", "control"}:
            raise ValueError
        case = doc["baseline_patch"]
        control = doc["control"]
        if not isinstance(case, dict) or not isinstance(control, dict):
            raise ValueError
        _verify(case, SOURCE_SHA, GOOD_SHA, PATCH_SHA, "BASELINE_FAILED_PATCH_PASSED", "failed", "passed")
        _verify(control, GOOD_SHA, GOOD_SHA, None, "BOTH_PASSED", "passed", "passed")
        return {"type": "TRUSTED_SYNTHETIC_HOST_EXECUTION", "demonstration_id": DEMONSTRATION_ID,
                "test_specification_id": TEST_ID, "source_sha256": SOURCE_SHA, "patched_sha256": GOOD_SHA,
                "patch_sha256": PATCH_SHA, "evidence_sha256": sha256(raw).hexdigest(),
                "baseline": "FAILED", "patched": "PASSED", "outcome": "BASELINE_FAILED_PATCH_PASSED",
                "control_outcome": "BOTH_PASSED", "sandbox_used": False,
                "execution_environment": "trusted_local_host", "trusted_fixture_only": True,
                "production_validation": False,
                "limitation": "Host execution of fixed synthetic bytes; not isolated and not production validation."}
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        raise PatchError("invalid_trusted_synthetic_evidence") from None


def _verify(report, source_sha, patched_sha, patch_sha, outcome, baseline_status, patched_status):
    if (set(report) != {"status", "version", "sandbox_used", "test_executed", "tests_run", "baseline", "patched",
                        "outcome", "snapshot_id", "source_sha256", "patched_sha256", "patch_sha256",
                        "patch_provenance", "cleanup", "reason"}
            or report["status"] != "COMPLETED" or report["version"] != "p9-trusted-host-v1"
            or report["sandbox_used"] is not False or report["test_executed"] is not True
            or report["tests_run"] != [TEST_ID] or report["outcome"] != outcome
            or report["source_sha256"] != source_sha or report["patched_sha256"] != patched_sha
            or report["patch_sha256"] != patch_sha or report["cleanup"] != "confirmed" or report["reason"] is not None):
        raise ValueError
    phases = (report["baseline"], report["patched"])
    for item, status, exit_code, expected_source in zip(phases, (baseline_status, patched_status),
                                                        (1, 0) if outcome == "BASELINE_FAILED_PATCH_PASSED" else (0, 0),
                                                        (source_sha, patched_sha)):
        if (set(item) != {"status", "exit_code", "duration_ms", "diagnostic", "source_sha256", "test_sha256", "invocation"}
                or item["status"] != status or type(item["exit_code"]) is not int or item["exit_code"] != exit_code
                or type(item["duration_ms"]) is not int or not 0 <= item["duration_ms"] <= 10000
                or item["source_sha256"] != expected_source or item["test_sha256"] != TEST_SHA
                or item["invocation"][-3:] != ["-S", "-B", "<workspace>/arithmetic_assertion.py"]):
            raise ValueError
    if compare(TestResult(baseline_status), TestResult(patched_status)) != outcome:
        raise ValueError
    if source_sha == SOURCE_SHA and _sha(BAD) != SOURCE_SHA or _sha(GOOD) != GOOD_SHA or _sha(PATCH.encode()) != PATCH_SHA:
        raise ValueError


def _sha(value: bytes) -> str:
    return sha256(value).hexdigest()
