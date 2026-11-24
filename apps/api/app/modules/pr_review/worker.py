"""Read-only pull-request review worker with outbox and lease fencing."""
from datetime import timedelta
from hashlib import sha256
import re
import json
from uuid import uuid4

from cryptography.fernet import InvalidToken
from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import get_settings
from app.domain.models import (AuthSession, PRReview, PRReviewFinding, PRReviewOutbox, Repository, User, now)
from app.infra.database import get_session_factory
from app.modules.auth.session import Principal, cipher, utc
from app.modules.github.client import GitHubFailure, get_github_client
from app.modules.github.issue_context import authorize_review as authorize
from app.modules.github.installation_token import invalidate_review_token, review_token
from app.modules.github.source_client import GitHubSourceClient
from app.modules.investigation.report_routes import lock_report_read_access
from app.modules.pr_review.core import active_policy_hash, PullClient, analyze_pull, review_identity


def process_pr_review(review_id, factory=None, github=None, pull_client=None, source_client=None):
    factory = factory or get_session_factory()
    github = github or get_github_client()
    pull_client = pull_client or PullClient(70)
    source_client = source_client or GitHubSourceClient(max_requests=160, max_seconds=120)
    lease = str(uuid4())

    def terminal(db, job, status, code=None):
        job.status, job.error_code, job.updated_at = status, code, now()
        job.lease_token = job.lease_expires_at = job.next_retry_at = None
        event = db.get(PRReviewOutbox, job.id)
        if event:
            event.status = "processed"

    with factory.begin() as db:
        job = db.scalar(select(PRReview).where(PRReview.id == review_id).with_for_update())
        if not job or job.status not in {"queued", "running"}:
            return
        if job.status == "running" and job.lease_expires_at and utc(job.lease_expires_at) > now():
            return
        # A duplicate message cannot bypass the persisted retry deadline.
        if job.status == "queued" and job.next_retry_at and utc(job.next_retry_at) > now():
            return
        # Preserve the prior transient backoff for jobs queued before migration 0021.
        if (job.status == "queued" and job.next_retry_at is None
                and job.error_code == "github_temporarily_unavailable"
                and utc(job.updated_at) + timedelta(seconds=min(120, 30 * 2 ** max(0, job.attempts - 1))) > now()):
            return
        if not get_settings().pr_reviews_enabled or job.policy_sha256 != active_policy_hash():
            terminal(db, job, "failed", "review_disabled_or_policy_changed")
            return
        if (type(job.github_pr_id) is not int or job.github_pr_id <= 0
                or not isinstance(job.base_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", job.base_sha)
                or not isinstance(job.head_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", job.head_sha)):
            terminal(db, job, "failed", "unverified_review_identity")
            return
        if job.attempts >= 3:
            terminal(db, job, "failed", "attempts_exhausted")
            return
        session = db.scalar(select(AuthSession).where(AuthSession.id_hash == job.session_hash).with_for_update())
        user, repo = db.get(User, job.user_id), db.get(Repository, job.repository_id)
        if (not session or session.revoked_at is not None or utc(session.expires_at) <= now()
                or session.user_id != job.user_id or session.tenant_id != job.tenant_id or not user or not repo
                or not repo.enabled or repo.tenant_id != job.tenant_id):
            terminal(db, job, "failed", "authorization_revoked")
            return
        try:
            token = cipher().decrypt(session.github_token_ciphertext.encode()).decode()
        except (InvalidToken, UnicodeError, ValueError):
            terminal(db, job, "failed", "invalid_session")
            return
        identity = Principal(user.id, job.tenant_id, user.github_user_id, token, session.id_hash)
        repo_id, repo_name, number, installation_id = repo.id, repo.full_name, job.number, repo.installation_id
        pinned = review_identity(job, repo_name)
        if type(pinned[3]) is not int or not pinned[4]:
            terminal(db, job, "failed", "unverified_review_identity")
            return
        job.status, job.lease_token = "running", lease
        job.next_retry_at = None
        job.lease_expires_at, job.updated_at, job.attempts = now() + timedelta(seconds=240), now(), job.attempts + 1

    try:
        with factory() as db:
            if authorize(repo_id, identity, db, github) != repo_name:
                raise GitHubFailure("authorization_revoked")
        source_token = review_token(identity, installation_id, repo_id)

        def authorize_source_read():
            # Reconcile current GitHub visibility and committed local revocations.
            # An already in-flight HTTP request cannot be recalled by this check.
            with factory() as db:
                if authorize(repo_id, identity, db, github) != repo_name:
                    raise GitHubFailure("authorization_revoked")

        metadata, files, findings, limitations = analyze_pull(
            source_client, pull_client, source_token, repo_id, repo_name, number,
            expected=pinned, authorize_access=authorize_source_read)
        with factory() as db:
            if authorize(repo_id, identity, db, github) != repo_name:
                raise GitHubFailure("authorization_revoked")
        with factory.begin() as db:
            job = db.scalar(select(PRReview).where(PRReview.id == review_id).with_for_update())
            if (not job or job.status != "running" or job.lease_token != lease or not job.lease_expires_at
                    or utc(job.lease_expires_at) <= now()
                    or review_identity(job, repo_name) != pinned):
                return
            lock_report_read_access(db, repo_id, identity, repo_name)
            if job.policy_sha256 != active_policy_hash() or not get_settings().pr_reviews_enabled:
                terminal(db, job, "failed", "review_disabled_or_policy_changed")
                return
            job.github_pr_id = metadata["id"]
            job.title, job.author, job.base_sha, job.head_sha = (metadata["title"], metadata["author"],
                                                                metadata["base_sha"], metadata["head_sha"])
            job.files, job.limitations = files, sorted(set(limitations + ["limited_rule_coverage"]))
            job.coverage = "partial"  # A single narrow rule is not comprehensive review coverage.
            seen = set()
            for item in findings:
                fingerprint = sha256(json.dumps([item["rule_id"], item["path"], item["start_line"],
                    item["end_line"], metadata["head_sha"], item["evidence"]["file_sha256"]], separators=(",", ":")).encode()).hexdigest()
                if fingerprint in seen:
                    continue
                seen.add(fingerprint)
                db.add(PRReviewFinding(id=str(uuid4()), review_id=job.id, repository_id=repo_id,
                    tenant_id=identity.tenant_id, fingerprint=fingerprint, **item))
            terminal(db, job, "completed")
    except (GitHubFailure, HTTPException, ValueError, TypeError, KeyError) as exc:
        safe_codes = {"github_rate_limited", "github_secondary_rate_limited",
                      "github_authentication_failed", "github_permission_denied",
                      "github_not_found", "github_temporarily_unavailable", "pull_request_changed",
                      "source_identity_mismatch", "github_blob_invalid", "authorization_revoked"}
        code = str(exc) if isinstance(exc, GitHubFailure) and str(exc) in safe_codes else "review_unavailable"
        if isinstance(exc, HTTPException) and exc.status_code in {401, 403, 404}:
            code = "authorization_revoked"
        if code == "authorization_revoked" or code in {
            "github_authentication_failed", "github_permission_denied", "github_not_found"
        }:
            try:
                invalidate_review_token(installation_id, repo_id)
            except GitHubFailure:
                pass  # The original access failure remains authoritative.
        with factory.begin() as db:
            job = db.scalar(select(PRReview).where(PRReview.id == review_id).with_for_update())
            if (job and job.status == "running" and job.lease_token == lease and job.lease_expires_at
                    and utc(job.lease_expires_at) > now()
                    and review_identity(job, repo_name) == pinned):
                retry_at = None
                if code == "github_temporarily_unavailable":
                    retry_at = now() + timedelta(seconds=min(120, 30 * 2 ** (job.attempts - 1)))
                elif (code in {"github_rate_limited", "github_secondary_rate_limited"}
                      and isinstance(exc, GitHubFailure) and exc.retry_at is not None):
                    retry_at = max(utc(exc.retry_at), now() + timedelta(seconds=60 * 2 ** (job.attempts - 1)))
                    if retry_at > now() + timedelta(hours=24):
                        retry_at = None
                if retry_at is not None and job.attempts < 3:
                    job.status, job.error_code, job.updated_at = "queued", code, now()
                    job.lease_token = job.lease_expires_at = None
                    job.next_retry_at = retry_at
                    event = db.get(PRReviewOutbox, job.id)
                    if event and event.status == "pending":
                        event.next_dispatch_at = retry_at
                    else:
                        terminal(db, job, "failed", "review_unavailable")
                else:
                    terminal(db, job, "failed", code)
