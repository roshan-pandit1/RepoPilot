"""Offline checks for the trusted-only macOS fixture registry and result binding."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.modules.patches.native_specs import (
    COMMIT, CONTROLS, REPOSITORY, SNAPSHOT, SOURCE_PATH, SPECS, TEST_SHA256,
    select_native_spec, validate_native_completed,
)
from app.modules.patches.validation import PatchError, SourceFile


def setup_fixture(index=0):
    spec = SPECS[index]
    file = SourceFile(SOURCE_PATH, spec.source, spec.source_sha256, "file", ("evidence",))
    context = SimpleNamespace(commit_sha=COMMIT, snapshot_id=SNAPSHOT, files=(file,))
    return spec, context


def report(spec):
    return {"version": "p9-macos-result-v1", "fixture_id": spec.id, "snapshot_id": SNAPSHOT,
            "commit": COMMIT, "source_sha256": spec.source_sha256, "patch_sha256": spec.patch_sha256,
            "patched_sha256": spec.patched_sha256, "test_sha256": TEST_SHA256, "status": "COMPLETED",
            "outcome": "BASELINE_FAILED_PATCH_PASSED", "sandbox_used": True, "test_executed": True,
            "tests_run": [spec.id], "reason": None,
            "baseline": {"status": "failed", "exit_code": 1, "duration_ms": 12, "diagnostic": "assertion_failed"},
            "patched": {"status": "passed", "exit_code": 0, "duration_ms": 12, "diagnostic": "pass_marker"},
            "sandbox": {"preflight_id": "1" * 32, "baseline_id": "2" * 32, "patched_id": "3" * 32,
                        "controls": list(CONTROLS), "cleanup": "confirmed"}}


def test_exact_fixture_and_patch_are_selected():
    spec, context = setup_fixture()
    selected, files, changed = select_native_spec(REPOSITORY, context, spec.patch)
    assert selected == spec and len(files) == 2 and changed[0].after_sha256 == spec.patched_sha256


@pytest.mark.parametrize("mutation", ["repository", "commit", "snapshot", "source", "hash", "patch"])
def test_wrong_identity_or_patch_fails_closed(mutation):
    spec, context = setup_fixture()
    repo, diff = REPOSITORY, spec.patch
    if mutation == "repository":
        repo = "external/repository"
    elif mutation == "commit":
        context.commit_sha = "b" * 40
    elif mutation == "snapshot":
        context.snapshot_id = "different"
    elif mutation == "source":
        context.files = (SourceFile(SOURCE_PATH, b"wrong", spec.source_sha256, "file", ("evidence",)),)
    elif mutation == "hash":
        context.files = (SourceFile(SOURCE_PATH, spec.source, "0" * 64, "file", ("evidence",)),)
    else:
        diff += "x"
    with pytest.raises(PatchError):
        select_native_spec(repo, context, diff)


def test_report_is_bound_to_outcome_and_identities():
    spec, context = setup_fixture()
    valid = report(spec)
    validate_native_completed(valid, REPOSITORY, context, spec.patch)
    for field, value in (("outcome", "BOTH_PASSED"), ("sandbox_used", False),
                         ("patch_sha256", "0" * 64), ("test_executed", False)):
        invalid = deepcopy(valid)
        invalid[field] = value
        with pytest.raises(PatchError):
            validate_native_completed(invalid, REPOSITORY, context, spec.patch)
    invalid = deepcopy(valid)
    invalid["sandbox"]["patched_id"] = invalid["sandbox"]["baseline_id"]
    with pytest.raises(PatchError):
        validate_native_completed(invalid, REPOSITORY, context, spec.patch)


def test_passing_control_does_not_claim_reproducer_repair():
    spec, context = setup_fixture(1)
    value = report(spec)
    value["baseline"] = dict(value["patched"])
    value["outcome"] = "BOTH_PASSED"
    validate_native_completed(value, REPOSITORY, context, spec.patch)
    value["outcome"] = "BASELINE_FAILED_PATCH_PASSED"
    with pytest.raises(PatchError):
        validate_native_completed(value, REPOSITORY, context, spec.patch)
