"""Durable, lease-fenced reservations; amounts are integer millionths of a USD."""
from uuid import uuid4
from datetime import timedelta

from sqlalchemy import case, func, select

from app.domain.models import (InvestigationExperiment, InvestigationProviderSelection,
    InvestigationReportJob, InvestigationUsageReservation, now)
from app.modules.auth.session import utc
from app.modules.investigation.report_model import ModelError

# Conservative GPT-5.6 Terra rates: published long-context 2x input / 1.5x output,
# 1.25x input cache writes, plus 10% regional uplift. No discount is assumed.
# Provider price changes or additional fees must be reviewed before any real experiment.
MODEL = 'gpt-5.6-terra'
INPUT_WINDOW = 1_050_000
OUTPUT_LIMIT = 2048
PRICING_POLICY = 'gpt-5.6-terra-2026-10-30-v1'
INPUT_RATE_TENTHS = 55
OUTPUT_RATE_TENTHS = 198


def upper_cost(input_tokens: int, output_tokens: int) -> int:
    return (input_tokens * INPUT_RATE_TENTHS + output_tokens * OUTPUT_RATE_TENTHS + 9) // 10


def experiment_is_eligible(exp, tenant_id, *, actual=False):
    return bool(exp and exp.tenant_id == tenant_id and exp.enabled and exp.provider == 'openai'
        and exp.model == MODEL and (not actual or exp.mode == 'actual')
        and exp.max_input_tokens == INPUT_WINDOW and 1 <= exp.max_output_tokens <= OUTPUT_LIMIT
        and 1 <= exp.max_concurrent <= 20 and 1 <= exp.max_requests <= 1000
        and exp.pricing_checked_at and exp.expires_at
        and now() - timedelta(hours=24) <= utc(exp.pricing_checked_at) <= now()
        and now() < utc(exp.expires_at) <= utc(exp.pricing_checked_at) + timedelta(hours=24))


def _locked_job(db, job_id, lease):
    job = db.scalar(select(InvestigationReportJob).where(InvestigationReportJob.id == job_id).with_for_update())
    if (not job or job.status != 'running' or job.lease_token != lease or not job.lease_expires_at
            or utc(job.lease_expires_at) <= now()):
        raise ModelError('stale_worker')
    return job


def _usage_totals(db, experiment_id, investigation_id):
    row = InvestigationUsageReservation
    charge = case((row.state == 'known', func.coalesce(row.accounted_microusd, row.reserved_microusd)),
                  else_=row.reserved_microusd)
    return db.execute(select(func.coalesce(func.sum(charge), 0),
        func.coalesce(func.sum(case((row.investigation_id == investigation_id, charge), else_=0)), 0),
        func.coalesce(func.sum(case((row.state.in_(('reserved', 'sent', 'uncertain')), 1), else_=0)), 0),
        func.count(row.id))
        .where(row.experiment_id == experiment_id)).one()


def reserve(factory, job_id, lease):
    """Lock job then experiment. One reservation per job; never retry a sent request."""
    with factory.begin() as db:
        job = _locked_job(db, job_id, lease)
        selection = db.get(InvestigationProviderSelection, job.id)
        if not selection or selection.tenant_id != job.tenant_id or selection.repository_id != job.repository_id:
            raise ModelError('model_not_enabled')
        exp = db.scalar(select(InvestigationExperiment).where(
            InvestigationExperiment.id == selection.experiment_id).with_for_update())
        if not experiment_is_eligible(exp, job.tenant_id):
            raise ModelError('budget_unavailable')
        if exp.mode == 'actual' and db.bind.dialect.name != 'postgresql':
            raise ModelError('budget_unavailable')
        existing = db.scalar(select(InvestigationUsageReservation).where(
            InvestigationUsageReservation.job_id == job.id).with_for_update())
        if existing:
            if existing.state != 'reserved' or existing.experiment_id != exp.id:
                raise ModelError('model_billing_unknown')
            # A new valid lease may take over a reservation that was never marked sent.
            existing.lease_token, existing.updated_at = lease, now()
            return existing.id, existing.max_output_tokens, existing.mode
        amount = upper_cost(INPUT_WINDOW, exp.max_output_tokens)
        total, per_job, active, request_count = _usage_totals(db, exp.id, job.investigation_id)
        if (total + amount > exp.budget_microusd
                or per_job + amount > exp.investigation_budget_microusd
                or active >= exp.max_concurrent or request_count >= exp.max_requests):
            raise ModelError('budget_exhausted')
        reservation = InvestigationUsageReservation(id=str(uuid4()), job_id=job.id, experiment_id=exp.id,
            tenant_id=job.tenant_id, repository_id=job.repository_id, investigation_id=job.investigation_id,
            snapshot_id=job.snapshot_id, lease_token=lease, state='reserved', mode=exp.mode,
            reserved_microusd=amount, max_input_tokens=INPUT_WINDOW, max_output_tokens=exp.max_output_tokens,
            model=MODEL, pricing_policy=PRICING_POLICY, input_rate_tenths=INPUT_RATE_TENTHS,
            output_rate_tenths=OUTPUT_RATE_TENTHS)
        db.add(reservation)
        db.flush()
        return reservation.id, reservation.max_output_tokens, reservation.mode


def mark_sent(factory, job_id, lease, reservation_id):
    with factory.begin() as db:
        job = _locked_job(db, job_id, lease)
        selection = db.get(InvestigationProviderSelection, job_id)
        if not selection:
            raise ModelError('model_not_enabled')
        exp = db.scalar(select(InvestigationExperiment).where(
            InvestigationExperiment.id == selection.experiment_id).with_for_update())
        row = db.scalar(select(InvestigationUsageReservation).where(
            InvestigationUsageReservation.id == reservation_id).with_for_update())
        if (not experiment_is_eligible(exp, job.tenant_id) or not row or row.job_id != job.id
                or row.experiment_id != exp.id or row.lease_token != lease or row.state != 'reserved'
                or row.mode != exp.mode or row.max_output_tokens != exp.max_output_tokens
                or row.max_input_tokens != INPUT_WINDOW or row.model != MODEL
                or row.pricing_policy != PRICING_POLICY or row.input_rate_tenths != INPUT_RATE_TENTHS
                or row.output_rate_tenths != OUTPUT_RATE_TENTHS):
            raise ModelError('budget_unavailable')
        total, per_job, active, request_count = _usage_totals(db, exp.id, job.investigation_id)
        if (total > exp.budget_microusd or per_job > exp.investigation_budget_microusd
                or active > exp.max_concurrent or request_count > exp.max_requests):
            raise ModelError('budget_exhausted')
        row.state, row.updated_at = 'sent', now()
        return row.max_output_tokens, row.mode, row.experiment_id


def finish(factory, reservation_id, input_tokens=None, output_tokens=None):
    """Unknown usage stays fully reserved forever until an explicit manual reconciliation."""
    with factory.begin() as db:
        row = db.scalar(select(InvestigationUsageReservation).where(
            InvestigationUsageReservation.id == reservation_id).with_for_update())
        if not row or row.state != 'sent':
            return
        valid = (type(input_tokens) is int and 0 <= input_tokens <= row.max_input_tokens
                 and type(output_tokens) is int and 0 <= output_tokens <= row.max_output_tokens)
        if valid:
            row.state = 'known'
            row.input_tokens, row.output_tokens = input_tokens, output_tokens
            row.accounted_microusd = (input_tokens * row.input_rate_tenths
                                     + output_tokens * row.output_rate_tenths + 9) // 10
        else:
            row.state = 'uncertain'
        row.updated_at = now()
