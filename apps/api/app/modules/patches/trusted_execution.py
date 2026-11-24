"""Run only two immutable synthetic fixtures behind the reviewed Docker policy."""
from contextlib import contextmanager
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path

from app.modules.patches.execution import Outcome, TestResult, compare, execution_unavailable
from app.modules.patches.synthetic_docker import ADAPTER, POLICY, DockerDriver, SandboxFailure, container_run, verify_workspace
from app.modules.patches.synthetic_specs import IMAGE, TEST_SHA256, select_spec
from app.modules.patches.validation import PatchError
from app.modules.patches.workspace import workspace_pair

CONTROLS = ["network-none", "non-root", "read-only-root", "read-only-fixture", "bounded-tmpfs",
            "no-docker-socket", "capabilities-dropped", "no-new-privileges", "seccomp",
            "memory-limit", "process-limit", "cpu-limit", "wall-timeout", "clean-environment"]


def spec_digest(spec):
    data = asdict(spec)
    data["source"] = spec.source_sha256
    data["patch"] = spec.patch_sha256
    data["test_sha256"] = TEST_SHA256
    return sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _base(spec, context):
    return {"version": "p4-synthetic-result-v1", "fixture_id": spec.id, "spec_sha256": spec_digest(spec),
            "baseline_snapshot_id": context.snapshot_id, "baseline_commit": context.commit_sha,
            "baseline_source_sha256": spec.source_sha256, "patched_workspace_sha256": spec.patched_sha256,
            "patch_sha256": spec.patch_sha256, "test_sha256": TEST_SHA256, "adapter_version": ADAPTER,
            "sandbox_policy": POLICY, "sandbox_image": IMAGE}


@contextmanager
def _container_readable(*workspaces):
    """Parent remains 0700; only the two known public synthetic files become readable."""
    try:
        for workspace in workspaces:
            for root, dirs, files in os.walk(workspace):
                for name in dirs:
                    os.chmod(Path(root) / name, 0o555)
                for name in files:
                    os.chmod(Path(root) / name, 0o444)
            os.chmod(workspace, 0o555)
        yield
    finally:
        for workspace in workspaces:
            if workspace.exists():
                os.chmod(workspace, 0o700)
                for root, dirs, files in os.walk(workspace):
                    for name in dirs:
                        os.chmod(Path(root) / name, 0o700)
                    for name in files:
                        os.chmod(Path(root) / name, 0o600)


def _test_result(result, elapsed):
    if result.code == 0 and result.stdout == b"PASS\n" and result.stderr == b"":
        return {"status": "passed", "exit_code": 0, "duration_ms": elapsed, "diagnostic": "pass_marker"}
    if result.code == 1 and result.stdout == b"FAIL\n" and result.stderr == b"":
        return {"status": "failed", "exit_code": 1, "duration_ms": elapsed, "diagnostic": "assertion_failed"}
    raise SandboxFailure("unexpected_test_output")


def run_synthetic(repository, context, diff, settings, *, cancelled=None, driver_factory=None):
    """Never accepts caller-selected executables or source beyond the built-in fixtures."""
    if settings.app_env != "test" or not settings.patch_synthetic_execution_enabled:
        return execution_unavailable()
    try:
        spec, files, changed = select_spec(repository, context, diff)
    except PatchError:
        return {"status": "EXECUTION_BLOCKED", "outcome": Outcome.EXECUTION_BLOCKED,
                "sandbox_used": False, "test_executed": False, "tests_run": [], "reason": "fixture_not_allowlisted"}
    report = {**_base(spec, context), "status": "INCOMPLETE", "outcome": Outcome.INCONCLUSIVE,
              "sandbox_used": False, "test_executed": False, "tests_run": [],
              "baseline": None, "patched": None, "reason": None}
    driver = None
    workspace_root = None
    try:
        if cancelled and cancelled():
            raise SandboxFailure("cancelled")
        driver = (driver_factory or DockerDriver)()
        driver.inspect_image()
        with workspace_pair(files, changed) as (baseline, patched):
            workspace_root = baseline.parent
            with _container_readable(baseline, patched):
                verify_workspace(baseline, spec)
                verify_workspace(patched, spec)
                _, _, preflight_id = container_run(driver, spec, baseline, probe=True, cancelled=cancelled)
                report["sandbox_used"] = True
                baseline_result, baseline_ms, baseline_id = container_run(driver, spec, baseline, probe=False, cancelled=cancelled)
                report["baseline"] = _test_result(baseline_result, baseline_ms)
                report["test_executed"] = True
                report["tests_run"] = [spec.id]
                verify_workspace(baseline, spec)
                verify_workspace(patched, spec)
                patched_result, patched_ms, patched_id = container_run(driver, spec, patched, probe=False, cancelled=cancelled)
                report["patched"] = _test_result(patched_result, patched_ms)
                verify_workspace(baseline, spec)
                verify_workspace(patched, spec)
                report["outcome"] = compare(TestResult(report["baseline"]["status"]),
                                            TestResult(report["patched"]["status"]))
                report["sandbox"] = {"preflight_container_id": preflight_id, "baseline_container_id": baseline_id,
                                     "patched_container_id": patched_id, "controls": CONTROLS, "cleanup": "confirmed"}
                report["status"] = "COMPLETED"
    except SandboxFailure as exc:
        failures = {"cancelled": Outcome.CANCELLED, "timeout": Outcome.TIMEOUT,
                    "resource_limit": Outcome.RESOURCE_LIMIT, "cleanup_failed": Outcome.CLEANUP_FAILURE,
                    "cleanup_unverified": Outcome.CLEANUP_FAILURE, "cleanup_ownership": Outcome.CLEANUP_FAILURE}
        if exc.code in {"docker_unavailable", "image_unavailable", "unsupported_host"} and not report["sandbox_used"]:
            report["status"], report["outcome"] = "VALIDATION_UNAVAILABLE", Outcome.TEST_UNAVAILABLE
        elif (exc.code.startswith(("preflight_", "container_policy", "container_security_policy", "container_mount_policy",
                                  "container_mount_options", "container_resource_policy", "container_command_policy",
                                  "container_identity_policy", "image_policy", "workspace_policy", "fixture_policy"))
              and not report["sandbox_used"]):
            report["status"], report["outcome"] = "EXECUTION_BLOCKED", Outcome.EXECUTION_BLOCKED
        else:
            report["outcome"] = failures.get(exc.code, Outcome.INFRASTRUCTURE_FAILURE)
            report["status"] = str(report["outcome"])
        report["reason"] = exc.code
    except (OSError, ValueError):
        if workspace_root is not None and workspace_root.exists():
            report["status"], report["outcome"], report["reason"] = (
                "CLEANUP_FAILURE", Outcome.CLEANUP_FAILURE, "workspace_cleanup_failure")
        else:
            report["status"], report["outcome"], report["reason"] = (
                "INFRASTRUCTURE_FAILURE", Outcome.INFRASTRUCTURE_FAILURE, "workspace_or_runtime_failure")
    finally:
        if driver is not None:
            try:
                driver.close()
            except OSError:
                report["status"], report["outcome"], report["reason"] = (
                    "CLEANUP_FAILURE", Outcome.CLEANUP_FAILURE, "driver_cleanup_failure")
    return report


