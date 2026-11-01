"""One-use synthetic token-count preflight; real counting and generation remain disabled."""
from __future__ import annotations

import json
import re
import time
from datetime import timedelta
from uuid import uuid4

import httpx
from sqlalchemy import select

from app.domain.models import (AuthSession, Installation, InvestigationExecutorApproval, InvestigationExperiment,
    InvestigationProviderTokenCount, InvestigationReportJob, InvestigationTokenCount, Membership, Repository, now)
from app.evaluation.experiment_executor import (_NETWORK_FENCE_LOCK, canonical, canonical_id,
    digest, isolated_port, prepare_review, read_private, require_fake_configuration)
from app.evaluation.provider_harness import CASE_ID, COMMIT, network_fence
from app.modules.auth.session import utc
from app.modules.github.guards import installation_guard, repository_guard
from app.modules.investigation.openai_provider import MAX_REQUEST_BYTES, strict_schema
from app.modules.investigation.report_model import ModelError
from app.modules.investigation.usage_ledger import (INPUT_WINDOW, MODEL, OUTPUT_LIMIT, PRICING_POLICY,
    VerifiedCountFee, _usage_totals, experiment_is_eligible, require_stress_capacity,
    require_verified_count_pricing, upper_cost)

COUNT_ENDPOINT = 'https://api.openai.com/v1/responses/input_tokens'
FAKE_ACCOUNT = 'org_repopilot_fixture'
FAKE_PROJECT = 'proj_repopilot_fixture'
MAX_COUNT_RESPONSE = 4096
MAX_PROVIDER_INPUT_ALLOWANCE = 16_384


def _identity(kind, value):
    expected = FAKE_ACCOUNT if kind == 'account' else FAKE_PROJECT
    if value != expected:
        raise ModelError('count_approval_invalid')
    return digest((kind + '\0' + value).encode())


def provider_identity(kind, value):
    """Hash bounded server-side organization/project identifiers without persisting them."""
    if (kind not in ('account', 'project') or type(value) is not str
            or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value)):
        raise ModelError('count_approval_invalid')
    return digest((kind + '\0' + value).encode())


def count_projection(generation):
    """Project only the reviewed text-only Responses request into the count contract."""
    expected = {'model', 'instructions', 'input', 'text', 'max_output_tokens', 'service_tier',
                'prompt_cache_options', 'store', 'truncation'}
    if (type(generation) is not dict or set(generation) != expected
            or len(canonical(generation)) > MAX_REQUEST_BYTES or generation['model'] != MODEL
            or type(generation['instructions']) is not str or not generation['instructions']
            or type(generation['input']) is not list or len(generation['input']) != 1
            or type(generation['input'][0]) is not dict
            or set(generation['input'][0]) != {'role', 'content'}
            or generation['input'][0]['role'] != 'user' or type(generation['input'][0]['content']) is not str
            or generation['text'] != {'format': {'type': 'json_schema', 'name': 'investigation_report',
                                                  'strict': True, 'schema': strict_schema()}}
            or type(generation['max_output_tokens']) is not int or generation['max_output_tokens'] != OUTPUT_LIMIT
            or generation['service_tier'] != 'default' or generation['prompt_cache_options'] != {'ttl': '30m'}
            or generation['store'] is not False or generation['truncation'] != 'disabled'):
        raise ModelError('count_input_invalid')
    if type(generation['text']['format']['strict']) is not bool:
        raise ModelError('count_input_invalid')
    # The count reference lists these common fields. Generation-only settings remain
    # bound by the full generation hash; equivalence of their billing effect is unverified.
    return {key: generation[key] for key in ('model', 'instructions', 'input', 'text', 'truncation')}


def _lock_access(db, job_id, tenant_id):
    """Follow the existing job/session/installation/repository revocation lock order."""
    if type(tenant_id) is not int or tenant_id <= 0:
        raise ModelError('count_access_denied')
    job = db.scalar(select(InvestigationReportJob).where(InvestigationReportJob.id == job_id).with_for_update())
    if not job or job.tenant_id != tenant_id:
        raise ModelError('count_access_denied')
    session = db.scalar(select(AuthSession).where(AuthSession.id_hash == job.session_hash).with_for_update())
    repo = db.get(Repository, job.repository_id)
    if not session or not repo:
        raise ModelError('count_access_denied')
    membership = db.scalar(select(Membership).where(Membership.tenant_id == tenant_id,
        Membership.user_id == job.user_id).with_for_update())
    ig = installation_guard(db, repo.installation_id)
    installation = db.scalar(select(Installation).where(Installation.id == repo.installation_id).with_for_update())
    rg = repository_guard(db, repo.installation_id, repo.id)
    repo = db.scalar(select(Repository).where(Repository.id == repo.id)
                     .execution_options(populate_existing=True).with_for_update())
    if (ig.revoked or rg.revoked or not installation or not installation.active
            or installation.tenant_id != tenant_id or not repo or not repo.enabled or repo.tenant_id != tenant_id
            or session.tenant_id != tenant_id or session.user_id != job.user_id or not membership
            or session.revoked_at is not None or utc(session.expires_at) <= now()):
        raise ModelError('count_access_denied')
    return job, session


