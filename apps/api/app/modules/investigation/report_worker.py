"""Lease-fenced, mock-only report task; no DB transaction spans model execution."""
from dataclasses import asdict
from datetime import timedelta
from uuid import uuid4

from billiard.exceptions import SoftTimeLimitExceeded
from cryptography.fernet import InvalidToken
from fastapi import HTTPException
from pydantic import SecretStr, ValidationError
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from urllib.parse import unquote, urlsplit

from app.core.config import get_settings
from app.core.index_logging import index_event
from app.domain.models import (AuthSession, CodeSnapshot, Installation, InvestigationJob, InvestigationReport,
    InvestigationReportJob, InvestigationReportOutbox, Membership, Repository, User, now)
from app.infra.database import get_session_factory
from app.modules.auth.session import Principal, cipher, utc
from app.modules.github.client import GitHubFailure, HttpGitHubClient, get_github_client
from app.modules.github.enrollment import visible_github_repositories
from app.modules.github.guards import installation_guard, repository_guard
from app.modules.github.issue_context import IssueData, build_context
from app.modules.github.issue_context_client import IssueContextClient
from app.modules.investigation.report_model import (ModelError, ModelTimeout, ModelUnavailable, build_package, execute_model,
                                                    get_investigation_model)
from app.modules.investigation.reporting import evidence_inputs, render_report_payload


class ReportTransientError(Exception):
    """Only a sanitized error code may leave the worker."""