def validate_completed_report(report, repository, context, diff):
    """Check saved JSON against the trusted fixture, patch and both exit markers."""
    try:
        spec, _, _ = select_spec(repository, context, diff)
        if not isinstance(report, dict) or any(report.get(k) != v for k, v in _base(spec, context).items()):
            raise ValueError()
        if set(report) != set(_base(spec, context)) | {"status", "outcome", "sandbox_used", "test_executed",
                                                        "tests_run", "baseline", "patched", "reason", "sandbox"}:
            raise ValueError()
        if (report.get("status") != "COMPLETED" or report.get("sandbox_used") is not True
                or report.get("test_executed") is not True or report.get("tests_run") != [spec.id]
                or report.get("reason") is not None):
            raise ValueError()
        sandbox = report["sandbox"]
        keys = {"preflight_container_id", "baseline_container_id", "patched_container_id", "controls", "cleanup"}
        if not isinstance(sandbox, dict) or set(sandbox) != keys or sandbox["controls"] != CONTROLS or sandbox["cleanup"] != "confirmed":
            raise ValueError()
        import re
        ids = [sandbox[key] for key in ("preflight_container_id", "baseline_container_id", "patched_container_id")]
        if len(set(ids)) != 3 or any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value) for value in ids):
            raise ValueError()
        for name in ("baseline", "patched"):
            item = report[name]
            if not isinstance(item, dict) or set(item) != {"status", "exit_code", "duration_ms", "diagnostic"}:
                raise ValueError()
            if (item["status"], item["exit_code"], item["diagnostic"]) not in {
                    ("passed", 0, "pass_marker"), ("failed", 1, "assertion_failed")}:
                raise ValueError()
            if type(item["duration_ms"]) is not int or not 0 <= item["duration_ms"] <= spec.timeout_seconds * 1000:
                raise ValueError()
        outcome = compare(TestResult(report["baseline"]["status"]), TestResult(report["patched"]["status"]))
        if report.get("outcome") != outcome:
            raise ValueError()
    except (PatchError, KeyError, TypeError, ValueError):
        raise PatchError("invalid_test_result") from None


def validate_incomplete_report(report, repository, context, diff):
    try:
        spec, _, _ = select_spec(repository, context, diff)
        if not isinstance(report, dict) or any(report.get(k) != v for k, v in _base(spec, context).items()):
            raise ValueError()
        allowed = set(_base(spec, context)) | {"status", "outcome", "sandbox_used", "test_executed",
                                               "tests_run", "baseline", "patched", "reason", "sandbox"}
        if not set(report) <= allowed:
            raise ValueError()
        if (report.get("status") not in {"TIMEOUT", "RESOURCE_LIMIT", "CANCELLED", "CLEANUP_FAILURE", "INFRASTRUCTURE_FAILURE"}
                or report.get("outcome") != report.get("status") or type(report.get("sandbox_used")) is not bool
                or type(report.get("test_executed")) is not bool
                or report.get("tests_run") not in ([], [spec.id])
                or report.get("test_executed") != bool(report.get("tests_run"))
                or (report.get("test_executed") and not report.get("sandbox_used"))
                or (not report.get("test_executed") and report.get("baseline") is not None)
                or not isinstance(report.get("reason"), str) or len(report["reason"]) > 80):
            raise ValueError()
        if report.get("test_executed"):
            item = report.get("baseline")
            if (not isinstance(item, dict) or set(item) != {"status", "exit_code", "duration_ms", "diagnostic"}
                    or (item["status"], item["exit_code"], item["diagnostic"]) not in {
                        ("passed", 0, "pass_marker"), ("failed", 1, "assertion_failed")}
                    or type(item["duration_ms"]) is not int or not 0 <= item["duration_ms"] <= spec.timeout_seconds * 1000):
                raise ValueError()
    except (PatchError, KeyError, TypeError, ValueError):
        raise PatchError("invalid_test_result") from None