def _binding(row):
    return {'version': 'synthetic-count-v1', 'job_id': row.job_id, 'experiment_id': row.experiment_id,
        'investigation_id': row.investigation_id, 'snapshot_id': row.snapshot_id,
        'repository_id': row.repository_id, 'tenant_id': row.tenant_id, 'source_commit': row.source_commit,
        'fixture_id': row.fixture_id, 'mode': row.mode, 'provider': row.provider, 'model': row.model,
        'account_sha256': row.account_sha256, 'project_sha256': row.project_sha256,
        'generation_sha256': row.generation_sha256, 'count_sha256': row.count_sha256,
        'manifest_sha256': row.manifest_sha256, 'pricing_policy': row.pricing_policy,
        'max_output_tokens': row.max_output_tokens, 'max_input_tokens': row.max_input_tokens,
        'expires_at': utc(row.expires_at).isoformat()}


def _provider_binding(row):
    """Immutable provider-count authorization fields; result and state are separate."""
    return {'version': 'provider-count-v1', 'job_id': row.job_id, 'experiment_id': row.experiment_id,
        'investigation_id': row.investigation_id, 'snapshot_id': row.snapshot_id,
        'repository_id': row.repository_id, 'tenant_id': row.tenant_id, 'source_commit': row.source_commit,
        'fixture_id': row.fixture_id, 'origin': row.origin, 'provider': row.provider, 'model': row.model,
        'account_sha256': row.account_sha256, 'project_sha256': row.project_sha256,
        'generation_sha256': row.generation_sha256, 'count_sha256': row.count_sha256,
        'manifest_sha256': row.manifest_sha256, 'pricing_policy': row.pricing_policy,
        'fee_policy': row.fee_policy, 'fee_reserved_microusd': row.fee_reserved_microusd,
        'service_tier': row.service_tier, 'cache_ttl': row.cache_ttl,
        'max_output_tokens': row.max_output_tokens, 'max_input_tokens': row.max_input_tokens,
        'expires_at': utc(row.expires_at).isoformat()}


def _provider_fee_terms(account, project):
    """Only independently verified terms may open the still-unconditional fee gate."""
    terms = require_verified_count_pricing()
    if (type(terms) is not VerifiedCountFee or type(terms.policy) is not str
            or not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', terms.policy)
            or type(terms.bound_microusd) is not int or not 0 <= terms.bound_microusd <= 6_000_000
            or terms.account_sha256 != provider_identity('account', account)
            or terms.project_sha256 != provider_identity('project', project)
            or terms.model != MODEL or terms.generation_policy != PRICING_POLICY
            or not terms.valid_until or terms.valid_until.tzinfo is None or utc(terms.valid_until) <= now()):
        raise ModelError('count_pricing_unverified')
    return terms


def _check_provider_identity(row, job, exp, generation, manifest, projection, account, project, snapshot_id, terms):
    """Validate immutable authorization fields for a provider count."""
    if (not row or getattr(row, 'origin', None) != 'external'
            or row.job_id != job.id or row.experiment_id != exp.id
            or not experiment_is_eligible(exp, job.tenant_id, actual=True)
            or exp.max_requests != 1 or exp.max_concurrent != 1 or exp.max_output_tokens != OUTPUT_LIMIT
            or exp.budget_microusd > 10_000_000 or exp.investigation_budget_microusd > 6_000_000
            or row.tenant_id != job.tenant_id or exp.tenant_id != job.tenant_id
            or row.investigation_id != job.investigation_id or row.repository_id != job.repository_id
            or row.snapshot_id != job.snapshot_id or row.snapshot_id != snapshot_id
            or row.source_commit != COMMIT or row.fixture_id != CASE_ID
            or row.provider != 'openai' or row.model != MODEL or row.pricing_policy != PRICING_POLICY
            or row.fee_policy != terms.policy or row.fee_reserved_microusd != terms.bound_microusd
            or row.service_tier != 'default' or row.cache_ttl != '30m'
            or row.max_output_tokens != OUTPUT_LIMIT or type(row.max_input_tokens) is not int
            or not 1 <= row.max_input_tokens <= MAX_PROVIDER_INPUT_ALLOWANCE
            or row.account_sha256 != provider_identity('account', account)
            or row.project_sha256 != provider_identity('project', project)
            or row.invalidated_at is not None or utc(row.expires_at) <= now()
            or utc(row.expires_at) > utc(exp.expires_at)
            or utc(row.expires_at) > utc(terms.valid_until)
            or row.generation_sha256 != digest(canonical(generation))
            or row.count_sha256 != digest(canonical(projection))
            or row.manifest_sha256 != digest(canonical(manifest))
            or row.binding_sha256 != digest(canonical(_provider_binding(row)))
            or row.consumed_at is not None or row.generation_approval_id is not None):
        raise ModelError('count_approval_invalid')
    return row


