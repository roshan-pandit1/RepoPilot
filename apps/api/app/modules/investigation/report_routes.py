"""Explicit report requests and authorized read-only report access."""
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import (AuthSession, CodeSnapshot, Installation, InstallationGuard, InvestigationExperiment, InvestigationJob,
                               InvestigationProviderSelection, InvestigationRealReport, InvestigationReport, InvestigationReportJob, InvestigationReportOutbox,
                               Membership, Repository, RepositoryGuard, now)
from app.infra.database import get_db
from app.modules.auth.session import Principal, principal, require_csrf, utc
from app.modules.github.client import GitHubClient, get_github_client
from app.modules.github.guards import installation_guard, repository_guard
from app.modules.github.issue_context import authorize
from app.modules.investigation.report_model import ModelError
from app.modules.investigation.reporting import evidence_inputs, render_report_payload
from app.modules.investigation.reporting_config import real_provider_enabled
from app.modules.investigation.usage_ledger import experiment_is_eligible
from app.core.config import get_settings

router = APIRouter(prefix='/v1/repositories')


class EvidenceCitation(BaseModel):
    chunk_id: str
    snapshot_id: str
    commit_sha: str
    start_line: int
    end_line: int
    path: str
    symbol: str | None
    url: str


class HypothesisView(BaseModel):
    title: str
    explanation: str
    observations: list[str]
    missing_or_contradictory: list[str]
    evidence: list[EvidenceCitation]
    contradictory_evidence: list[EvidenceCitation]
    support_status: Literal['speculative', 'unsupported']
    uncertainty: Literal['high']


class ReportView(BaseModel):
    investigation_id: str
    repository_id: str
    issue_id: str
    issue_number: int
    snapshot_id: str
    commit_sha: str
    provider: Literal['mock', 'openai']
    model: Literal['deterministic-v1', 'gpt-5.6-terra']
    status: Literal['completed']
    disclaimer: str
    summary: str
    hypotheses: list[HypothesisView]
    missing_evidence: list[str]
    next_steps: list[str]
    warnings: list[str]
    input_truncated: bool
    snapshot_partial: bool
    input_tokens: int | None
    output_tokens: int | None
    cost_microusd: int | None
    created_at: datetime


class ReportEnvelope(BaseModel):
    report_job_id: str
    status: Literal['queued', 'running', 'completed', 'failed', 'cancelled']
    attempts: int
    error_code: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    report: ReportView | None


def parent_and_snapshot(db, repository_id, job_id, identity, name, *, lock_snapshot=False):
    parent = db.scalar(select(InvestigationJob).where(InvestigationJob.id == str(job_id),
        InvestigationJob.repository_id == repository_id, InvestigationJob.tenant_id == identity.tenant_id,
        InvestigationJob.user_id == identity.user_id))
    if not parent:
        raise HTTPException(404, 'Investigation not found')
    if parent.operation != 'code_evidence' or parent.status != 'completed':
        raise HTTPException(409, 'Completed evidence investigation required')
    stmt = select(CodeSnapshot).where(CodeSnapshot.id == parent.snapshot_id,
        CodeSnapshot.repository_id == repository_id, CodeSnapshot.tenant_id == identity.tenant_id,
        CodeSnapshot.commit_sha == parent.snapshot_commit_sha, CodeSnapshot.published.is_(True))
    snapshot = db.scalar(stmt.with_for_update() if lock_snapshot else stmt)
    if not snapshot or name != parent.source_repository_name:
        raise HTTPException(409, 'Snapshot is no longer available')
    return parent, snapshot


def lock_report_read_access(db, repository_id, identity, name):
    """Fence local revocation after the remote check without network calls under locks."""
    session = db.scalar(select(AuthSession).where(AuthSession.id_hash == identity.session_hash)
                        .with_for_update().execution_options(populate_existing=True))
    if (not session or session.revoked_at is not None or utc(session.expires_at) <= now()
            or session.tenant_id != identity.tenant_id or session.user_id != identity.user_id
            or not db.get(Membership, (identity.tenant_id, identity.user_id))):
        raise HTTPException(401, 'Authentication required')
    repo = db.scalar(select(Repository).where(Repository.id == repository_id,
                     Repository.tenant_id == identity.tenant_id).execution_options(populate_existing=True))
    if not repo:
        raise HTTPException(404, 'Repository not found')
    installation_id = repo.installation_id
    ig = db.scalar(select(InstallationGuard).where(InstallationGuard.id == installation_id)
                   .with_for_update().execution_options(populate_existing=True))
    installation = db.scalar(select(Installation).where(Installation.id == installation_id)
                             .with_for_update().execution_options(populate_existing=True))
    rg = db.scalar(select(RepositoryGuard).where(RepositoryGuard.installation_id == installation_id,
                   RepositoryGuard.repository_id == repository_id).with_for_update()
                   .execution_options(populate_existing=True))
    repo = db.scalar(select(Repository).where(Repository.id == repository_id)
                     .with_for_update().execution_options(populate_existing=True))
    if (not ig or ig.revoked or not installation or not installation.active
            or installation.tenant_id != identity.tenant_id or not rg or rg.revoked
            or not repo or not repo.enabled or repo.tenant_id != identity.tenant_id
            or repo.installation_id != installation_id or repo.full_name != name):
        raise HTTPException(404, 'Repository not found')


