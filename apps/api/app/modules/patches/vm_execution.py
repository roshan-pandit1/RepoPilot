"""Non-executing contract for a future isolated synthetic VM runner.

No VM driver is installed or called here.  Preparing input or parsing a guest
message never constitutes a security preflight or a completed execution report.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from hashlib import sha256
import json
import re
import secrets

from app.modules.patches.execution import Outcome, execution_unavailable
from app.modules.patches.native_specs import TEST_SHA256, TEST_SOURCE, select_native_spec
from app.modules.patches.validation import PatchError

VERSION = "p9.1-vm-request-v1"
MAX_REQUEST_BYTES = 32768
MAX_RESPONSE_BYTES = 4096
GUEST_COMMAND = ("/usr/bin/python3", "-I", "-S", "-B", "/fixture/test_arithmetic.py")


@dataclass(frozen=True)
class GuestPolicy:
    """Required requested settings, not evidence of effective VM configuration."""
    cpu_count: int = 2
    memory_bytes: int = 2 * 1024**3
    timeout_seconds: int = 10
    max_output_bytes: int = MAX_RESPONSE_BYTES
    networks: tuple[str, ...] = ()
    host_shares: tuple[str, ...] = ()
    host_sockets: tuple[str, ...] = ()


POLICY = GuestPolicy()


def validate_requested_policy(policy: GuestPolicy) -> None:
    """Reject changes to the fixed synthetic policy before provisioning exists."""
    if (type(policy) is not GuestPolicy or policy != POLICY
            or any(type(value) is not int for value in (
                policy.cpu_count, policy.memory_bytes, policy.timeout_seconds, policy.max_output_bytes))
            or any(type(value) is not tuple for value in (
                policy.networks, policy.host_shares, policy.host_sockets))):
        raise PatchError("vm_policy_rejected")


def prepare_vm_input(repository, context, diff: str) -> bytes:
    """Create a bounded, request-bound payload only from the immutable registry.

    File contents are included as inert base64 data.  Guest paths and the command
    are fixed here, and may not be chosen by a caller or model output.
    """
    try:
        spec, files, changed = select_native_spec(repository, context, diff)
        validate_requested_policy(POLICY)
        if (len(files) != 2 or files[1].content != TEST_SOURCE
                or sha256(TEST_SOURCE).hexdigest() != TEST_SHA256 or len(changed) != 1):
            raise PatchError("synthetic_fixture_integrity")
        payload = {
            "version": VERSION,
            "nonce": secrets.token_hex(32),
            "fixture_id": spec.id,
            "snapshot_id": context.snapshot_id,
            "commit": context.commit_sha,
            "source_sha256": spec.source_sha256,
            "patched_sha256": spec.patched_sha256,
            "patch_sha256": spec.patch_sha256,
            "test_sha256": TEST_SHA256,
            "baseline_b64": base64.b64encode(spec.source).decode("ascii"),
            "patched_b64": base64.b64encode(changed[0].content).decode("ascii"),
            "test_b64": base64.b64encode(TEST_SOURCE).decode("ascii"),
            "command": list(GUEST_COMMAND),
            "timeout_seconds": spec.timeout_seconds,
            "output_bytes": spec.output_bytes,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")
        if len(encoded) > MAX_REQUEST_BYTES:
            raise PatchError("vm_request_too_large")
        return encoded
    except PatchError:
        raise
    except (AttributeError, TypeError, UnicodeError, ValueError):
        raise PatchError("vm_invalid_request") from None


def parse_untrusted_guest_response(raw: bytes, request: bytes) -> tuple[str, str]:
    """Check framing and request binding only; the result is *not* trusted evidence.

    A future driver must separately attest the running guest, effective policy,
    transfer, cleanup and execution. This function cannot create a proposal result.
    """
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    try:
        if (type(raw) is not bytes or not 0 < len(raw) <= MAX_RESPONSE_BYTES
                or type(request) is not bytes or not 0 < len(request) <= MAX_REQUEST_BYTES):
            raise ValueError
        sent = json.loads(request, object_pairs_hook=unique_pairs)
        received = json.loads(raw, object_pairs_hook=unique_pairs)
        if (not isinstance(sent, dict) or sent.get("version") != VERSION
                or not isinstance(sent.get("nonce"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", sent["nonce"])
                or not isinstance(received, dict)
                or set(received) != {"version", "nonce", "request_sha256", "baseline", "patched"}
                or received["version"] != VERSION or received["nonce"] != sent["nonce"]
                or received["request_sha256"] != sha256(request).hexdigest()
                or received["baseline"] not in ("passed", "failed")
                or received["patched"] not in ("passed", "failed")):
            raise ValueError
        return received["baseline"], received["patched"]
    except (UnicodeError, ValueError, TypeError, KeyError, RecursionError):
        raise PatchError("vm_invalid_response") from None


def run_vm_synthetic(repository, context, diff, settings, *, cancelled=None) -> dict:
    """Fail closed: no reviewed driver, guest image, preflight or VM is installed."""
    if settings.app_env != "test" or not settings.patch_synthetic_execution_enabled:
        return execution_unavailable()
    try:
        select_native_spec(repository, context, diff)
    except (PatchError, AttributeError, TypeError):
        return {"status": "EXECUTION_BLOCKED", "outcome": Outcome.EXECUTION_BLOCKED,
                "sandbox_used": False, "test_executed": False, "tests_run": [],
                "reason": "fixture_not_allowlisted"}
    if cancelled and cancelled():
        return {"status": "CANCELLED", "outcome": Outcome.CANCELLED,
                "sandbox_used": False, "test_executed": False, "tests_run": [],
                "reason": "cancelled"}
    return {"status": "VALIDATION_UNAVAILABLE", "outcome": Outcome.TEST_UNAVAILABLE,
            "sandbox_used": False, "test_executed": False, "tests_run": [],
            "reason": "vm_runtime_and_guest_not_verified"}