def _check_provider_binding(row, job, exp, generation, manifest, projection, account, project, snapshot_id, terms):
    """Validate external-only provenance. This does not make a provider request."""
    _check_provider_identity(row, job, exp, generation, manifest, projection, account, project, snapshot_id, terms)
    if (row.status != 'verified' or not row.created_at or not row.sent_at or not row.completed_at
            or utc(row.sent_at) < utc(row.created_at) or utc(row.completed_at) < utc(row.sent_at)
            or utc(row.completed_at) > now()
            or type(row.input_tokens) is not int or not 0 <= row.input_tokens <= row.max_input_tokens
            or row.fee_state not in ('known', 'uncertain')
            or row.fee_state == 'known' and (type(row.fee_accounted_microusd) is not int
                or not 0 <= row.fee_accounted_microusd <= row.fee_reserved_microusd)
            or row.fee_state == 'uncertain' and row.fee_accounted_microusd is not None):
        raise ModelError('count_approval_invalid')
    return row


def validate_locked_provider_count(db, *, count_id, job, exp, generation, manifest, account, project, snapshot_id):
    """Require separately authorized provider evidence, never a simulated-count row."""
    if not canonical_id(count_id):
        raise ModelError('count_approval_invalid')
    terms = _provider_fee_terms(account, project)
    row = db.scalar(select(InvestigationProviderTokenCount).where(
        InvestigationProviderTokenCount.id == count_id).with_for_update())
    if (db.get(InvestigationTokenCount, count_id) is not None
            or db.scalar(select(InvestigationTokenCount.id).where(
                (InvestigationTokenCount.job_id == job.id) | (InvestigationTokenCount.experiment_id == exp.id)))
            or db.get(InvestigationExecutorApproval, count_id) is not None):
        raise ModelError('count_approval_invalid')
    return _check_provider_binding(row, job, exp, generation, manifest, count_projection(generation),
                                   account, project, snapshot_id, terms)


