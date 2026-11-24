"""Lease-fenced patch worker. No transaction spans provider or remote calls."""
from dataclasses import asdict
from datetime import timedelta
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from billiard.exceptions import SoftTimeLimitExceeded
from cryptography.fernet import InvalidToken
from fastapi import HTTPException
from pydantic import SecretStr, ValidationError
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.domain.models import AuthSession, CodeSnapshot, InvestigationJob, PatchOutbox, PatchProposal, Repository, User, now
from app.infra.database import get_session_factory
from app.modules.auth.session import Principal, cipher, utc
from app.modules.github.client import GitHubFailure, get_github_client
from app.modules.github.issue_context import IssueData, authorize
from app.modules.ingestion.code_selection import contains_sensitive_source
from app.modules.investigation.report_model import sanitize_issue_text
from app.modules.investigation.report_routes import lock_report_read_access, parent_and_snapshot
from app.modules.patches.context import assemble_context
from app.modules.patches.execution import execution_unavailable
from app.modules.patches.generation import ProviderLimits, generate_candidate
from app.modules.patches.service import get_candidate_provider, inventory, patch_limits, static_validation_record, verify_saved
from app.modules.patches.trusted_execution import run_synthetic
from app.modules.patches.validation import PatchError


def process_patch(proposal_id: str, factory=None, github=None, provider=None):
    factory = factory or get_session_factory()
    github = github or get_github_client()
    lease = str(uuid4())

    def terminal(task, db, state, code=None):
        task.status, task.error_code, task.updated_at = state, code, now()
        task.lease_token = task.lease_expires_at = None
        outbox = db.get(PatchOutbox, task.id)
        if outbox:
            outbox.status = "processed"

    with factory.begin() as db:
        task = db.scalar(select(PatchProposal).where(PatchProposal.id == proposal_id).with_for_update())
        if not task or task.status not in {"queued", "generating", "validation_pending", "validating"}:
            return
        if task.status in {"generating", "validating"} and task.lease_expires_at and utc(task.lease_expires_at) > now():
            return
        if not get_settings().patch_proposals_enabled:
            terminal(task, db, "failed", "patch_disabled")
            return
        # This check is independent of the HTTP route, so replayed or injected
        # Celery deliveries cannot invoke a provider before exact-request approval.
        parent = db.get(InvestigationJob, task.investigation_id)
        snapshot = db.get(CodeSnapshot, task.snapshot_id)
        if (not parent or not snapshot or parent.snapshot_id != snapshot.id
                or snapshot.repository_id != task.repository_id or snapshot.tenant_id != task.tenant_id
                or parent.issue_origin_repository_id is not None or snapshot.inventory_coverage == "PARTIAL_INVENTORY"):
            terminal(task, db, "failed", "upstream_inference_approval_required")
            return
        if task.attempts >= 3:
            terminal(task, db, "failed", "attempts_exhausted")
            return
        session = db.scalar(select(AuthSession).where(AuthSession.id_hash == task.session_hash).with_for_update())
        user, repo = db.get(User, task.user_id), db.get(Repository, task.repository_id)
        if (not session or session.revoked_at is not None or utc(session.expires_at) <= now()
                or session.tenant_id != task.tenant_id or session.user_id != task.user_id or not user or not repo):
            terminal(task, db, "failed", "authorization_revoked")
            return
        try:
            token = cipher().decrypt(session.github_token_ciphertext.encode()).decode()
        except (InvalidToken, UnicodeError, ValueError):
            terminal(task, db, "failed", "invalid_session")
            return
        identity = Principal(user.id, task.tenant_id, user.github_user_id, token, session.id_hash)
        repo_id, repo_name, parent_id = task.repository_id, repo.full_name, task.investigation_id
        mode = "validate" if task.status in {"validation_pending", "validating"} else "generate"
        task.status = "validating" if mode == "validate" else "generating"
        task.attempts += 1
        task.lease_token, task.lease_expires_at, task.updated_at = (
            lease, now() + timedelta(seconds=get_settings().patch_worker_lease_seconds), now())

    def fail(state, code):
        with factory.begin() as db:
            task = db.scalar(select(PatchProposal).where(PatchProposal.id == proposal_id).with_for_update())
            if (task and task.lease_token == lease and task.status in {"generating", "validating"}
                    and task.lease_expires_at and utc(task.lease_expires_at) > now()):
                terminal(task, db, state, code)

    def current_parent_snapshot(db):
        try:
            parent, snapshot = parent_and_snapshot(db, repo_id, parent_id, identity, repo_name, lock_snapshot=True)
            if parent.issue_origin_repository_id is not None or snapshot.inventory_coverage == "PARTIAL_INVENTORY":
                raise PatchError("upstream_inference_approval_required")
            return parent, snapshot
        except HTTPException as exc:
            if exc.status_code == 409:
                raise PatchError("issue_or_snapshot_changed") from None
            raise

    def cancelled(expected_status):
        with factory() as db:
            current_task = db.get(PatchProposal, proposal_id)
            return (not current_task or current_task.status != expected_status
                    or current_task.lease_token != lease or not current_task.lease_expires_at
                    or utc(current_task.lease_expires_at) <= now())

    try:
        if mode == "generate":
            provider = provider or get_candidate_provider()
            if provider is None:
                raise PatchError("provider_unavailable")
            # The durable human approval ledger is not yet connected to this worker.
            # Reject the real network provider even on replay or injected delivery.
            from app.modules.patches.ollama_provider import OllamaPatchProvider
            if isinstance(provider, OllamaPatchProvider):
                raise PatchError("inference_approval_required")
        with factory() as db:
            name = authorize(repo_id, identity, db, github)
        if name != repo_name:
            raise PatchError("authorization_revoked")
        raw_issue = github.issue(identity.token, repo_name, _issue_number(factory, proposal_id))
        if not isinstance(raw_issue, dict) or "pull_request" in raw_issue:
            raise PatchError("issue_changed")
        try:
            issue = IssueData.model_validate(raw_issue)
        except ValidationError:
            raise PatchError("issue_changed") from None
        with factory.begin() as db:
            task = db.scalar(select(PatchProposal).where(PatchProposal.id == proposal_id).with_for_update())
            if not task or task.lease_token != lease or task.status not in {"generating", "validating"}:
                return
            lock_report_read_access(db, repo_id, identity, repo_name)
            parent, snapshot = current_parent_snapshot(db)
            if (issue.id != parent.issue_id or issue.number != parent.issue_number
                    or utc(issue.updated_at) != utc(parent.issue_updated_at)
                    or task.snapshot_id != snapshot.id or task.commit_sha != snapshot.commit_sha):
                raise PatchError("issue_or_snapshot_changed")
            context = assemble_context(db, parent, snapshot,
                title=sanitize_issue_text(issue.title, 1024), body=sanitize_issue_text(issue.body or "", 16000))
            if (context.repository_id != repo_id or context.tenant_id != identity.tenant_id
                    or context.repository_full_name != repo_name):
                raise PatchError("source_identity_changed")
            if mode == "validate":
                verify_saved(task, context, repo_name)
                diff_text = task.diff
        if mode == "generate":
            # Do not send known runtime credentials to an injected provider or persist them in its output.
            settings = get_settings()
            secrets = [getattr(settings, key).get_secret_value() for key in type(settings).model_fields
                       if isinstance(getattr(settings, key), SecretStr)]
            secrets += [token, identity.session_hash, make_url(settings.database_url).password,
                        unquote(urlsplit(settings.redis_url).password or "")]
            text_input = context.title + context.body + "".join(f.content.decode("utf-8") for f in context.files)
            if any(secret and secret in text_input for secret in secrets):
                raise PatchError("sensitive_input")
            provider_limits = ProviderLimits(settings.patch_provider_max_input_bytes,
                                             settings.patch_provider_max_output_bytes,
                                             settings.patch_provider_timeout_seconds)
            candidate = generate_candidate(provider, context, patch_limits(), provider_limits,
                                           cancelled=lambda: cancelled("generating"))
            if (contains_sensitive_source(candidate.diff) or contains_sensitive_source(candidate.rationale)
                    or any(secret and (secret in candidate.diff or secret in candidate.rationale) for secret in secrets)):
                raise PatchError("unsafe_output")
        else:
            validation_result = run_synthetic(repo_name, context, diff_text, get_settings(),
                                              cancelled=lambda: cancelled("validating"))
        with factory() as db:
            if authorize(repo_id, identity, db, github) != repo_name:
                raise PatchError("authorization_revoked")
        latest = github.issue(identity.token, repo_name, issue.number)
        if not isinstance(latest, dict) or "pull_request" in latest:
            raise PatchError("issue_changed")
        try:
            latest_issue = IssueData.model_validate(latest)
        except ValidationError:
            raise PatchError("issue_changed") from None
        if latest_issue != issue:
            raise PatchError("issue_changed")
        with factory.begin() as db:
            task = db.scalar(select(PatchProposal).where(PatchProposal.id == proposal_id).with_for_update())
            if (not task or task.lease_token != lease or not task.lease_expires_at
                    or utc(task.lease_expires_at) <= now() or task.status not in {"generating", "validating"}):
                return
            lock_report_read_access(db, repo_id, identity, repo_name)
            parent, snapshot = current_parent_snapshot(db)
            current = assemble_context(db, parent, snapshot, title=context.title, body=context.body)
            if current != context or task.snapshot_id != snapshot.id or task.commit_sha != snapshot.commit_sha:
                raise PatchError("source_identity_changed")
            if mode == "generate":
                task.provider, task.model, task.diff, task.rationale = (candidate.provider, candidate.model,
                                                                    candidate.diff, candidate.rationale)
                task.evidence = [asdict(e) for e in context.evidence if e.id in candidate.evidence_ids]
                task.changed_files = inventory(candidate.changed_files)
                task.static_result = static_validation_record(candidate.diff)
                task.test_result = execution_unavailable()
                verify_saved(task, current, repo_name)
                final_state = "static_validated"
            else:
                verify_saved(task, current, repo_name)
                task.test_result = validation_result
                final_state = ("tests_passed" if validation_result["patched"]["status"] == "passed"
                               else "tests_failed") if validation_result.get("status") == "COMPLETED" else "static_validated"
                task.status = final_state
                verify_saved(task, current, repo_name)
            terminal(task, db, final_state)
    except PatchError as exc:
        safe = {"inference_approval_required", "upstream_inference_approval_required", "provider_unavailable", "issue_changed", "issue_or_snapshot_changed", "sensitive_input",
                "unsafe_output", "source_identity_changed", "authorization_revoked", "invalid_model_output",
                "invalid_evidence_reference", "uncited_changed_file", "source_identity_or_size", "sensitive_source",
                "invalid_provider_configuration", "provider_credentials_missing", "invalid_provider_request",
                "provider_input_too_large", "local_model_not_configured", "local_model_invalid",
                "local_model_digest_not_configured", "local_model_not_found", "local_model_incompatible",
                "local_model_insufficient_evidence", "local_provider_invalid_endpoint",
                "local_provider_proxy_configured", "local_provider_unreachable", "local_provider_redirect",
                "local_provider_cloud_not_disabled", "local_provider_request_failed",
                "local_provider_invalid_response", "local_provider_cancelled", "local_provider_runtime_unavailable"}
        fail("stale" if str(exc) in {"issue_changed", "issue_or_snapshot_changed", "source_identity_changed"}
             else "failed", str(exc) if str(exc) in safe else "validation_failed")
    except (GitHubFailure, HTTPException):
        fail("failed", "authorization_or_github_unavailable")
    except (TimeoutError, SoftTimeLimitExceeded):
        fail("failed", "provider_timeout")
    except (TypeError, ValueError):
        fail("failed", "invalid_runtime_configuration")
    except SQLAlchemyError:
        # Leave the outbox pending; a later delivery can reclaim an expired lease.
        raise
    except Exception:
        # No raw provider/source/credential text may escape via worker logs.
        fail("failed", "worker_failed")


def _issue_number(factory, proposal_id):
    from app.domain.models import InvestigationJob
    with factory() as db:
        proposal = db.get(PatchProposal, proposal_id)
        parent = db.get(InvestigationJob, proposal.investigation_id) if proposal else None
        if not parent:
            raise PatchError("issue_changed")
        return parent.issue_number
