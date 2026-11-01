"""Offline preview and separately approved, one-use experiment executor.

The live command is disabled unless an exact, independently recorded approval exists.
This checkpoint runs and tests only the dry-run and fake-transport paths.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import stat
import tempfile
from contextlib import nullcontext
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from uuid import UUID, uuid4

import httpx
from sqlalchemy import or_, select, text

from app.domain.models import (InvestigationExecutorApproval, InvestigationExperiment,
    InvestigationProviderSelection, InvestigationReportJob, Repository, User, now)
from app.evaluation.provider_harness import (CASE_ID, COMMIT, DATASET_HASH, EXPECTED_PATH,
    REPOSITORY, TREE, load_fixture, network_fence, require)
from app.modules.auth.session import utc
from app.modules.ingestion.citations import github_citation
from app.modules.investigation.openai_provider import MAX_REQUEST_BYTES, OpenAIInvestigationModel, build_responses_payload
from app.modules.investigation.report_model import (EvidenceInput, InvestigationInput, ModelError, ModelRequest,
    REPORT_INSTRUCTIONS, build_package, model_request, sanitize_issue_text, sanitize_source)
from app.modules.investigation.usage_ledger import (INPUT_WINDOW, MODEL, OUTPUT_LIMIT,
    experiment_is_eligible, mark_sent, require_stress_capacity, require_verified_actual_pricing, upper_cost)

_NETWORK_FENCE_LOCK = RLock()


def require_fake_configuration(*, allow_provider_identity=False):
    """The isolated executor never consumes a real key or enables paid settings."""
    if (os.environ.get('INVESTIGATION_PROVIDER', 'mock') != 'mock'
            or os.environ.get('INVESTIGATION_REAL_ENABLED', 'false').lower() not in ('false', '0', '')
            or os.environ.get('INVESTIGATION_PAID_BACKGROUND_ENABLED', 'false').lower() not in ('false', '0', '')
            or os.environ.get('EMBEDDING_PROVIDER', 'disabled') != 'disabled'
            or os.environ.get('EMBEDDING_ALLOW_PAID', 'false').lower() not in ('false', '0', '')
            or os.environ.get('INVESTIGATION_EXPERIMENT_ID')
            or os.environ.get('INVESTIGATION_OPENAI_API_KEY') or os.environ.get('OPENAI_API_KEY')
            or not allow_provider_identity and (os.environ.get('INVESTIGATION_OPENAI_ORGANIZATION')
                                               or os.environ.get('INVESTIGATION_OPENAI_PROJECT'))
            or os.environ.get('INVESTIGATION_COUNT_EXTERNAL_ENABLED', 'false').lower() not in ('false', '0', '')
            or os.environ.get('EMBEDDING_API_KEY')):
        raise ModelError('model_not_enabled')


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode('utf-8')


def digest(value):
    return hashlib.sha256(value).hexdigest()


def canonical_id(value):
    try:
        return str(UUID(value)) == value
    except (TypeError, ValueError, AttributeError):
        return False


def isolated_port(factory):
    """Allow only the dedicated 5B2B PostgreSQL target or an in-memory unit test DB."""
    url = factory.kw['bind'].url
    if os.environ.get('APP_ENV') != 'test':
        raise ModelError('approval_invalid')
    if (url.get_backend_name() == 'postgresql' and url.host == '127.0.0.1' and url.port
            and url.username == 'repopilot_fixture' and not url.query
            and re.fullmatch(r'repopilot_5b2b_[0-9a-f]{16}', url.database or '')):
        return url.port
    if (url.get_backend_name() == 'sqlite' and url.database in (None, '', ':memory:')
            and os.environ.get('APP_ENV') == 'test'):
        return 0
    raise ModelError('approval_invalid')


def normalized(request):
    """Exclude a volatile fetch time; all other approved fields remain exact."""
    if type(request) is not ModelRequest:
        raise ModelError('model_input_invalid')
    return model_request(replace(request.untrusted_data, issue_retrieved_at=None))


def disclosure(root, request, *, experiment_id, job_id):
    """Build an exact semantic request and secret-minimized review manifest."""
    require(canonical_id(experiment_id) and canonical_id(job_id), 'invalid_executor_identifier')
    request = normalized(request)
    data = request.untrusted_data
    _, case, source, chunks, file, omitted = load_fixture(root)
    require(data.commit_sha == COMMIT and data.repository_id == '902' and data.issue_id == '990'
            and data.issue_number == 5 and canonical_id(data.investigation_id)
            and canonical_id(data.snapshot_id) and data.title == sanitize_issue_text(case['title'], 500)
            and data.body == sanitize_issue_text(case['body'], 2500)
            and not data.labels and not data.comments, 'fixture_mismatch')
    allowed = {(chunk.symbol, chunk.start_line, chunk.end_line): chunk for chunk in chunks}
    require(1 <= len(data.evidence) <= 2, 'fixture_evidence_mismatch')
    metadata = []
    for item in data.evidence:
        key = (item.symbol, item.start_line, item.end_line)
        chunk = allowed.get(key)
        require(chunk is not None and item.path == EXPECTED_PATH and canonical_id(item.chunk_id)
                and item.commit_sha == COMMIT and item.snapshot_id == data.snapshot_id
                and item.citation == github_citation(REPOSITORY, COMMIT, EXPECTED_PATH,
                                                     item.start_line, item.end_line)
                and item.excerpt == sanitize_source(chunk.text, 800), 'fixture_evidence_mismatch')
        metadata.append({'chunk_id': item.chunk_id, 'path': item.path, 'symbol': item.symbol,
            'start_line': item.start_line, 'end_line': item.end_line,
            'citation': item.citation, 'excerpt_bytes': len(item.excerpt.encode()),
            'excerpt_sha256': digest(item.excerpt.encode())})
    require(any(item['symbol'] == 'valid_signature' and item['start_line'] == 6
                and item['end_line'] == 8 for item in metadata), 'fixture_label_missing')
    payload = build_responses_payload(request, OUTPUT_LIMIT)
    raw = canonical(payload)
    user_data = json.loads(payload['input'][0]['content'])
    manifest = {'version': '5b2b-disclosure-v1', 'fixture_id': CASE_ID,
        'dataset_sha256': DATASET_HASH, 'source_commit': COMMIT, 'source_tree': TREE,
        'source_blob': file.blob_sha, 'source_sha256': digest(source),
        'repository': REPOSITORY, 'repository_id': data.repository_id,
        'investigation_id': data.investigation_id, 'report_job_id': job_id,
        'experiment_id': experiment_id, 'snapshot_id': data.snapshot_id,
        'request_sha256': digest(raw), 'request_bytes': len(raw),
        'request_byte_limit': MAX_REQUEST_BYTES, 'actual_pricing_state': 'blocked_unverified',
        'instructions_sha256': digest(payload['instructions'].encode()),
        'output_schema_sha256': digest(canonical(payload['text']['format']['schema'])),
        'input_fields': sorted(user_data),
        'issue_title_bytes': len(data.title.encode()), 'issue_title_sha256': digest(data.title.encode()),
        'issue_body_bytes': len(data.body.encode()), 'issue_body_sha256': digest(data.body.encode()),
        'label_count': len(data.labels), 'comment_count': len(data.comments), 'evidence': metadata,
        'model': MODEL, 'provider': 'openai', 'service_tier': 'default',
        'http_metadata': {'client_request_id': job_id,
            'explicit_headers': ['Authorization', 'Content-Type', 'OpenAI-Organization', 'OpenAI-Project',
                                 'X-Client-Request-Id'],
            'authorization_value': 'server-side credential omitted',
            'account_project_values': 'server-side identifiers bound by the provider-count record',
            'automatic_transport_headers': ['Host', 'Content-Length', 'Accept', 'Accept-Encoding',
                                            'Connection', 'User-Agent']},
        'prompt_cache_options': {'ttl': '30m'}, 'store': False, 'truncation': 'disabled',
        'tools': [], 'output_format': 'strict_json_schema', 'max_output_tokens': OUTPUT_LIMIT,
        'heuristic_request_bytes_div_4': (len(raw) + 3) // 4,
        'token_estimate_note': 'Byte/4 heuristic only; not a verified token count or billing bound.',
        'reservation_input_tokens': INPUT_WINDOW, 'reservation_microusd': upper_cost(INPUT_WINDOW, OUTPUT_LIMIT),
        'redactions': ['Source literals, comments, numeric literals and sensitive identifiers are sanitized.',
                       'Issue sensitive patterns are omitted; issue retrieval time is omitted.'],
        'disclosure_risks': ['Screening is incomplete; sanitized source still leaves the machine.',
                             'Provider retention and billing depend on account terms.'],
        'omitted_eligible_files': omitted}
    return payload, manifest


def create_fake_approval(factory, *, experiment_id, job_id, manifest, expires_at):
    """Create a simulated test approval, never an actual paid approval."""
    require_fake_configuration()
    isolated_port(factory)
    if (not canonical_id(experiment_id) or not canonical_id(job_id)
            or manifest.get('experiment_id') != experiment_id or manifest.get('report_job_id') != job_id
            or not re.fullmatch(r'[0-9a-f]{64}', manifest.get('request_sha256', ''))
            or utc(expires_at) <= now()):
        raise ModelError('approval_invalid')
    with factory.begin() as db:
        job = db.scalar(select(InvestigationReportJob).where(InvestigationReportJob.id == job_id).with_for_update())
        selection = db.get(InvestigationProviderSelection, job_id)
        exp = db.scalar(select(InvestigationExperiment).where(
            InvestigationExperiment.id == experiment_id).with_for_update())
        if (not job or job.status != 'queued' or not selection or not exp
                or selection.experiment_id != experiment_id or selection.tenant_id != job.tenant_id
                or exp.tenant_id != job.tenant_id or not exp.enabled or exp.mode != 'simulated'
                or exp.provider != 'openai' or exp.model != MODEL or exp.max_concurrent != 1
                or exp.max_requests != 1 or exp.max_input_tokens != INPUT_WINDOW
                or exp.max_output_tokens != OUTPUT_LIMIT or exp.budget_microusd > 10_000_000
                or exp.investigation_budget_microusd > 6_000_000
                or job.snapshot_id != manifest.get('snapshot_id')
                or manifest.get('source_commit') != COMMIT or manifest.get('fixture_id') != CASE_ID
                or utc(expires_at) > utc(exp.expires_at)):
            raise ModelError('approval_invalid')
        if db.scalar(select(InvestigationExecutorApproval.id).where(or_(
                InvestigationExecutorApproval.job_id == job_id,
                InvestigationExecutorApproval.experiment_id == experiment_id))):
            raise ModelError('approval_invalid')
        approval = InvestigationExecutorApproval(id=str(uuid4()), job_id=job_id, experiment_id=experiment_id,
            tenant_id=job.tenant_id, snapshot_id=job.snapshot_id, source_commit=COMMIT, fixture_id=CASE_ID,
            mode='simulated', provider='openai', model=MODEL, request_sha256=manifest['request_sha256'],
            manifest_sha256=digest(canonical(manifest)), state='ready', expires_at=expires_at)
        db.add(approval)
        db.flush()
        return approval.id


class _ApprovalBoundModel:
    """Bind an adapter request to an approval consumed with the ledger send marker."""
    mode = ''

    def _bind(self, *, root, experiment_id, job_id, approval_id, manifest_sha256):
        if (not all(canonical_id(value) for value in (experiment_id, job_id, approval_id))
                or not isinstance(manifest_sha256, str)
                or not re.fullmatch(r'[0-9a-f]{64}', manifest_sha256)):
            raise ModelError('approval_invalid')
        self.root, self.experiment_id, self.job_id = Path(root), experiment_id, job_id
        self.approval_id, self.manifest_sha256 = approval_id, manifest_sha256

    def _generate_reserved(self, request, *, factory, job_id, lease, reservation_id):
        isolated_port(factory)
        if self.mode == 'actual' and factory.kw['bind'].dialect.name != 'postgresql':
            raise ModelError('approval_invalid')
        if (job_id != self.job_id or self.mode == 'simulated'
                and type(self._transport) is not httpx.MockTransport):
            raise ModelError('approval_invalid')
        request = normalized(request)
        try:
            generation, manifest = disclosure(self.root, request, experiment_id=self.experiment_id, job_id=job_id)
        except (ValueError, OSError):
            raise ModelError('approval_invalid') from None
        if digest(canonical(manifest)) != self.manifest_sha256:
            raise ModelError('approval_invalid')
        self._expected_request_sha256 = manifest['request_sha256']
        self._current_manifest, self._current_generation = manifest, generation
        return super()._generate_reserved(request, factory=factory, job_id=job_id, lease=lease,
                                          reservation_id=reservation_id)

    def _mark_sent(self, factory, job_id, lease, reservation_id, payload):
        request_hash = digest(canonical(payload))
        count_binding = getattr(self, '_count_binding', None)
        if self.mode == 'actual' and count_binding is None:
            raise ModelError('count_approval_invalid')
        def lock_count_access(db, job):
            # Reconstruct against locked current source/access before the send marker.
            from app.evaluation.token_counting import _lock_access
            _lock_access(db, job.id, job.tenant_id)
            generation, manifest = prepare_review(factory, self.root, experiment_id=self.experiment_id,
                                                   job_id=job_id, session=db, expected_status='running')
            if generation != self._current_generation or manifest != self._current_manifest:
                raise ModelError('count_approval_invalid')

        def consume(db, job, exp, reservation):
            approval = db.scalar(select(InvestigationExecutorApproval).where(
                InvestigationExecutorApproval.id == self.approval_id).with_for_update())
            if (not approval or approval.state != 'ready' or utc(approval.expires_at) <= now()
                    or approval.job_id != job_id or approval.experiment_id != self.experiment_id
                    or approval.tenant_id != job.tenant_id or approval.snapshot_id != job.snapshot_id
                    or approval.source_commit != COMMIT or approval.fixture_id != CASE_ID
                    or approval.mode != self.mode or approval.provider != 'openai' or approval.model != MODEL
                    or approval.request_sha256 != request_hash or request_hash != self._expected_request_sha256
                    or approval.manifest_sha256 != self.manifest_sha256
                    or exp.id != self.experiment_id or exp.mode != self.mode
                    or exp.max_requests != 1 or exp.max_concurrent != 1
                    or exp.budget_microusd > 10_000_000 or exp.investigation_budget_microusd > 6_000_000
                    or reservation.mode != self.mode):
                raise ModelError('approval_invalid')
            if self.mode == 'actual':
                require_verified_actual_pricing()
                database = db.execute(text('select current_database()')).scalar_one()
                revision = db.execute(text('select version_num from alembic_version')).scalar_one()
                if database != db.bind.url.database or revision != '0013':
                    raise ModelError('approval_invalid')
            if count_binding is not None:
                count_id, account, project = count_binding
                if self.mode == 'actual':
                    from app.evaluation.token_counting import validate_locked_provider_count
                    count = validate_locked_provider_count(db, count_id=count_id, job=job, exp=exp,
                        generation=self._current_generation, manifest=self._current_manifest,
                        account=account, project=project, snapshot_id=job.snapshot_id)
                    require_stress_capacity(reservation.reserved_microusd + count.fee_reserved_microusd,
                                            exp.investigation_budget_microusd, exp.budget_microusd)
                    count.status, count.consumed_at, count.generation_approval_id = 'consumed', now(), approval.id
                elif self.mode == 'simulated':
                    from app.evaluation.token_counting import count_projection, validate_locked_fake_count
                    validate_locked_fake_count(db, count_id=count_id, job=job, exp=exp,
                        generation=self._current_generation, manifest=self._current_manifest,
                        projection=count_projection(self._current_generation), account=account, project=project,
                        snapshot_id=job.snapshot_id)
                else:
                    raise ModelError('approval_invalid')
            approval.state, approval.consumed_at = 'consumed', now()
        return mark_sent(factory, job_id, lease, reservation_id, before_mark=consume,
                         before_selection=lock_count_access if count_binding is not None else None)


class ApprovedFakeModel(_ApprovalBoundModel, OpenAIInvestigationModel):
    """The existing adapter with a one-use, simulated approval and fake transport."""
    mode = 'simulated'

    def __init__(self, *, root, experiment_id, job_id, approval_id, manifest_sha256, transport):
        if type(transport) is not httpx.MockTransport:
            raise ModelError('approval_invalid')
        OpenAIInvestigationModel.__init__(self, 'synthetic-fake-only-key', transport=transport)
        self._bind(root=root, experiment_id=experiment_id, job_id=job_id,
                   approval_id=approval_id, manifest_sha256=manifest_sha256)


class ApprovedLiveModel(_ApprovalBoundModel, OpenAIInvestigationModel):
    """A separately approved actual request; never enabled by the ordinary worker."""
    mode = 'actual'

    def __init__(self, *, root, experiment_id, job_id, approval_id, manifest_sha256, api_key, transport=None,
                 count_id=None, account=None, project=None):
        if not api_key or transport is not None and type(transport) is not httpx.MockTransport:
            raise ModelError('approval_invalid')
        OpenAIInvestigationModel.__init__(self, api_key, transport=transport)
        self._bind(root=root, experiment_id=experiment_id, job_id=job_id,
                   approval_id=approval_id, manifest_sha256=manifest_sha256)
        self._organization, self._project = account, project
        if count_id is not None:
            if not canonical_id(count_id) or count_id == approval_id or not account or not project:
                raise ModelError('count_approval_invalid')
            self._count_binding = (count_id, account, project)


def execute_fake(factory, *, root, job_id, experiment_id, approval_id, manifest, transport, github,
                 count_id=None, count_account=None, count_project=None):
    """Run the existing report worker with a simulated approval and network fence."""
    from app.modules.investigation.report_worker import process_report
    require_fake_configuration()
    if type(transport) is not httpx.MockTransport:
        raise ModelError('approval_invalid')
    port = isolated_port(factory)
    manifest_hash = digest(canonical(manifest))
    with factory() as db:
        row = db.get(InvestigationExecutorApproval, approval_id)
        if (not row or row.state != 'ready' or utc(row.expires_at) <= now() or row.job_id != job_id
                or row.experiment_id != experiment_id or row.manifest_sha256 != manifest_hash):
            raise ModelError('approval_invalid')
        tenant_id, snapshot_id = row.tenant_id, row.snapshot_id
    if count_id is not None:
        if not canonical_id(count_id) or count_id == approval_id or not count_account or not count_project:
            raise ModelError('approval_invalid')
        from app.evaluation.token_counting import validate_fake_count_for_generation
        validate_fake_count_for_generation(factory, root, count_id=count_id, job_id=job_id,
            experiment_id=experiment_id, tenant_id=tenant_id, account=count_account, project=count_project,
            snapshot_id=snapshot_id)
    elif count_account is not None or count_project is not None:
        raise ModelError('approval_invalid')
    model = ApprovedFakeModel(root=root, experiment_id=experiment_id, job_id=job_id, approval_id=approval_id,
                              manifest_sha256=manifest_hash, transport=transport)
    if count_id is not None:
        model._count_binding = (count_id, count_account, count_project)
    try:
        # The socket fence patches process-global functions; serialize its use in this process.
        with _NETWORK_FENCE_LOCK, network_fence(port):
            process_report(job_id, factory, github, model)
    finally:
        # A used object cannot be reused even if the caller retains a reference.
        model._transport = None


def template(root):
    """Build a deterministic local preview with placeholder IDs, never an approval."""
    _, case, _, chunks, _, _ = load_fixture(root)
    snapshot = '11111111-1111-4111-8111-111111111111'
    investigation = '22222222-2222-4222-8222-222222222222'
    evidence = []
    for index, chunk in enumerate(sorted(chunks, key=lambda x: x.symbol is None)):
        evidence.append({'chunk_id': f'{index + 3:08d}-3333-4333-8333-333333333333',
            'path': EXPECTED_PATH, 'symbol': chunk.symbol, 'start_line': chunk.start_line,
            'end_line': chunk.end_line, 'citation': github_citation(REPOSITORY, COMMIT, EXPECTED_PATH,
                chunk.start_line, chunk.end_line), 'source_text': chunk.text})
    package = build_package(investigation_id=investigation, repository_id=902, issue_id=990, issue_number=5,
        context={'title': case['title'], 'body': case['body'], 'labels': [], 'comments': [],
                 'state': 'open', 'created_at': '2026-01-01T00:00:00Z',
                 'updated_at': '2026-01-01T00:00:00Z', 'truncation': {}},
        snapshot_id=snapshot, commit_sha=COMMIT, evidence=evidence)
    return disclosure(root, model_request(package), experiment_id='55555555-5555-4555-8555-555555555555',
                      job_id='66666666-6666-4666-8666-666666666666')


def write_private(directory, payload, manifest):
    flags = os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    directory_fd = os.open(directory, flags)
    try:
        info = os.fstat(directory_fd)
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid()
                and stat.S_IMODE(info.st_mode) == 0o700, 'review_directory_not_private')
        for name, value in (('request.json', payload), ('manifest.json', manifest)):
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0),
                         0o600, dir_fd=directory_fd)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(canonical(value))
    finally:
        os.close(directory_fd)


def read_private(directory, root, *, experiment_id, job_id):
    """Read and independently reconstruct an exact reviewed request without printing it."""
    flags = os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    directory_fd = os.open(directory, flags)
    try:
        info = os.fstat(directory_fd)
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid()
                and stat.S_IMODE(info.st_mode) == 0o700, 'review_directory_not_private')
        values = []
        for name, limit in (('request.json', MAX_REQUEST_BYTES), ('manifest.json', 32_000)):
            fd = os.open(name, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0), dir_fd=directory_fd)
            with os.fdopen(fd, 'rb') as stream:
                info = os.fstat(stream.fileno())
                require(stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid()
                        and stat.S_IMODE(info.st_mode) == 0o600 and info.st_size <= limit,
                        'review_file_not_private')
                raw = stream.read(limit + 1)
            def unique(pairs):
                output = {}
                for key, value in pairs:
                    require(key not in output, 'review_duplicate_key')
                    output[key] = value
                return output
            value = json.loads(raw, object_pairs_hook=unique,
                               parse_constant=lambda _: (_ for _ in ()).throw(ValueError('invalid_number')))
            require(raw == canonical(value), 'review_not_canonical')
            values.append(value)
    finally:
        os.close(directory_fd)
    payload, manifest = values
    try:
        data = json.loads(payload['input'][0]['content'], object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError('invalid_number')))
        data['evidence'] = tuple(EvidenceInput(**item) for item in data['evidence'])
        data['labels'], data['comments'] = tuple(data['labels']), tuple(data['comments'])
        request = ModelRequest(REPORT_INSTRUCTIONS, InvestigationInput(**data))
        rebuilt_payload, rebuilt_manifest = disclosure(root, request, experiment_id=experiment_id, job_id=job_id)
    except (KeyError, IndexError, TypeError, AttributeError, ModelError):
        raise ValueError('invalid_review') from None
    require(payload == rebuilt_payload and manifest == rebuilt_manifest, 'review_mismatch')
    return payload, manifest


def prepare_review(factory, root, *, experiment_id, job_id, session=None, expected_status='queued'):
    """Read an isolated synthetic job and derive its exact prospective model request."""
    from app.core.config import get_settings
    from app.domain.models import AuthSession, CodeSnapshot, Installation, InvestigationJob, Membership
    from app.modules.github.issue_context import build_context
    from app.modules.investigation.reporting import evidence_inputs
    isolated_port(factory)
    if expected_status not in ('queued', 'running') or expected_status == 'running' and session is None:
        raise ModelError('approval_invalid')
    _, case, _, _, _, _ = load_fixture(root)
    issue = {'id': 990, 'number': 5, 'title': case['title'], 'body': case['body'], 'state': 'open',
             'created_at': '2026-01-01T00:00:00Z', 'updated_at': '2026-01-01T00:00:00Z',
             'comments': 0, 'labels': []}
    with nullcontext(session) if session is not None else factory() as db:
        job = db.get(InvestigationReportJob, job_id)
        selection = db.get(InvestigationProviderSelection, job_id)
        exp = db.get(InvestigationExperiment, experiment_id)
        parent = db.get(InvestigationJob, job.investigation_id) if job else None
        snapshot = db.get(CodeSnapshot, job.snapshot_id) if job else None
        repo = db.get(Repository, job.repository_id) if job else None
        user = db.get(User, job.user_id) if job else None
        session = db.get(AuthSession, job.session_hash) if job else None
        installation = db.get(Installation, repo.installation_id) if repo else None
        if (not job or job.status != expected_status or not selection or selection.experiment_id != experiment_id
                or selection.tenant_id != job.tenant_id or selection.repository_id != job.repository_id
                or not exp or not experiment_is_eligible(exp, job.tenant_id)
                or exp.max_requests != 1 or exp.max_concurrent != 1 or exp.max_output_tokens != OUTPUT_LIMIT
                or exp.budget_microusd > 10_000_000 or exp.investigation_budget_microusd > 6_000_000
                or not session or session.revoked_at is not None or utc(session.expires_at) <= now()
                or session.user_id != job.user_id or session.tenant_id != job.tenant_id
                or not db.get(Membership, (job.tenant_id, job.user_id))
                or not repo or not repo.enabled or repo.tenant_id != job.tenant_id
                or repo.id != 902 or repo.full_name != REPOSITORY or repo.installation_id != 901
                or not installation or not installation.active or installation.tenant_id != job.tenant_id
                or not user or user.github_user_id != 77 or not parent or parent.issue_id != 990
                or parent.status != 'completed' or parent.operation != 'code_evidence'
                or parent.user_id != job.user_id or parent.tenant_id != job.tenant_id
                or parent.repository_id != job.repository_id
                or parent.issue_number != 5 or parent.snapshot_id != job.snapshot_id
                or parent.snapshot_commit_sha != COMMIT or parent.source_repository_name != REPOSITORY
                or utc(parent.issue_updated_at) != datetime(2026, 1, 1, tzinfo=timezone.utc)
                or not snapshot or not snapshot.published or snapshot.commit_sha != COMMIT
                or snapshot.tenant_id != job.tenant_id or snapshot.repository_id != job.repository_id):
            raise ModelError('approval_invalid')
        evidence = evidence_inputs(db, parent, snapshot)
        context = build_context(issue, [], 902, REPOSITORY, 5, get_settings())
        package = build_package(investigation_id=parent.id, repository_id=902, issue_id=990, issue_number=5,
            context=context, snapshot_id=snapshot.id, commit_sha=COMMIT, evidence=evidence)
    return disclosure(root, model_request(package), experiment_id=experiment_id, job_id=job_id)


def record_live_approval(factory, root, *, experiment_id, job_id, directory, request_hash, manifest_hash,
                         screening_acknowledged=False, pricing_acknowledged=False,
                         count_id=None, account=None, project=None):
    """Record a separate generation approval only for a verified provider count."""
    from app.core.config import get_settings
    from app.domain.models import InvestigationRealReport, InvestigationReport, InvestigationUsageReservation
    from app.evaluation.disclosure_screen import screen_exact
    if not screening_acknowledged or not pricing_acknowledged:
        raise ModelError('approval_invalid')
    require_verified_actual_pricing()
    require_fake_configuration(allow_provider_identity=True)  # Registration never enables a paid provider.
    settings = get_settings()
    if (factory.kw['bind'].dialect.name != 'postgresql' or settings.app_env != 'test'
            or settings.embedding_provider != 'disabled' or settings.embedding_allow_paid
            or settings.investigation_provider != 'mock' or settings.investigation_real_enabled
            or settings.investigation_paid_background_enabled
            or settings.investigation_openai_api_key.get_secret_value()):
        raise ModelError('approval_invalid')
    port = isolated_port(factory)
    with _NETWORK_FENCE_LOCK, network_fence(port):
        payload, manifest = read_private(directory, root, experiment_id=experiment_id, job_id=job_id)
        screen_exact(root, payload, manifest)
        if request_hash != digest(canonical(payload)) or manifest_hash != digest(canonical(manifest)):
            raise ModelError('approval_invalid')
        prospective_payload, prospective_manifest = prepare_review(factory, root,
            experiment_id=experiment_id, job_id=job_id)
        if payload != prospective_payload or manifest != prospective_manifest:
            raise ModelError('approval_invalid')
        with factory.begin() as db:
            from app.evaluation.token_counting import _lock_access, validate_locked_provider_count
            initial = db.get(InvestigationReportJob, job_id)
            if not initial:
                raise ModelError('approval_invalid')
            job, _ = _lock_access(db, job_id, initial.tenant_id)
            selection = db.get(InvestigationProviderSelection, job_id)
            exp = db.scalar(select(InvestigationExperiment).where(
                InvestigationExperiment.id == experiment_id).with_for_update())
            if (not job or job.status != 'queued' or not selection or selection.experiment_id != experiment_id
                    or not exp or exp.mode not in ('simulated', 'actual') or not experiment_is_eligible(exp, job.tenant_id)
                    or exp.max_requests != 1 or exp.max_concurrent != 1 or exp.max_output_tokens != OUTPUT_LIMIT
                    or exp.budget_microusd > 10_000_000 or exp.investigation_budget_microusd > 6_000_000
                    or manifest['snapshot_id'] != job.snapshot_id):
                raise ModelError('approval_invalid')
            require_stress_capacity(upper_cost(exp.max_input_tokens, exp.max_output_tokens),
                                    exp.investigation_budget_microusd, exp.budget_microusd)
            if not canonical_id(count_id) or not account or not project or exp.mode != 'actual':
                raise ModelError('count_approval_invalid')
            current_payload, current_manifest = prepare_review(factory, root, experiment_id=experiment_id,
                                                                job_id=job_id, session=db)
            if current_payload != payload or current_manifest != manifest:
                raise ModelError('approval_invalid')
            count = validate_locked_provider_count(db, count_id=count_id, job=job, exp=exp, generation=payload,
                manifest=manifest, account=account, project=project, snapshot_id=job.snapshot_id)
            require_stress_capacity(upper_cost(exp.max_input_tokens, exp.max_output_tokens) + count.fee_reserved_microusd,
                                    exp.investigation_budget_microusd, exp.budget_microusd)
            if db.scalar(select(InvestigationExecutorApproval.id).where(or_(
                    InvestigationExecutorApproval.job_id == job_id,
                    InvestigationExecutorApproval.experiment_id == experiment_id))):
                raise ModelError('approval_invalid')
            if (db.scalar(select(InvestigationUsageReservation.id).where(
                    InvestigationUsageReservation.experiment_id == experiment_id))
                    or db.scalar(select(InvestigationRealReport.id).where(
                        InvestigationRealReport.report_job_id == job_id))
                    or db.scalar(select(InvestigationReport.id).where(
                        InvestigationReport.report_job_id == job_id))):
                raise ModelError('approval_invalid')
            # The count authorization is separate and already consumed by the count send.
            approval = InvestigationExecutorApproval(id=str(uuid4()), job_id=job_id, experiment_id=experiment_id,
                tenant_id=job.tenant_id, snapshot_id=job.snapshot_id, source_commit=COMMIT, fixture_id=CASE_ID,
                mode='actual', provider='openai', model=MODEL, request_sha256=request_hash,
                manifest_sha256=manifest_hash, state='ready', expires_at=min(utc(exp.expires_at), now() + timedelta(minutes=15)))
            db.add(approval)
            db.flush()
            return approval.id


class SyntheticGitHub:
    """Only the pinned synthetic identity and issue; never contacts GitHub."""
    def __init__(self, root, app_id):
        _, case, _, _, _, _ = load_fixture(root)
        self.case, self.app_id = case, app_id

    def installations(self, token):
        return [{'id': 901, 'app_id': self.app_id, 'account': {'id': 77, 'type': 'User'}, 'suspended_at': None}]

    def repositories(self, token, installation_id):
        return [{'id': 902, 'full_name': REPOSITORY, 'private': False}] if installation_id == 901 else []

    def issue(self, token, name, number):
        if name != REPOSITORY or number != 5:
            raise ModelError('issue_unavailable')
        return {'id': 990, 'number': 5, 'title': self.case['title'], 'body': self.case['body'], 'state': 'open',
                'created_at': '2026-01-01T00:00:00Z', 'updated_at': '2026-01-01T00:00:00Z',
                'comments': 0, 'labels': []}

    def issue_comments(self, token, name, number, count):
        return []


def execute_live(factory, root, *, experiment_id, job_id, approval_id, directory, count_id=None):
    """Explicit one-shot entry point; requires a separately recorded actual approval."""
    from app.core.config import get_settings
    from app.modules.investigation.reporting_config import real_executor_enabled
    from app.modules.investigation.report_worker import process_report
    require_verified_actual_pricing()
    port = isolated_port(factory)
    if factory.kw['bind'].dialect.name != 'postgresql':
        raise ModelError('approval_invalid')
    settings = get_settings()
    account = settings.investigation_openai_organization.get_secret_value()
    project = settings.investigation_openai_project.get_secret_value()
    if (settings.app_env != 'test' or settings.embedding_provider != 'disabled' or settings.embedding_allow_paid
            or not real_executor_enabled(settings) or settings.investigation_experiment_id != experiment_id
            or not canonical_id(count_id) or count_id == approval_id or not account or not project):
        raise ModelError('model_not_enabled')
    with _NETWORK_FENCE_LOCK, network_fence(port):
        _, manifest = read_private(directory, root, experiment_id=experiment_id, job_id=job_id)
        with factory() as db:
            approval = db.get(InvestigationExecutorApproval, approval_id)
            if (not approval or approval.mode != 'actual' or approval.state != 'ready'
                    or utc(approval.expires_at) <= now() or approval.job_id != job_id
                    or approval.experiment_id != experiment_id
                    or approval.manifest_sha256 != digest(canonical(manifest))):
                raise ModelError('approval_invalid')
            tenant_id, snapshot_id = approval.tenant_id, approval.snapshot_id
        from app.evaluation.token_counting import validate_provider_count_for_generation
        validate_provider_count_for_generation(factory, root, count_id=count_id, job_id=job_id,
            experiment_id=experiment_id, tenant_id=tenant_id, account=account, project=project,
            snapshot_id=snapshot_id)
        github = SyntheticGitHub(root, settings.github_app_id)
    model = ApprovedLiveModel(root=root, experiment_id=experiment_id, job_id=job_id, approval_id=approval_id,
        manifest_sha256=digest(canonical(manifest)), api_key=settings.investigation_openai_api_key.get_secret_value(),
        count_id=count_id, account=account, project=project)
    try:
        process_report(job_id, factory, github, model)
    finally:
        model._api_key = ''
        model._organization, model._project = '', ''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--dry-run', action='store_true', help='offline template with placeholder identifiers')
    action.add_argument('--review-job', action='store_true', help='review a previously prepared synthetic job')
    action.add_argument('--record-live-approval', action='store_true', help='record a separately approved request')
    action.add_argument('--live', action='store_true', help='execute one separately approved request')
    parser.add_argument('--experiment-id')
    parser.add_argument('--job-id')
    parser.add_argument('--approval-id')
    parser.add_argument('--provider-count-id')
    parser.add_argument('--review-directory')
    parser.add_argument('--confirm-request-sha256')
    parser.add_argument('--confirm-manifest-sha256')
    parser.add_argument('--acknowledge-external-disclosure', action='store_true')
    parser.add_argument('--acknowledge-source-screening', action='store_true')
    parser.add_argument('--acknowledge-account-pricing', action='store_true')
    parser.add_argument('--acknowledge-one-paid-request', action='store_true')
    args = parser.parse_args()
    if not __debug__:
        raise SystemExit('Optimized Python is not permitted.')
    # The Git subprocess must not fetch missing objects or use configured helpers.
    os.environ.update(GIT_TERMINAL_PROMPT='0', GIT_NO_LAZY_FETCH='1', GIT_ALLOW_PROTOCOL='',
                      GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                      GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='protocol.allow', GIT_CONFIG_VALUE_0='never')
    root = Path(__file__).resolve().parents[4]
    if args.dry_run:
        try:
            require_fake_configuration()
            with _NETWORK_FENCE_LOCK, network_fence(0):
                payload, manifest = template(root)
                directory = tempfile.mkdtemp(prefix='repopilot-5b2b-review-')
                write_private(directory, payload, manifest)
        except Exception:
            raise SystemExit('Offline preview failed; no request was sent.') from None
        print(f'Offline template only; no approval or provider request. Private review directory: {directory}')
        print(f'Request SHA-256: {manifest["request_sha256"]}; manifest SHA-256: {digest(canonical(manifest))}')
        return
    if not canonical_id(args.experiment_id) or not canonical_id(args.job_id):
        parser.error('A canonical experiment ID and report job ID are required.')
    if args.record_live_approval and (not args.review_directory or not args.acknowledge_external_disclosure
            or not args.acknowledge_source_screening or not args.acknowledge_account_pricing
            or not args.confirm_request_sha256 or not args.confirm_manifest_sha256
            or not canonical_id(args.provider_count_id)):
        parser.error('Approval requires a provider count, reviewed hashes and explicit review acknowledgements.')
    if args.live and (not args.review_directory or not canonical_id(args.approval_id)
                      or not canonical_id(args.provider_count_id) or not args.acknowledge_one_paid_request):
        parser.error('Live execution requires the private review, recorded approval ID and paid-request acknowledgement.')
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    engine = None
    try:
        # Validate the exact disposable target before connecting or changing any state.
        engine = create_engine(os.environ['DATABASE_URL'], hide_parameters=True)
        factory = sessionmaker(engine, expire_on_commit=False)
        port = isolated_port(factory)
        if engine.dialect.name != 'postgresql':
            raise ModelError('approval_invalid')
        with _NETWORK_FENCE_LOCK, network_fence(port), engine.connect() as db:
            name = db.execute(text('select current_database()')).scalar_one()
            revision = db.execute(text('select version_num from alembic_version')).scalar_one()
            if name != engine.url.database or revision != '0013':
                raise ModelError('approval_invalid')
        if args.review_job:
            require_fake_configuration()
            with _NETWORK_FENCE_LOCK, network_fence(port):
                payload, manifest = prepare_review(factory, root, experiment_id=args.experiment_id, job_id=args.job_id)
                directory = tempfile.mkdtemp(prefix='repopilot-5b2b-review-')
                write_private(directory, payload, manifest)
            print(f'No provider request sent. Private review directory: {directory}')
            print(f'Request SHA-256: {manifest["request_sha256"]}; manifest SHA-256: {digest(canonical(manifest))}')
        elif args.record_live_approval:
            from app.core.config import get_settings
            settings = get_settings()
            approval = record_live_approval(factory, root, experiment_id=args.experiment_id, job_id=args.job_id,
                directory=args.review_directory, request_hash=args.confirm_request_sha256,
                manifest_hash=args.confirm_manifest_sha256, screening_acknowledged=args.acknowledge_source_screening,
                pricing_acknowledged=args.acknowledge_account_pricing, count_id=args.provider_count_id,
                account=settings.investigation_openai_organization.get_secret_value(),
                project=settings.investigation_openai_project.get_secret_value())
            print(f'One-use approval recorded: {approval}. No provider request sent.')
        else:
            logging.getLogger('httpx').setLevel(logging.WARNING)
            execute_live(factory, root, experiment_id=args.experiment_id, job_id=args.job_id,
                         approval_id=args.approval_id, directory=args.review_directory, count_id=args.provider_count_id)
            with factory() as db:
                job = db.get(InvestigationReportJob, args.job_id)
                print(f'Experiment worker state: {job.status if job else "unavailable"}.')
    except Exception:
        raise SystemExit('Executor did not complete; inspect the disposable ledger before any further action.') from None
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == '__main__':
    # Use the canonical module's class identities when invoked with ``python -m``.
    # The adapter's live-transport guard intentionally checks that exact class.
    from app.evaluation.experiment_executor import main as canonical_main
    canonical_main()