def record_provider_count_approval(factory, root, *, job_id, experiment_id, tenant_id, account, project,
                                   review_directory, generation_sha256, manifest_sha256, expires_at,
                                   max_input_tokens, disclosure_acknowledged=False, pricing_acknowledged=False):
    """Record a separate count authorization only after independently verified fee terms.

    The count-pricing gate is currently unconditional, so this cannot create a live approval.
    """
    from app.evaluation.disclosure_screen import screen_exact

    if disclosure_acknowledged is not True or pricing_acknowledged is not True:
        raise ModelError('count_approval_invalid')
    terms = _provider_fee_terms(account, project)
    if factory.kw['bind'].dialect.name != 'postgresql':
        raise ModelError('count_approval_invalid')
    require_fake_configuration(allow_provider_identity=True)
    port = isolated_port(factory)
    if (not canonical_id(job_id) or not canonical_id(experiment_id) or type(tenant_id) is not int
            or type(max_input_tokens) is not int or not 1 <= max_input_tokens <= MAX_PROVIDER_INPUT_ALLOWANCE
            or not expires_at or expires_at.tzinfo is None or utc(expires_at) <= now()
            or utc(expires_at) > now() + timedelta(minutes=15) or utc(expires_at) > utc(terms.valid_until)):
        raise ModelError('count_approval_invalid')
    with _NETWORK_FENCE_LOCK, network_fence(port):
        reviewed, reviewed_manifest = read_private(review_directory, root, experiment_id=experiment_id, job_id=job_id)
        screen_exact(root, reviewed, reviewed_manifest)
        with factory.begin() as db:
            job, session, exp, generation, manifest, projection = _prepared(
                db, factory, root, job_id=job_id, experiment_id=experiment_id, tenant_id=tenant_id)
            if (reviewed != generation or reviewed_manifest != manifest
                    or not experiment_is_eligible(exp, tenant_id)
                    or exp.max_requests != 1 or exp.max_concurrent != 1 or exp.max_output_tokens != OUTPUT_LIMIT
                    or exp.budget_microusd > 10_000_000 or exp.investigation_budget_microusd > 6_000_000
                    or digest(canonical(generation)) != generation_sha256
                    or digest(canonical(manifest)) != manifest_sha256 or utc(expires_at) > utc(exp.expires_at)
                    or utc(expires_at) > utc(session.expires_at) or manifest['fixture_id'] != CASE_ID
                    or manifest['source_commit'] != COMMIT
                    or db.scalar(select(InvestigationTokenCount.id).where(
                        (InvestigationTokenCount.job_id == job_id) | (InvestigationTokenCount.experiment_id == experiment_id)))
                    or db.scalar(select(InvestigationProviderTokenCount.id).where(
                        (InvestigationProviderTokenCount.job_id == job_id)
                        | (InvestigationProviderTokenCount.experiment_id == experiment_id)))
                    or db.scalar(select(InvestigationExecutorApproval.id).where(
                        (InvestigationExecutorApproval.job_id == job_id)
                        | (InvestigationExecutorApproval.experiment_id == experiment_id)))):
                raise ModelError('count_approval_invalid')
            total, per_job, active, requests = _usage_totals(db, experiment_id, job.investigation_id)
            generation_bound = upper_cost(INPUT_WINDOW, OUTPUT_LIMIT)
            combined = generation_bound + terms.bound_microusd
            require_stress_capacity(combined, exp.investigation_budget_microusd, exp.budget_microusd)
            if (total + combined > exp.budget_microusd or per_job + combined > exp.investigation_budget_microusd
                    or active or requests):
                raise ModelError('budget_exhausted')
            row = InvestigationProviderTokenCount(id=str(uuid4()), job_id=job_id, experiment_id=experiment_id,
                investigation_id=job.investigation_id, snapshot_id=job.snapshot_id, repository_id=job.repository_id,
                tenant_id=tenant_id, source_commit=COMMIT, fixture_id=CASE_ID, origin='external', provider='openai',
                model=MODEL, account_sha256=provider_identity('account', account),
                project_sha256=provider_identity('project', project), generation_sha256=generation_sha256,
                count_sha256=digest(canonical(projection)), manifest_sha256=manifest_sha256, binding_sha256='',
                pricing_policy=PRICING_POLICY, fee_policy=terms.policy, service_tier='default', cache_ttl='30m',
                max_input_tokens=max_input_tokens, max_output_tokens=OUTPUT_LIMIT, status='pending',
                fee_state='reserved', fee_reserved_microusd=terms.bound_microusd,
                created_at=now(), expires_at=expires_at)
            row.binding_sha256 = digest(canonical(_provider_binding(row)))
            # Count authorization is distinct from a generation approval.
            exp.mode = 'actual'
            db.add(row)
            db.flush()
            return row.id


def validate_provider_count_for_generation(factory, root, *, count_id, job_id, experiment_id, tenant_id,
                                           account, project, snapshot_id):
    """Read-only preflight; the count is consumed atomically with the later send marker."""
    port = isolated_port(factory)
    if not canonical_id(count_id) or not canonical_id(snapshot_id):
        raise ModelError('count_approval_invalid')
    with _NETWORK_FENCE_LOCK, network_fence(port), factory.begin() as db:
        job, _ = _lock_access(db, job_id, tenant_id)
        exp = db.scalar(select(InvestigationExperiment).where(InvestigationExperiment.id == experiment_id).with_for_update())
        if not exp or exp.mode != 'actual' or exp.tenant_id != tenant_id:
            raise ModelError('count_approval_invalid')
        generation, manifest = prepare_review(factory, root, experiment_id=experiment_id, job_id=job_id, session=db)
        row = validate_locked_provider_count(db, count_id=count_id, job=job, exp=exp, generation=generation,
            manifest=manifest, account=account, project=project, snapshot_id=snapshot_id)
        return row.input_tokens


def _provider_count_uncertain(factory, count_id):
    """A marked send is never retried or automatically refunded."""
    with factory.begin() as db:
        row = db.scalar(select(InvestigationProviderTokenCount).where(
            InvestigationProviderTokenCount.id == count_id).with_for_update())
        if not row or row.status != 'sent':
            raise ModelError('count_approval_invalid')
        row.status, row.completed_at, row.fee_state = 'uncertain', now(), 'uncertain'