def process_report(job_id: str, factory=None, github=None, model=None):
    factory = factory or get_session_factory()
    github = github or get_github_client()
    model = model or get_investigation_model()
    lease = str(uuid4())

    def terminal(db, task, state, code):
        task.status, task.error_code, task.updated_at = state, code, now()
        task.completed_at = None if state == 'queued' else now()
        task.lease_token, task.lease_expires_at = None, None
        if state != 'queued':
            outbox = db.get(InvestigationReportOutbox, task.id)
            if outbox:
                outbox.status = 'processed'

    with factory.begin() as db:
        task = db.scalar(select(InvestigationReportJob).where(InvestigationReportJob.id == job_id).with_for_update())
        if not task or task.status not in ('queued', 'running'):
            return
        if task.status == 'running' and task.lease_expires_at and utc(task.lease_expires_at) > now():
            return
        if task.attempts >= 5:
            terminal(db, task, 'failed', 'attempts_exhausted')
            return
        session = db.scalar(select(AuthSession).where(AuthSession.id_hash == task.session_hash).with_for_update())
        if (not session or session.revoked_at is not None or utc(session.expires_at) <= now()
                or session.user_id != task.user_id or session.tenant_id != task.tenant_id
                or not db.get(Membership, (task.tenant_id, task.user_id))):
            terminal(db, task, 'cancelled', 'session_unavailable')
            return
        user = db.get(User, task.user_id)
        repo = db.get(Repository, task.repository_id)
        installation = db.get(Installation, repo.installation_id) if repo else None
        parent = db.get(InvestigationJob, task.investigation_id)
        snapshot = db.get(CodeSnapshot, task.snapshot_id)
        if (not user or not repo or not repo.enabled or repo.tenant_id != task.tenant_id
                or not installation or not installation.active or installation.tenant_id != task.tenant_id
                or not parent or parent.user_id != task.user_id or parent.tenant_id != task.tenant_id
                or parent.repository_id != repo.id or parent.status != 'completed' or parent.operation != 'code_evidence'
                or parent.snapshot_id != task.snapshot_id or parent.source_repository_name != repo.full_name
                or not snapshot or not snapshot.published or snapshot.repository_id != repo.id
                or snapshot.tenant_id != task.tenant_id or snapshot.commit_sha != parent.snapshot_commit_sha):
            terminal(db, task, 'cancelled', 'evidence_unavailable')
            return
        try:
            token = cipher().decrypt(session.github_token_ciphertext.encode()).decode()
        except (InvalidToken, UnicodeError, ValueError):
            terminal(db, task, 'failed', 'invalid_session')
            return
        identity = Principal(user.id, task.tenant_id, user.github_user_id, token, session.id_hash)
        repo_id, repo_name, installation_id = repo.id, repo.full_name, installation.id
        parent_id, snapshot_id, commit = parent.id, snapshot.id, snapshot.commit_sha
        issue_id, issue_number, updated = parent.issue_id, parent.issue_number, utc(parent.issue_updated_at)
        task.attempts += 1
        task.status, task.lease_token = 'running', lease
        task.started_at = task.started_at or now()
        task.updated_at, task.lease_expires_at = now(), now() + timedelta(seconds=240)
    index_event('report_job_claimed', job_id=job_id, repository_id=repo_id, snapshot_id=snapshot_id)

    def fail(state, code):
        with factory.begin() as db:
            task = db.scalar(select(InvestigationReportJob).where(InvestigationReportJob.id == job_id).with_for_update())
            if task and task.status == 'running' and task.lease_token == lease:
                if state == 'queued' and task.attempts >= 5:
                    state, code = 'failed', 'attempts_exhausted'
                terminal(db, task, state, code)

    source = IssueContextClient(get_settings().issue_context_max_requests) if type(github) is HttpGitHubClient else github

    def check_remote():
        allowed = visible_github_repositories(identity, source, installation_id)
        return any(item['id'] == repo_id and item['full_name'] == repo_name for item in allowed)

    def check_local(db):
        session = db.get(AuthSession, identity.session_hash)
        repo = db.get(Repository, repo_id)
        installation = db.get(Installation, installation_id)
        parent = db.get(InvestigationJob, parent_id)
        snapshot = db.get(CodeSnapshot, snapshot_id)
        if (not session or session.revoked_at is not None or utc(session.expires_at) <= now()
                or session.user_id != identity.user_id or session.tenant_id != identity.tenant_id
                or not db.get(Membership, (identity.tenant_id, identity.user_id))
                or not installation or not installation.active or installation.tenant_id != identity.tenant_id
                or not repo or not repo.enabled or repo.tenant_id != identity.tenant_id
                or repo.installation_id != installation_id or repo.full_name != repo_name
                or not parent or parent.status != 'completed' or parent.operation != 'code_evidence'
                or parent.user_id != identity.user_id or parent.tenant_id != identity.tenant_id
                or parent.repository_id != repo_id or parent.snapshot_id != snapshot_id
                or parent.snapshot_commit_sha != commit or parent.source_repository_name != repo_name
                or parent.issue_id != issue_id or parent.issue_number != issue_number
                or utc(parent.issue_updated_at) != updated
                or not snapshot or not snapshot.published or snapshot.tenant_id != identity.tenant_id
                or snapshot.repository_id != repo_id or snapshot.commit_sha != commit):
            raise ModelError('authorization_revoked')
        return parent, snapshot

    try:
        if not check_remote():
            fail('cancelled', 'repository_unavailable')
            return
        raw = source.issue(identity.token, repo_name, issue_number)
        if not isinstance(raw, dict) or 'pull_request' in raw:
            raise ModelError('issue_unavailable')
        try:
            issue = IssueData.model_validate(raw)
        except ValidationError:
            raise ModelError('issue_unavailable') from None
        if issue.id != issue_id or issue.number != issue_number or utc(issue.updated_at) != updated:
            raise ModelError('issue_changed')
        comments = source.issue_comments(identity.token, repo_name, issue_number, get_settings().issue_context_comment_count)
        context = build_context(raw, comments, repo_id, repo_name, issue_number, get_settings())
        if not check_remote():
            fail('cancelled', 'repository_unavailable')
            return
        # This read-only transaction closes before any model work.
        with factory() as db:
            parent, snapshot = check_local(db)
            evidence = evidence_inputs(db, parent, snapshot)
            evidence_state = [(row['chunk_id'], row['path'], row['symbol'], row['start_line'], row['end_line'], row['citation'], row['fingerprint'])
                              for row in evidence]
            package = build_package(investigation_id=parent_id, repository_id=repo_id, issue_id=issue_id,
                issue_number=issue_number, context=context, snapshot_id=snapshot_id, commit_sha=commit,
                evidence=evidence)
        # Reject known runtime credentials wherever they appear in the projection.
        # This does not detect arbitrary, unknown secrets embedded in public content.
        def contains_identifier(value, secret):
            if isinstance(value, str):
                return secret in value
            if isinstance(value, dict):
                return any(contains_identifier(item, secret) for item in value.values())
            if isinstance(value, (list, tuple)):
                return any(contains_identifier(item, secret) for item in value)
            return False
        projected = asdict(package)
        settings = get_settings()
        runtime_secrets = [getattr(settings, name).get_secret_value()
                           for name in type(settings).model_fields
                           if isinstance(getattr(settings, name), SecretStr)]
        try:
            runtime_secrets.extend([make_url(settings.database_url).password,
                                    unquote(urlsplit(settings.redis_url).password or '')])
        except (TypeError, ValueError):
            raise ModelError('sensitive_input') from None
        if any(secret and contains_identifier(projected, secret)
               for secret in (identity.token, identity.session_hash, *runtime_secrets)):
            raise ModelError('sensitive_input')
        if not check_remote():
            fail('cancelled', 'repository_unavailable')
            return
        with factory() as db:
            parent, snapshot = check_local(db)
            current = evidence_inputs(db, parent, snapshot)
            current_state = [(row['chunk_id'], row['path'], row['symbol'], row['start_line'], row['end_line'],
                              row['citation'], row['fingerprint']) for row in current]
            if current_state != evidence_state:
                raise ModelError('evidence_unavailable')
        # Only a synchronous deterministic in-process mock can be selected by configuration.
        try:
            draft, usage = execute_model(model, package)
            if any(secret and contains_identifier(draft, secret)
                   for secret in (identity.token, identity.session_hash, *runtime_secrets)):
                raise ModelError('model_output_unsafe')
            # Revalidate citation rendering and total report size before any publication.
            render_report_payload(draft, parent=parent, evidence=evidence)
        except (ModelError, SoftTimeLimitExceeded):
            raise
        except Exception:
            raise ModelUnavailable('model_unavailable') from None
        latest_raw = source.issue(identity.token, repo_name, issue_number)
        if not isinstance(latest_raw, dict) or 'pull_request' in latest_raw:
            raise ModelError('issue_unavailable')
        try:
            latest = IssueData.model_validate(latest_raw)
        except ValidationError:
            raise ModelError('issue_unavailable') from None
        if latest.id != issue_id or latest.number != issue_number or utc(latest.updated_at) != updated:
            raise ModelError('issue_changed')
        if not check_remote():
            fail('cancelled', 'repository_unavailable')
            return
    except GitHubFailure as exc:
        if str(exc) == 'github_not_found':
            fail('cancelled', 'issue_unavailable')
            return
        fail('queued', 'github_verification_unavailable')
        raise ReportTransientError('github_verification_unavailable') from None
    except HTTPException as exc:
        if exc.status_code in (403, 404):
            fail('cancelled', 'repository_unavailable')
            return
        if exc.status_code == 502:
            fail('failed', 'issue_unavailable')
            return
        fail('queued', 'github_verification_unavailable')
        raise ReportTransientError('github_verification_unavailable') from None
    except ModelUnavailable:
        fail('queued', 'model_unavailable')
        raise ReportTransientError('model_unavailable') from None
    except ModelTimeout:
        fail('queued', 'model_timeout')
        raise ReportTransientError('model_timeout') from None
    except ModelError as exc:
        code = str(exc)
        if code in {'authorization_revoked', 'issue_unavailable', 'issue_changed', 'evidence_unavailable'}:
            fail('cancelled', code)
        else:
            fail('failed', code if code in {'model_output_invalid', 'model_output_too_large',
                'model_output_unsafe', 'model_evidence_invalid', 'model_not_enabled',
                'model_usage_invalid', 'model_input_invalid', 'context_limit', 'sensitive_input'} else 'model_failed')
        return
    except SoftTimeLimitExceeded:
        fail('queued', 'worker_timeout')
        raise ReportTransientError('worker_timeout') from None
    except OperationalError:
        fail('queued', 'database_temporarily_unavailable')
        raise ReportTransientError('database_temporarily_unavailable') from None

    with factory.begin() as db:
        task = db.scalar(select(InvestigationReportJob).where(InvestigationReportJob.id == job_id).with_for_update())
        if (not task or task.status != 'running' or task.lease_token != lease or not task.lease_expires_at
                or utc(task.lease_expires_at) <= now()):
            return
        session = db.scalar(select(AuthSession).where(AuthSession.id_hash == task.session_hash).with_for_update())
        ig = installation_guard(db, installation_id)
        installation = db.scalar(select(Installation).where(Installation.id == installation_id).with_for_update())
        rg = repository_guard(db, installation_id, repo_id)
        repo = db.scalar(select(Repository).where(Repository.id == repo_id).with_for_update())
        snapshot = db.scalar(select(CodeSnapshot).where(CodeSnapshot.id == snapshot_id,
            CodeSnapshot.repository_id == repo_id, CodeSnapshot.tenant_id == identity.tenant_id,
            CodeSnapshot.commit_sha == commit, CodeSnapshot.published.is_(True)).with_for_update())
        if (not session or session.revoked_at is not None or utc(session.expires_at) <= now()
                or session.user_id != identity.user_id or session.tenant_id != identity.tenant_id
                or not db.get(Membership, (identity.tenant_id, identity.user_id)) or ig.revoked or rg.revoked
                or not installation or not installation.active or installation.tenant_id != identity.tenant_id
                or not repo or not repo.enabled or repo.tenant_id != identity.tenant_id
                or repo.full_name != repo_name or repo.installation_id != installation_id or not snapshot):
            terminal(db, task, 'cancelled', 'authorization_revoked')
            return
        try:
            parent, snapshot = check_local(db)
            current = evidence_inputs(db, parent, snapshot)
            current_state = [(row['chunk_id'], row['path'], row['symbol'], row['start_line'], row['end_line'], row['citation'], row['fingerprint'])
                             for row in current]
            if current_state != evidence_state:
                raise ModelError('evidence_unavailable')
        except ModelError:
            terminal(db, task, 'cancelled', 'evidence_unavailable')
            return
        if db.scalar(select(InvestigationReport.id).where(InvestigationReport.investigation_id == parent_id).limit(1)):
            terminal(db, task, 'failed', 'report_exists')
            return
        db.add(InvestigationReport(id=str(uuid4()), report_job_id=job_id, investigation_id=parent_id,
            snapshot_id=snapshot_id, repository_id=repo_id, tenant_id=identity.tenant_id, commit_sha=commit,
            provider=model.provider, model=model.model, payload=draft, input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens, cost_microusd=usage.cost_microusd, input_truncated=package.truncated))
        terminal(db, task, 'completed', None)
    index_event('report_job_completed', job_id=job_id, repository_id=repo_id, snapshot_id=snapshot_id)
