"""Offline-only tests: no VM, fixture execution or synthetic test results."""
import base64
from dataclasses import replace
from hashlib import sha256
import json
from types import SimpleNamespace

import pytest

from app.modules.patches.native_specs import (
    COMMIT, REPOSITORY, SNAPSHOT, SOURCE_PATH, SPECS, TEST_SOURCE,
)
from app.modules.patches.validation import PatchError, SourceFile
from app.modules.patches.vm_execution import (
    GUEST_COMMAND, POLICY, GuestPolicy, parse_untrusted_guest_response,
    prepare_vm_input, run_vm_synthetic, validate_requested_policy,
)


def fixture():
    spec = SPECS[0]
    file = SourceFile(SOURCE_PATH, spec.source, spec.source_sha256, "f", ("e",))
    return spec, SimpleNamespace(commit_sha=COMMIT, snapshot_id=SNAPSHOT, files=(file,))


def test_request_contains_only_pinned_source_test_and_fixed_command():
    spec, context = fixture()
    request = json.loads(prepare_vm_input(REPOSITORY, context, spec.patch))
    assert base64.b64decode(request["baseline_b64"]) == spec.source
    assert sha256(base64.b64decode(request["patched_b64"])).hexdigest() == spec.patched_sha256
    assert base64.b64decode(request["test_b64"]) == TEST_SOURCE
    assert request["patch_sha256"] == spec.patch_sha256
    assert request["command"] == list(GUEST_COMMAND)
    assert len(request["nonce"]) == 64


@pytest.mark.parametrize("change", ["repository", "source", "patch", "snapshot"])
def test_unapproved_source_identity_is_rejected(change):
    spec, context = fixture()
    repository, diff = REPOSITORY, spec.patch
    if change == "repository":
        repository = "unknown/repository"
    elif change == "source":
        context.files = (SourceFile(SOURCE_PATH, b"unexpected", spec.source_sha256, "f", ("e",)),)
    elif change == "patch":
        diff += "unexpected"
    else:
        context.snapshot_id = "wrong"
    with pytest.raises(PatchError):
        prepare_vm_input(repository, context, diff)


@pytest.mark.parametrize("policy", [
    replace(POLICY, networks=("nat",)), replace(POLICY, host_shares=("/Users",)),
    replace(POLICY, host_sockets=("/var/run/docker.sock",)),
    replace(POLICY, memory_bytes=3 * 1024**3), replace(POLICY, cpu_count=0),
    replace(POLICY, memory_bytes=float(POLICY.memory_bytes)),
    replace(POLICY, timeout_seconds=100), replace(POLICY, max_output_bytes=10000),
])
def test_requested_policy_rejects_unsafe_configuration(policy: GuestPolicy):
    with pytest.raises(PatchError, match="vm_policy_rejected"):
        validate_requested_policy(policy)


def test_framing_does_not_establish_a_trusted_vm_result():
    spec, context = fixture()
    request = prepare_vm_input(REPOSITORY, context, spec.patch)
    payload = json.loads(request)
    response = {"version": payload["version"], "nonce": payload["nonce"],
                "request_sha256": sha256(request).hexdigest(), "baseline": "failed", "patched": "passed"}
    encoded = json.dumps(response).encode()
    assert parse_untrusted_guest_response(encoded, request) == ("failed", "passed")
    for raw in (b"{}", encoded + b"x", b"x" * 4097,
                json.dumps({**response, "nonce": "0" * 64}).encode(),
                json.dumps({**response, "request_sha256": "0" * 64}).encode(),
                json.dumps({**response, "patched": "unknown"}).encode(),
                b'{"version":1,"version":2}'):
        with pytest.raises(PatchError, match="vm_invalid_response"):
            parse_untrusted_guest_response(raw, request)


def test_execution_is_unavailable_and_does_not_accept_unregistered_sources():
    spec, context = fixture()
    settings = SimpleNamespace(app_env="test", patch_synthetic_execution_enabled=True)
    result = run_vm_synthetic(REPOSITORY, context, spec.patch, settings)
    assert result["status"] == "VALIDATION_UNAVAILABLE"
    assert result["test_executed"] is False and result["sandbox_used"] is False
    assert run_vm_synthetic("external/repo", context, spec.patch, settings)["status"] == "EXECUTION_BLOCKED"
    assert run_vm_synthetic(REPOSITORY, context, spec.patch, settings, cancelled=lambda: True)["status"] == "CANCELLED"
    settings.app_env = "production"
    assert run_vm_synthetic(REPOSITORY, context, spec.patch, settings)["status"] == "VALIDATION_UNAVAILABLE"