def run_provider_count(factory, root, *, count_id, job_id, experiment_id, tenant_id, account, project,
                       snapshot_id, transport=None):
    """Send a separately authorized count once; currently blocked by the fee gate.

    Mock transports are rejected for external provenance. The fake adapter exercises the
    shared bounded parser, but its results stay in the simulated table.
    """
    from app.core.config import get_settings

    if transport is not None:
        raise ModelError('count_not_enabled')
    terms = _provider_fee_terms(account, project)
    if factory.kw['bind'].dialect.name != 'postgresql':
        raise ModelError('count_not_enabled')
    port = isolated_port(factory)
    settings = get_settings()
    api_key = settings.investigation_openai_api_key.get_secret_value()
    if (not canonical_id(count_id) or not canonical_id(snapshot_id) or settings.app_env != 'test'
            or not settings.investigation_count_external_enabled or settings.investigation_paid_background_enabled
            or settings.investigation_real_enabled
            or settings.investigation_provider != 'openai' or not api_key
            or settings.investigation_experiment_id != experiment_id
            or settings.embedding_provider != 'disabled' or settings.embedding_allow_paid
            or settings.investigation_openai_organization.get_secret_value() != account
            or settings.investigation_openai_project.get_secret_value() != project):
        raise ModelError('count_not_enabled')
    with _NETWORK_FENCE_LOCK, network_fence(port), factory.begin() as db:
        job, _ = _lock_access(db, job_id, tenant_id)
        exp = db.scalar(select(InvestigationExperiment).where(InvestigationExperiment.id == experiment_id).with_for_update())
        if not exp or exp.mode != 'actual' or exp.tenant_id != tenant_id:
            raise ModelError('count_approval_invalid')
        generation, manifest = prepare_review(factory, root, experiment_id=experiment_id, job_id=job_id, session=db)
        projection = count_projection(generation)
        row = db.scalar(select(InvestigationProviderTokenCount).where(
            InvestigationProviderTokenCount.id == count_id).with_for_update())
        _check_provider_identity(row, job, exp, generation, manifest, projection, account, project, snapshot_id, terms)
        if (row.status != 'pending' or row.fee_state != 'reserved'
                or db.get(InvestigationExecutorApproval, count_id) is not None
                or db.scalar(select(InvestigationExecutorApproval.id).where(
                    (InvestigationExecutorApproval.job_id == job.id)
                    | (InvestigationExecutorApproval.experiment_id == exp.id)))
                or db.get(InvestigationTokenCount, count_id) is not None
                or db.scalar(select(InvestigationTokenCount.id).where(
                    (InvestigationTokenCount.job_id == job.id) | (InvestigationTokenCount.experiment_id == exp.id)))):
            raise ModelError('count_approval_invalid')
        total, per_job, active, requests = _usage_totals(db, experiment_id, job.investigation_id)
        generation_bound = upper_cost(INPUT_WINDOW, OUTPUT_LIMIT)
        require_stress_capacity(generation_bound + row.fee_reserved_microusd,
                                exp.investigation_budget_microusd, exp.budget_microusd)
        if (total + generation_bound > exp.budget_microusd
                or per_job + generation_bound > exp.investigation_budget_microusd or active or requests):
            raise ModelError('budget_exhausted')
        row.status, row.sent_at = 'sent', now()
        payload = canonical(projection)
    # No database transaction or lock is held during network work. Current pricing
    # remains unverified, so this block cannot be reached in this checkpoint.
    try:
        deadline = time.monotonic() + 30
        with httpx.Client(timeout=httpx.Timeout(10), trust_env=False, follow_redirects=False) as client:
            with client.stream('POST', COUNT_ENDPOINT, content=payload,
                    headers={'Authorization': 'Bearer ' + api_key, 'Content-Type': 'application/json',
                             'OpenAI-Organization': account, 'OpenAI-Project': project,
                             'X-Client-Request-Id': count_id}) as response:
                count = _read_count_response(response, deadline=deadline)
    except BaseException as exc:
        try:
            _provider_count_uncertain(factory, count_id)
        except Exception:
            raise ModelError('count_state_unavailable') from None
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        raise ModelError('count_billing_unknown') from None
    try:
        with _NETWORK_FENCE_LOCK, network_fence(port), factory.begin() as db:
            job, _ = _lock_access(db, job_id, tenant_id)
            exp = db.scalar(select(InvestigationExperiment).where(InvestigationExperiment.id == experiment_id).with_for_update())
            if not exp or exp.mode != 'actual' or exp.tenant_id != tenant_id:
                raise ModelError('count_approval_invalid')
            generation, manifest = prepare_review(factory, root, experiment_id=experiment_id, job_id=job_id, session=db)
            row = db.scalar(select(InvestigationProviderTokenCount).where(
                InvestigationProviderTokenCount.id == count_id).with_for_update())
            _check_provider_identity(row, job, exp, generation, manifest, count_projection(generation),
                                     account, project, snapshot_id, _provider_fee_terms(account, project))
            if row.status != 'sent' or row.fee_state != 'reserved':
                raise ModelError('count_approval_invalid')
            row.status, row.completed_at, row.input_tokens, row.fee_state = 'verified', now(), count, 'uncertain'
            input_allowance = row.max_input_tokens
    except Exception:
        try:
            _provider_count_uncertain(factory, count_id)
        except Exception:
            raise ModelError('count_state_unavailable') from None
        raise ModelError('count_state_unavailable') from None
    if count > input_allowance:
        raise ModelError('count_limit_exceeded')
    return count


