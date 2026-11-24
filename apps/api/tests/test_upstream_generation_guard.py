from uuid import uuid4

import pytest

from app.domain.models import InvestigationJob, PatchOutbox, PatchProposal
from app.modules.patches.worker import process_patch
from test_auth_enrollment import csrf, github_auth as github_auth
from test_patch_proposals import create, enable, parent_setup, proposal_root


def test_upstream_route_blocks_before_any_provider_probe(client, factory, github_auth, monkeypatch):
    parent, _, _ = parent_setup(client, factory, github_auth, monkeypatch)
    enable(monkeypatch)
    with factory.begin() as db:
        db.get(InvestigationJob, parent).issue_origin_repository_id = 222
    monkeypatch.setattr("app.modules.patches.routes.get_candidate_provider", lambda: pytest.fail("provider queried"))
    listed = client.get(proposal_root(parent))
    assert listed.status_code == 200 and listed.json()["available"] is False
    response = client.post(proposal_root(parent), json={"request_id": str(uuid4())}, headers=csrf(client))
    assert response.status_code == 409


def test_replayed_upstream_worker_delivery_cannot_invoke_provider(client, factory, github_auth, monkeypatch):
    parent, _, _ = parent_setup(client, factory, github_auth, monkeypatch)
    enable(monkeypatch)
    proposal = create(client, parent)
    with factory.begin() as db:
        db.get(InvestigationJob, parent).issue_origin_repository_id = 222
    class Never:
        def generate(self, *args, **kwargs):
            pytest.fail("upstream source reached provider")
    process_patch(proposal, factory, github_auth, Never())
    with factory() as db:
        task = db.get(PatchProposal, proposal)
        assert task.status == "failed" and task.error_code == "upstream_inference_approval_required"
        assert task.diff is None and db.get(PatchOutbox, proposal).status == "processed"


def test_scoped_partial_route_blocks_before_provider_probe(client, factory, github_auth, monkeypatch):
    from types import SimpleNamespace

    parent, _, _ = parent_setup(client, factory, github_auth, monkeypatch)
    enable(monkeypatch)
    def partial_access(db, *args, **kwargs):
        return db.get(InvestigationJob, parent), SimpleNamespace(inventory_coverage="PARTIAL_INVENTORY")
    monkeypatch.setattr("app.modules.patches.routes._access", partial_access)
    monkeypatch.setattr("app.modules.patches.routes.get_candidate_provider", lambda: pytest.fail("provider queried"))
    assert client.get(proposal_root(parent)).json()["available"] is False
    assert client.post(proposal_root(parent), json={"request_id": str(uuid4())}, headers=csrf(client)).status_code == 409


def test_replayed_partial_worker_delivery_cannot_invoke_provider(client, factory, github_auth, monkeypatch):
    from app.domain.models import CodeSnapshot

    parent, snapshot_id, _ = parent_setup(client, factory, github_auth, monkeypatch)
    enable(monkeypatch)
    proposal = create(client, parent)
    with factory.begin() as db:
        snapshot = db.get(CodeSnapshot, snapshot_id)
        snapshot.published = False
        snapshot.inventory_coverage = "PARTIAL_INVENTORY"
        snapshot.inventory_manifest = {"version": "synthetic"}
        snapshot.inventory_manifest_sha256 = "a" * 64
    class Never:
        def generate(self, *args, **kwargs):
            pytest.fail("partial source reached provider")
    process_patch(proposal, factory, github_auth, Never())
    with factory() as db:
        task = db.get(PatchProposal, proposal)
        assert task.status == "failed" and task.error_code == "upstream_inference_approval_required"
        assert task.diff is None and db.get(PatchOutbox, proposal).status == "processed"


@pytest.mark.parametrize("classification", ["upstream", "partial"])
def test_report_route_blocks_scoped_jobs_before_evidence_or_provider(client, factory, github_auth, monkeypatch, classification):
    from types import SimpleNamespace
    from test_investigation_reports import report_url, setup_parent

    parent, _, _ = setup_parent(client, factory, github_auth, monkeypatch)
    def scoped(db, *args, **kwargs):
        job = db.get(InvestigationJob, parent)
        if classification == "upstream":
            job.issue_origin_repository_id = 222
        return job, SimpleNamespace(inventory_coverage="PARTIAL_INVENTORY" if classification == "partial" else "UNKNOWN_INVENTORY")
    monkeypatch.setattr("app.modules.investigation.report_routes.parent_and_snapshot", scoped)
    monkeypatch.setattr("app.modules.investigation.report_routes.evidence_inputs", lambda *args: pytest.fail("evidence read before approval"))
    assert client.post(report_url(parent), headers=csrf(client)).status_code == 409


