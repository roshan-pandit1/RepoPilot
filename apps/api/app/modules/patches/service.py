"""Patch-provider discovery and reproducible stored-proposal checks."""
from hashlib import sha256
from hmac import compare_digest
import re
from app.core.config import get_settings
from app.modules.patches.generation import CandidateProvider
from app.modules.patches.validation import Limits, PatchError, validate_patch


def get_candidate_provider() -> CandidateProvider | None:
    """Return only explicitly configured adapters; never fall back to a hosted service."""
    settings = get_settings()
    if settings.patch_generation_provider != "ollama" or not settings.patch_local_model_enabled:
        return None
    from app.modules.patches.ollama_provider import OllamaPatchProvider

    return OllamaPatchProvider(settings.patch_local_model_name, settings.patch_local_model_digest,
                               settings.patch_local_model_endpoint, settings.patch_provider_max_input_bytes,
                               settings.patch_provider_max_output_bytes, strategy=settings.patch_local_model_strategy)


def candidate_provider_status(provider) -> tuple[bool, str | None]:
    """Probe local metadata only; no issue text, source or model inference is sent."""
    if provider is None:
        return False, "Patch generation provider is unavailable."
    from app.modules.patches.ollama_provider import OllamaPatchProvider
    if isinstance(provider, OllamaPatchProvider):
        return False, "Local inference is unavailable until the human approval gate is integrated."
    probe = getattr(provider, "check_readiness", None)
    if not callable(probe):  # The existing explicitly injected synthetic test provider.
        return True, None
    try:
        probe()
    except PatchError as exc:
        reasons = {
            "local_model_not_configured": "Local patch model is not configured.",
            "local_model_digest_not_configured": "Local patch model digest is not configured.",
            "local_model_invalid": "Local patch model name is not permitted.",
            "local_model_not_found": "Local patch model was not found.",
            "local_model_incompatible": "Local patch model identity or format is incompatible.",
            "local_provider_unreachable": "Local patch provider is unreachable.",
            "local_provider_cloud_not_disabled": "Local provider cloud features are not verified as disabled.",
            "local_provider_invalid_endpoint": "Local provider endpoint is not permitted.",
            "local_provider_proxy_configured": "Local provider cannot run with a proxy configured.",
        }
        return False, reasons.get(str(exc), "Local patch provider is unavailable or not safely configured.")
    except TimeoutError:
        return False, "Local patch provider timed out."
    return True, None


def patch_limits() -> Limits:
    settings = get_settings()
    return Limits(files=settings.patch_max_files, changed_lines=settings.patch_max_changed_lines,
                  patch_bytes=settings.patch_max_bytes)


def inventory(changed):
    return [{"path": f.path, "file_id": f.file_id, "before_sha256": f.before_sha256,
             "after_sha256": f.after_sha256, "evidence_ids": list(f.evidence_ids)} for f in changed]


def static_validation_record(diff):
    """Bind the exact UTF-8 bytes at the point the static check accepts them."""
    if not isinstance(diff, str):
        raise PatchError("invalid_patch")
    try:
        digest = sha256(diff.encode("utf-8")).hexdigest()
    except UnicodeEncodeError:
        raise PatchError("invalid_patch") from None
    return {"status": "passed", "checks": ["snapshot", "source_hash", "evidence", "diff"],
            "patch_sha256": digest}


def verified_patch_digest(proposal):
    """Legacy records lack a bound digest and require an explicit static recheck."""
    record = proposal.static_result
    if not isinstance(record, dict) or "patch_sha256" not in record:
        return None
    digest = record["patch_sha256"]
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise PatchError("invalid_patch_digest")
    actual = static_validation_record(proposal.diff)["patch_sha256"]
    if not compare_digest(digest, actual):
        raise PatchError("invalid_patch_digest")
    return digest


def verify_saved(proposal, context, repository=None):
    if (proposal.snapshot_id != context.snapshot_id or proposal.commit_sha != context.commit_sha
            or proposal.investigation_id != context.investigation_id or not isinstance(proposal.evidence, list)):
        raise PatchError("snapshot_mismatch")
    legacy = {"status": "passed", "checks": ["snapshot", "source_hash", "evidence", "diff"]}
    if (not isinstance(proposal.static_result, dict)
            or {k: v for k, v in proposal.static_result.items() if k != "patch_sha256"} != legacy):
        raise PatchError("invalid_static_result")
    verified_patch_digest(proposal)
    report = proposal.test_result
    if not isinstance(report, dict):
        raise PatchError("invalid_test_result")
    if report.get("status") == "COMPLETED":
        from app.modules.patches.trusted_execution import validate_completed_report
        validate_completed_report(report, repository, context, proposal.diff)
        expected = "tests_passed" if report["patched"]["status"] == "passed" else "tests_failed"
        if proposal.status != expected:
            raise PatchError("invalid_test_result")
    elif report.get("status") in {"pending", "cancelled", "VALIDATION_UNAVAILABLE", "EXECUTION_BLOCKED"}:
        if (report.get("sandbox_used") is not False or report.get("tests_run") != []
                or report.get("test_executed") not in (None, False)
                or report.get("baseline") is not None or report.get("patched") is not None
                or (report.get("status") == "pending" and proposal.status not in {"validation_pending", "validating"})
                or (report.get("status") == "cancelled" and proposal.review_state != "rejected")
                or (report.get("status") == "EXECUTION_BLOCKED" and report.get("test_executed") is not False)):
            raise PatchError("invalid_test_result")
    elif report.get("status") in {"TIMEOUT", "RESOURCE_LIMIT", "CANCELLED", "CLEANUP_FAILURE", "INFRASTRUCTURE_FAILURE"}:
        from app.modules.patches.trusted_execution import validate_incomplete_report
        validate_incomplete_report(report, repository, context, proposal.diff)
        if proposal.status != "static_validated":
            raise PatchError("invalid_test_result")
    else:
        raise PatchError("invalid_test_result")
    expected_refs = {e.id: e for e in context.evidence}
    ids = [row.get("id") if isinstance(row, dict) else None for row in proposal.evidence]
    if (not ids or not all(isinstance(i, str) for i in ids)
            or len(set(ids)) != len(ids) or any(i not in expected_refs for i in ids)):
        raise PatchError("invalid_evidence_reference")
    for row in proposal.evidence:
        ref = expected_refs[row["id"]]
        if row != vars(ref):
            raise PatchError("invalid_evidence_reference")
    changed = validate_patch(proposal.diff, context.files, patch_limits())
    if (inventory(changed) != proposal.changed_files
            or any(not set(ids).intersection(f.evidence_ids) for f in changed)):
        raise PatchError("source_identity_changed")
    return changed