def _prepared(db, factory, root, *, job_id, experiment_id, tenant_id):
    job, session = _lock_access(db, job_id, tenant_id)
    exp = db.scalar(select(InvestigationExperiment).where(InvestigationExperiment.id == experiment_id).with_for_update())
    if not exp or exp.mode != 'simulated' or exp.tenant_id != tenant_id:
        raise ModelError('count_approval_invalid')
    generation, manifest = prepare_review(factory, root, experiment_id=experiment_id, job_id=job_id, session=db)
    projection = count_projection(generation)
    return job, session, exp, generation, manifest, projection


def create_fake_count_approval(factory, root, *, job_id, experiment_id, tenant_id, account, project,
                               review_directory, generation_sha256, manifest_sha256, expires_at,
                               max_input_tokens=16_384, acknowledge_count_disclosure=False):
    """Record a synthetic one-use count authorization; cannot create paid approval."""
    if acknowledge_count_disclosure is not True:
        raise ModelError('count_approval_invalid')
    require_fake_configuration()
    port = isolated_port(factory)
    account_sha, project_sha = _identity('account', account), _identity('project', project)
    if (not canonical_id(job_id) or not canonical_id(experiment_id) or type(tenant_id) is not int
            or type(max_input_tokens) is not int or not 1 <= max_input_tokens <= INPUT_WINDOW
            or not expires_at or expires_at.tzinfo is None or utc(expires_at) <= now()
            or utc(expires_at) > now() + timedelta(minutes=15)):
        raise ModelError('count_approval_invalid')
    with _NETWORK_FENCE_LOCK, network_fence(port):
        reviewed, reviewed_manifest = read_private(review_directory, root, experiment_id=experiment_id, job_id=job_id)
        with factory.begin() as db:
            job, session, exp, generation, manifest, projection = _prepared(
                db, factory, root, job_id=job_id, experiment_id=experiment_id, tenant_id=tenant_id)
            if (reviewed != generation or reviewed_manifest != manifest or digest(canonical(generation)) != generation_sha256
                    or digest(canonical(manifest)) != manifest_sha256 or utc(expires_at) > utc(exp.expires_at)
                    or utc(expires_at) > utc(session.expires_at) or manifest['fixture_id'] != CASE_ID
                    or manifest['source_commit'] != COMMIT):
                raise ModelError('count_approval_invalid')
            if db.scalar(select(InvestigationTokenCount.id).where(
                    (InvestigationTokenCount.job_id == job_id) | (InvestigationTokenCount.experiment_id == experiment_id))):
                raise ModelError('count_approval_invalid')
            count_id = str(uuid4())
            if db.get(InvestigationExecutorApproval, count_id) is not None:
                raise ModelError('count_approval_invalid')
            row = InvestigationTokenCount(id=count_id, job_id=job_id, experiment_id=experiment_id,
                investigation_id=job.investigation_id, snapshot_id=job.snapshot_id, repository_id=job.repository_id,
                tenant_id=tenant_id, source_commit=COMMIT, fixture_id=CASE_ID, mode='simulated', provider='openai',
                model=MODEL, account_sha256=account_sha, project_sha256=project_sha,
                generation_sha256=generation_sha256, count_sha256=digest(canonical(projection)),
                manifest_sha256=manifest_sha256, binding_sha256='', pricing_policy=PRICING_POLICY,
                max_output_tokens=OUTPUT_LIMIT, max_input_tokens=max_input_tokens,
                status='ready', created_at=now(), expires_at=expires_at)
            row.binding_sha256 = digest(canonical(_binding(row)))
            db.add(row)
            db.flush()
            return row.id