@pytest.mark.parametrize("classification", ["upstream", "partial"])
def test_replayed_report_worker_blocks_scoped_jobs_before_model(client, factory, github_auth, monkeypatch, classification):
    from app.domain.models import CodeSnapshot, InvestigationReportJob, InvestigationReportOutbox
    from app.modules.investigation.report_worker import process_report
    from test_investigation_reports import request_report, setup_parent

    parent, snapshot_id, _ = setup_parent(client, factory, github_auth, monkeypatch)
    task_id = request_report(client, parent)
    with factory.begin() as db:
        if classification == "upstream":
            db.get(InvestigationJob, parent).issue_origin_repository_id = 222
        else:
            snapshot = db.get(CodeSnapshot, snapshot_id)
            snapshot.published = False
            snapshot.inventory_coverage = "PARTIAL_INVENTORY"
            snapshot.inventory_manifest = {"version": "synthetic"}
            snapshot.inventory_manifest_sha256 = "a" * 64
    class Never:
        def __getattribute__(self, name):
            pytest.fail("scoped evidence reached model")
    process_report(task_id, factory, github_auth, Never())
    with factory() as db:
        task = db.get(InvestigationReportJob, task_id)
        assert task.status == "failed" and task.error_code == "scoped_inference_approval_required"
        assert db.get(InvestigationReportOutbox, task_id).status == "processed"


def test_patch_worker_rechecks_origin_after_claim_before_provider(client, factory, github_auth, monkeypatch):
    parent, _, _ = parent_setup(client, factory, github_auth, monkeypatch)
    enable(monkeypatch)
    proposal = create(client, parent)
    original = github_auth.issue
    def change_origin(*args, **kwargs):
        result = original(*args, **kwargs)
        with factory.begin() as db:
            db.get(InvestigationJob, parent).issue_origin_repository_id = 222
        return result
    github_auth.issue = change_origin
    class Never:
        def generate(self, *args, **kwargs):
            pytest.fail("scoped source reached provider")
    process_patch(proposal, factory, github_auth, Never())
    with factory() as db:
        task = db.get(PatchProposal, proposal)
        assert task.status == "failed" and task.error_code == "upstream_inference_approval_required"
        assert task.diff is None and db.get(PatchOutbox, proposal).status == "processed"


def test_report_worker_rechecks_origin_after_claim_before_model(client, factory, github_auth, monkeypatch):
    from app.domain.models import InvestigationReportJob, InvestigationReportOutbox
    from app.modules.investigation.report_worker import process_report
    from test_investigation_reports import request_report, setup_parent

    parent, _, _ = setup_parent(client, factory, github_auth, monkeypatch)
    task_id = request_report(client, parent)
    original = github_auth.issue
    def change_origin(*args, **kwargs):
        result = original(*args, **kwargs)
        with factory.begin() as db:
            db.get(InvestigationJob, parent).issue_origin_repository_id = 222
        return result
    github_auth.issue = change_origin
    class Never:
        def __getattribute__(self, name):
            pytest.fail("scoped source reached model")
    process_report(task_id, factory, github_auth, Never())
    with factory() as db:
        task = db.get(InvestigationReportJob, task_id)
        assert task.status == "cancelled" and task.error_code == "authorization_revoked"
        assert db.get(InvestigationReportOutbox, task_id).status == "processed"


def test_real_ollama_worker_is_blocked_without_durable_approval(client, factory, github_auth, monkeypatch):
    from app.modules.patches.ollama_provider import OllamaPatchProvider

    parent, _, _ = parent_setup(client, factory, github_auth, monkeypatch)
    enable(monkeypatch)
    proposal = create(client, parent)
    provider = OllamaPatchProvider("qwen2.5-coder:7b", "a" * 64, "http://127.0.0.1:11434", 10000, 10000)
    monkeypatch.setattr(provider, "generate", lambda *args, **kwargs: pytest.fail("real provider invoked"))
    process_patch(proposal, factory, github_auth, provider)
    with factory() as db:
        task = db.get(PatchProposal, proposal)
        assert task.status == "failed" and task.error_code == "inference_approval_required"
        assert task.diff is None and db.get(PatchOutbox, proposal).status == "processed"


def test_real_ollama_not_presented_as_available_without_durable_approval():
    from app.modules.patches.ollama_provider import OllamaPatchProvider
    from app.modules.patches.service import candidate_provider_status

    provider = OllamaPatchProvider("qwen2.5-coder:7b", "a" * 64, "http://127.0.0.1:11434", 10000, 10000)
    available, reason = candidate_provider_status(provider)
    assert available is False and "approval gate" in reason