@router.post('/{repository_id}/investigations/{job_id}/report', status_code=202)
def request_report(request: Request, repository_id: int = Path(gt=0, lt=2**63), job_id: UUID = Path(),
                   identity: Principal = Depends(principal), db: Session = Depends(get_db),
                   github: GitHubClient = Depends(get_github_client)):
    require_csrf(request, identity, db)
    db.rollback()  # Never hold the CSRF row lock during GitHub authorization.
    name = authorize(repository_id, identity, db, github)
    require_csrf(request, identity, db)
    repo = db.scalar(select(Repository).where(Repository.id == repository_id,
                     Repository.tenant_id == identity.tenant_id))
    if not repo:
        raise HTTPException(404, 'Repository not found')
    installation_id = repo.installation_id
    if installation_guard(db, installation_id).revoked:
        raise HTTPException(404, 'Repository not found')
    installation = db.scalar(select(Installation).where(Installation.id == installation_id).with_for_update())
    if repository_guard(db, installation_id, repository_id).revoked:
        raise HTTPException(404, 'Repository not found')
    repo = db.scalar(select(Repository).where(Repository.id == repository_id)
                     .with_for_update().execution_options(populate_existing=True))
    if (not installation or not installation.active or installation.tenant_id != identity.tenant_id
            or not repo or not repo.enabled or repo.tenant_id != identity.tenant_id
            or repo.installation_id != installation_id or repo.full_name != name):
        raise HTTPException(404, 'Repository not found')
    parent, snapshot = parent_and_snapshot(db, repository_id, job_id, identity, name, lock_snapshot=True)
    try:
        evidence_inputs(db, parent, snapshot)
    except ModelError:
        raise HTTPException(409, 'Evidence is unavailable') from None
    task = db.scalar(select(InvestigationReportJob).where(InvestigationReportJob.investigation_id == parent.id))
    if not task:
        settings = get_settings()
        if settings.investigation_provider == 'openai':
            if not real_provider_enabled(settings):
                raise HTTPException(503, 'Real report generation is disabled')
            exp = db.get(InvestigationExperiment, settings.investigation_experiment_id)
            if not experiment_is_eligible(exp, identity.tenant_id, actual=True):
                raise HTTPException(503, 'Real report experiment is unavailable')
        task = InvestigationReportJob(id=str(uuid4()), investigation_id=parent.id, snapshot_id=snapshot.id,
            repository_id=repository_id, tenant_id=identity.tenant_id, user_id=identity.user_id,
            session_hash=identity.session_hash)
        db.add(task)
        db.flush()
        if settings.investigation_provider == 'openai':
            db.add(InvestigationProviderSelection(job_id=task.id, repository_id=repository_id,
                tenant_id=identity.tenant_id, experiment_id=exp.id))
        db.add(InvestigationReportOutbox(job_id=task.id, repository_id=repository_id, tenant_id=identity.tenant_id))
    selection = db.get(InvestigationProviderSelection, task.id)
    result = {'report_job_id': task.id, 'status': task.status, 'provider': 'openai' if selection else 'mock'}
    db.commit()
    return result


@router.get('/{repository_id}/investigations/{job_id}/report', response_model=ReportEnvelope)
def get_report(repository_id: int = Path(gt=0, lt=2**63), job_id: UUID = Path(),
               identity: Principal = Depends(principal), db: Session = Depends(get_db),
               github: GitHubClient = Depends(get_github_client)):
    name = authorize(repository_id, identity, db, github)
    lock_report_read_access(db, repository_id, identity, name)
    parent, snapshot = parent_and_snapshot(db, repository_id, job_id, identity, name, lock_snapshot=True)
    task = db.scalar(select(InvestigationReportJob).where(InvestigationReportJob.investigation_id == parent.id,
        InvestigationReportJob.tenant_id == identity.tenant_id, InvestigationReportJob.user_id == identity.user_id,
        InvestigationReportJob.repository_id == repository_id))
    if not task:
        raise HTTPException(404, 'Report not found')
    result = {'report_job_id': task.id, 'status': task.status, 'attempts': task.attempts,
              'error_code': task.error_code, 'created_at': task.created_at, 'started_at': task.started_at,
              'completed_at': task.completed_at, 'report': None}
    if task.status == 'completed':
        report = db.scalar(select(InvestigationReport).where(InvestigationReport.report_job_id == task.id,
            InvestigationReport.investigation_id == parent.id, InvestigationReport.snapshot_id == snapshot.id,
            InvestigationReport.commit_sha == snapshot.commit_sha, InvestigationReport.repository_id == repository_id,
            InvestigationReport.tenant_id == identity.tenant_id))
        if not report:
            report = db.scalar(select(InvestigationRealReport).where(InvestigationRealReport.report_job_id == task.id,
                InvestigationRealReport.investigation_id == parent.id, InvestigationRealReport.snapshot_id == snapshot.id,
                InvestigationRealReport.commit_sha == snapshot.commit_sha, InvestigationRealReport.repository_id == repository_id,
                InvestigationRealReport.tenant_id == identity.tenant_id))
        if not report:
            raise HTTPException(409, 'Report is unavailable')
        try:
            rows = evidence_inputs(db, parent, snapshot)
            rendered = render_report_payload(report.payload, parent=parent, evidence=rows)
        except ModelError:
            raise HTTPException(409, 'Report is unavailable') from None
        result['report'] = {'investigation_id': parent.id, 'repository_id': str(repository_id),
            'issue_id': str(parent.issue_id), 'issue_number': parent.issue_number, 'snapshot_id': snapshot.id,
            'commit_sha': snapshot.commit_sha, 'provider': report.provider, 'model': report.model, 'status': 'completed',
            'disclaimer': ('Deterministic mock output; not AI reasoning or a diagnosis.' if report.provider == 'mock'
                           else 'Model-generated possibilities require human review; they are not verified diagnoses.'),
            'input_truncated': report.input_truncated, 'snapshot_partial': bool(snapshot.skipped_count),
            'input_tokens': report.input_tokens,
            'output_tokens': report.output_tokens, 'cost_microusd': report.cost_microusd,
            'created_at': report.created_at, **rendered}
    return result