def _validate_binding(row, job, exp, generation, manifest, projection, account, project, *, expected_snapshot):
    if (not row or row.job_id != job.id or row.experiment_id != exp.id or row.tenant_id != job.tenant_id
            or row.investigation_id != job.investigation_id or row.repository_id != job.repository_id
            or row.snapshot_id != job.snapshot_id or row.snapshot_id != expected_snapshot
            or row.source_commit != COMMIT or row.fixture_id != CASE_ID or row.mode != 'simulated'
            or row.provider != 'openai' or row.model != MODEL or row.pricing_policy != PRICING_POLICY
            or row.max_output_tokens != OUTPUT_LIMIT or row.account_sha256 != _identity('account', account)
            or row.project_sha256 != _identity('project', project) or row.invalidated_at is not None
            or utc(row.expires_at) <= now() or row.generation_sha256 != digest(canonical(generation))
            or row.count_sha256 != digest(canonical(projection)) or row.manifest_sha256 != digest(canonical(manifest))
            or row.binding_sha256 != digest(canonical(_binding(row)))):
        raise ModelError('count_approval_invalid')


def _mark_fake_count_sent(factory, root, *, count_id, job_id, experiment_id, tenant_id, account, project, snapshot_id):
    require_fake_configuration()
    isolated_port(factory)
    if not canonical_id(count_id) or not canonical_id(snapshot_id):
        raise ModelError('count_approval_invalid')
    with factory.begin() as db:
        job, _, exp, generation, manifest, projection = _prepared(
            db, factory, root, job_id=job_id, experiment_id=experiment_id, tenant_id=tenant_id)
        row = db.scalar(select(InvestigationTokenCount).where(InvestigationTokenCount.id == count_id).with_for_update())
        if db.get(InvestigationExecutorApproval, count_id) is not None:
            raise ModelError('count_approval_invalid')
        _validate_binding(row, job, exp, generation, manifest, projection, account, project,
                          expected_snapshot=snapshot_id)
        if row.status != 'ready':
            raise ModelError('count_approval_invalid')
        row.status, row.sent_at = 'sent', now()
        return canonical(projection)


def _finish_uncertain(factory, count_id):
    with factory.begin() as db:
        row = db.scalar(select(InvestigationTokenCount).where(InvestigationTokenCount.id == count_id).with_for_update())
        if not row or row.status != 'sent':
            raise ModelError('count_approval_invalid')
        row.status, row.input_tokens, row.completed_at = 'uncertain', None, now()


def _complete_fake_count(factory, root, *, count_id, job_id, experiment_id, tenant_id, account, project,
                         snapshot_id, count):
    """Revalidate access and binding in the same transaction that stores the result."""
    with factory.begin() as db:
        job, _, exp, generation, manifest, projection = _prepared(
            db, factory, root, job_id=job_id, experiment_id=experiment_id, tenant_id=tenant_id)
        row = db.scalar(select(InvestigationTokenCount).where(InvestigationTokenCount.id == count_id).with_for_update())
        _validate_binding(row, job, exp, generation, manifest, projection, account, project,
                          expected_snapshot=snapshot_id)
        if row.status != 'sent':
            raise ModelError('count_approval_invalid')
        row.status, row.input_tokens, row.completed_at = 'complete', count, now()


def _invalidate_completed(factory, count_id):
    with factory.begin() as db:
        row = db.scalar(select(InvestigationTokenCount).where(InvestigationTokenCount.id == count_id).with_for_update())
        if row and row.status == 'complete' and row.invalidated_at is None:
            row.invalidated_at = now()


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate_key')
        result[key] = value
    return result


def _read_count_response(response, *, deadline):
    if response.status_code != 200:
        raise ValueError('count_http_error')
    raw = bytearray()
    for part in response.iter_bytes():
        if time.monotonic() > deadline:
            raise ValueError('count_timeout')
        raw.extend(part)
        if len(raw) > MAX_COUNT_RESPONSE:
            raise ValueError('count_response_too_large')
    data = json.loads(raw, object_pairs_hook=_unique_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('invalid_number')))
    if (type(data) is not dict or set(data) != {'object', 'input_tokens'}
            or data['object'] != 'response.input_tokens' or type(data['input_tokens']) is not int
            or not 0 <= data['input_tokens'] <= INPUT_WINDOW):
        raise ValueError('count_response_invalid')
    return data['input_tokens']


