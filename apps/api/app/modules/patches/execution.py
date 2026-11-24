"""Before/after contracts. The only installed executor always fails closed."""
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class Outcome(StrEnum):
    BASELINE_FAILED_PATCH_PASSED = "BASELINE_FAILED_PATCH_PASSED"
    BOTH_PASSED = "BOTH_PASSED"
    BOTH_FAILED = "BOTH_FAILED"
    BASELINE_PASSED_PATCH_FAILED = "BASELINE_PASSED_PATCH_FAILED"
    TEST_UNAVAILABLE = "TEST_UNAVAILABLE"
    EXECUTION_BLOCKED = "EXECUTION_BLOCKED"
    TIMEOUT = "TIMEOUT"
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"
    INCONCLUSIVE = "INCONCLUSIVE"
    RESOURCE_LIMIT = "RESOURCE_LIMIT"
    CANCELLED = "CANCELLED"
    CLEANUP_FAILURE = "CLEANUP_FAILURE"


@dataclass(frozen=True)
class TestResult:
    status: str  # passed, failed, timeout, unavailable, blocked, infrastructure_failure


class IsolatedExecutor(Protocol):
    """Future adapter must enforce OS isolation; this interface is not a sandbox."""

    def run(self, *, spec_id: str, workspace: object) -> TestResult: ...


class UnavailableExecutor:
    def run(self, *, spec_id: str, workspace: object) -> TestResult:
        return TestResult("unavailable")


def compare(baseline: TestResult, patched: TestResult) -> Outcome:
    states = {baseline.status, patched.status}
    for value, outcome in (("cleanup_failure", Outcome.CLEANUP_FAILURE), ("cancelled", Outcome.CANCELLED),
                           ("resource_limit", Outcome.RESOURCE_LIMIT),
                           ("blocked", Outcome.EXECUTION_BLOCKED), ("timeout", Outcome.TIMEOUT),
                           ("infrastructure_failure", Outcome.INFRASTRUCTURE_FAILURE),
                           ("unavailable", Outcome.TEST_UNAVAILABLE)):
        if value in states:
            return outcome
    return {("failed", "passed"): Outcome.BASELINE_FAILED_PATCH_PASSED,
            ("passed", "passed"): Outcome.BOTH_PASSED,
            ("failed", "failed"): Outcome.BOTH_FAILED,
            ("passed", "failed"): Outcome.BASELINE_PASSED_PATCH_FAILED}.get(
                (baseline.status, patched.status), Outcome.INCONCLUSIVE)


def execution_unavailable() -> dict:
    return {"status": "VALIDATION_UNAVAILABLE", "outcome": Outcome.TEST_UNAVAILABLE,
            "sandbox_used": False, "tests_run": [],
            "reason": "No reviewed isolated code-execution sandbox is configured."}