def _post_count(payload, *, count_id, account, project, api_key, transport):
    """Bounded fake HTTP/parser logic; it cannot fall through to live transport."""
    if type(transport) is not httpx.MockTransport:
        raise ModelError('count_not_enabled')
    deadline = time.monotonic() + 30
    with httpx.Client(transport=transport, timeout=httpx.Timeout(10), trust_env=False,
                      follow_redirects=False) as client:
        with client.stream('POST', COUNT_ENDPOINT, content=payload,
                headers={'Authorization': 'Bearer ' + api_key, 'Content-Type': 'application/json',
                         'OpenAI-Organization': account, 'OpenAI-Project': project,
                         'X-Client-Request-Id': count_id}) as response:
            return _read_count_response(response, deadline=deadline)


def run_fake_count(factory, root, *, count_id, job_id, experiment_id, tenant_id, account, project,
                   snapshot_id, transport):
    """Mark one simulated send and use only an injected, fenced MockTransport."""
    require_fake_configuration()
    if type(transport) is not httpx.MockTransport:
        raise ModelError('count_not_enabled')
    port = isolated_port(factory)
    with _NETWORK_FENCE_LOCK, network_fence(port):
        payload = _mark_fake_count_sent(factory, root, count_id=count_id, job_id=job_id,
            experiment_id=experiment_id, tenant_id=tenant_id, account=account, project=project, snapshot_id=snapshot_id)
        try:
            count = _post_count(payload, count_id=count_id, account=account, project=project,
                                api_key='synthetic-fake-only-key', transport=transport)
        except BaseException as exc:
            try:
                _finish_uncertain(factory, count_id)
            except Exception:
                raise ModelError('count_state_unavailable') from None
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            raise ModelError('count_billing_unknown') from None
        try:
            _complete_fake_count(factory, root, count_id=count_id, job_id=job_id, experiment_id=experiment_id,
                tenant_id=tenant_id, account=account, project=project, snapshot_id=snapshot_id, count=count)
        except (ModelError, ValueError):
            try:
                _finish_uncertain(factory, count_id)
            except Exception:
                raise ModelError('count_state_unavailable') from None
            raise
        except Exception:
            raise ModelError('count_state_unavailable') from None
        try:
            return validate_fake_count_for_generation(factory, root, count_id=count_id, job_id=job_id,
                experiment_id=experiment_id, tenant_id=tenant_id, account=account, project=project, snapshot_id=snapshot_id)
        except (ModelError, ValueError) as exc:
            if not isinstance(exc, ModelError) or str(exc) != 'count_limit_exceeded':
                try:
                    _invalidate_completed(factory, count_id)
                except Exception:
                    raise ModelError('count_state_unavailable') from None
            raise


def validate_fake_count_for_generation(factory, root, *, count_id, job_id, experiment_id, tenant_id,
                                       account, project, snapshot_id):
    """Check a simulated count binding; it never authorizes or prices a real request."""
    require_fake_configuration()
    port = isolated_port(factory)
    if not canonical_id(count_id) or not canonical_id(snapshot_id):
        raise ModelError('count_approval_invalid')
    with _NETWORK_FENCE_LOCK, network_fence(port), factory.begin() as db:
        job, _, exp, generation, manifest, projection = _prepared(
            db, factory, root, job_id=job_id, experiment_id=experiment_id, tenant_id=tenant_id)
        return validate_locked_fake_count(db, count_id=count_id, job=job, exp=exp, generation=generation,
            manifest=manifest, projection=projection, account=account, project=project, snapshot_id=snapshot_id)


def validate_locked_fake_count(db, *, count_id, job, exp, generation, manifest, projection, account, project,
                               snapshot_id):
    """Recheck a count in the generation send-marker transaction; simulated mode only."""
    row = db.scalar(select(InvestigationTokenCount).where(InvestigationTokenCount.id == count_id).with_for_update())
    if db.get(InvestigationExecutorApproval, count_id) is not None:
        raise ModelError('count_approval_invalid')
    _validate_binding(row, job, exp, generation, manifest, projection, account, project,
                      expected_snapshot=snapshot_id)
    if row.status != 'complete' or type(row.input_tokens) is not int or row.input_tokens < 0:
        raise ModelError('count_approval_invalid')
    if row.input_tokens > row.max_input_tokens:
        raise ModelError('count_limit_exceeded')
    return row.input_tokens
