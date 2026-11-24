"""Synthetic origin/partial integration; no source execution or model calls."""
from copy import deepcopy
from hashlib import sha1, sha256

import pytest
from sqlalchemy import select

from app.domain.models import (CodeChunk, CodeSnapshot, InvestigationIssueOrigin, InvestigationJob,
                               PartialSnapshotScope, Repository)
from app.workers.tasks import process_investigation
from test_auth_enrollment import csrf, github_auth as github_auth
from app.modules.investigation.retrieval import Candidate, fingerprint_chunk, validate_snapshot
from test_issue_context import setup_issue

STAMP = "2026-01-01T00:00:00Z"
SOURCE = b"export function process_sync(): number {\n  return 1\n}\n"
BLOB = sha1(b"blob " + str(len(SOURCE)).encode() + b"\0" + SOURCE).hexdigest()
SHA = sha256(SOURCE).hexdigest()
BODY = "The synthetic process_sync function returns an incorrect value."
URL = "/v1/repositories/902/upstream-issues/5/investigations"


def setup(client, github):
    setup_issue(client, github)
    github.repository = lambda token, name: {"id": 902, "full_name": "alice/public", "private": False,
        "fork": True, "default_branch": "main", "parent": {"id": 903, "full_name": "bob/upstream", "private": False}}
    github.issue = lambda token, name, number: {"id": 990, "number": number, "title": "process_sync fails",
        "body": BODY, "state": "open", "created_at": STAMP, "updated_at": STAMP, "comments": 0,
        "labels": [], "html_url": f"https://github.com/bob/upstream/issues/{number}",
        "repository_url": "https://api.github.com/repos/bob/upstream"}
    github.commit = lambda token, name, ref: {"sha": "a" * 40}
    github.is_ancestor = lambda token, name, pin, head: pin == head == "a" * 40
    github.tree_file = lambda token, name, commit, path: {"path": path, "sha": BLOB, "size": len(SOURCE)}
    github.blob = lambda token, name, sha, size: SOURCE
    return {"parent_repository_id": 903, "issue_id": 990, "issue_body_sha256": sha256(BODY.encode()).hexdigest(),
        "commit_sha": "a" * 40, "branch": "main", "files": [{"path": "src/tasks.ts", "byte_length": len(SOURCE),
        "sha256": SHA, "git_blob_sha1": BLOB}]}


def test_upstream_partial_job_uses_true_origin_and_does_not_replace_published_snapshot(client, factory, github_auth, monkeypatch):
    payload = setup(client, github_auth)
    with factory.begin() as db:
        repo = db.get(Repository, 902)
        previous = CodeSnapshot(id="a" * 36, repository_id=902, tenant_id=repo.tenant_id,
                                commit_sha="b" * 40, published=True)
        db.add(previous)
    response = client.post(URL, json=payload, headers=csrf(client))
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]
    history = client.get("/v1/repositories/902/investigations")
    assert history.status_code == 200
    assert history.json()["items"][0]["issue_origin"]["repository"] == "bob/upstream"
    issue = client.get(f"/v1/repositories/902/investigations/{job_id}/upstream-context")
    assert issue.status_code == 200
    assert issue.json()["repository_id"] == "902" and issue.json()["issue_id"] == "990"
    assert issue.json()["url"] == "https://github.com/bob/upstream/issues/5"
    with factory() as db:
        job = db.get(InvestigationJob, job_id)
        origin = db.get(InvestigationIssueOrigin, job_id)
        scope = db.get(PartialSnapshotScope, job_id)
        snapshot = db.get(CodeSnapshot, job.snapshot_id)
        chunk = db.scalar(select(CodeChunk).where(CodeChunk.repository_id == 902,
            CodeChunk.tenant_id == job.tenant_id))
        assert (origin.origin_repository_name, origin.issue_id) == ("bob/upstream", 990)
        assert snapshot.inventory_coverage == "PARTIAL_INVENTORY" and snapshot.published is False
        assert scope.manifest_sha256 == snapshot.inventory_manifest_sha256
        assert db.get(CodeSnapshot, "a" * 36).published is True
        chunk_id = chunk.id
    def retrieve(_factory, **kwargs):
        with factory() as db:
            validate_snapshot(db, snapshot_id=kwargs["snapshot_id"], repository_id=kwargs["repository_id"],
                              tenant_id=kwargs["tenant_id"], commit=kwargs["commit"], job_id=kwargs["job_id"])
            chunk = db.get(CodeChunk, chunk_id)
            from app.domain.models import IndexedFile
            file = db.get(IndexedFile, chunk.file_id)
            query = kwargs["queries"][0]
            return [Candidate(chunk.id, file.id, file.path, chunk.symbol, chunk.start_line, chunk.end_line,
                fingerprint_chunk(chunk, file), query.id, sha256(query.text.encode()).hexdigest(), 1, 0)]
    monkeypatch.setattr("app.modules.investigation.retrieval.retrieve_candidates", retrieve)
    process_investigation(job_id, factory, github_auth)
    data = client.get(f"/v1/repositories/902/investigations/{job_id}")
    assert data.status_code == 200, data.text
    assert data.json()["status"] == "completed", data.json()["error_code"]
    assert data.json()["issue_origin"]["repository"] == "bob/upstream"
    assert data.json()["snapshot_inventory"]["classification"] == "PARTIAL_INVENTORY"
    assert data.json()["snapshot_partial"] is True
    evidence = client.get(f"/v1/repositories/902/investigations/{job_id}/evidence")
    assert evidence.status_code == 200 and evidence.json()["evidence_count"] == 1
    assert client.post(f"/v1/repositories/902/investigations/{job_id}/patch-proposals", json={"request_id": "11111111-1111-4111-8111-111111111111"}, headers=csrf(client)).status_code in (409, 503)
    previous_issue = github_auth.issue
    github_auth.issue = lambda *args: {**previous_issue(*args), "body": "changed"}
    assert client.get(f"/v1/repositories/902/investigations/{job_id}/upstream-context").status_code == 409
    assert client.get(f"/v1/repositories/902/investigations/{job_id}").status_code == 409
    assert client.get(f"/v1/repositories/902/investigations/{job_id}/evidence").status_code == 409


@pytest.mark.parametrize("change", ["wrong_parent", "wrong_issue", "body_hash", "commit", "source_hash", "blob", "duplicate"])
def test_upstream_partial_creation_rejects_unverified_identities(client, factory, github_auth, change):
    payload = setup(client, github_auth)
    if change == "wrong_parent":
        payload["parent_repository_id"] = 904
    if change == "wrong_issue":
        payload["issue_id"] = 991
    if change == "body_hash":
        payload["issue_body_sha256"] = "f" * 64
    if change == "commit":
        payload["commit_sha"] = "b" * 40
    if change == "source_hash":
        payload["files"][0]["sha256"] = "f" * 64
    if change == "blob":
        payload["files"][0]["git_blob_sha1"] = "f" * 40
    if change == "duplicate":
        payload["files"].append(deepcopy(payload["files"][0]))
    response = client.post(URL, json=payload, headers=csrf(client))
    assert response.status_code in (409, 422)
    with factory() as db:
        assert db.scalar(select(InvestigationJob.id)) is None
        assert db.scalar(select(CodeSnapshot.id)) is None


def test_changed_upstream_issue_cannot_publish_evidence(client, factory, github_auth):
    payload = setup(client, github_auth)
    response = client.post(URL, json=payload, headers=csrf(client))
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]
    previous = github_auth.issue
    github_auth.issue = lambda *args: {**previous(*args), "body": "different"}
    process_investigation(job_id, factory, github_auth)
    with factory() as db:
        job = db.get(InvestigationJob, job_id)
        assert job.status == "cancelled" and job.error_code == "issue_changed"
    assert client.get(f"/v1/repositories/902/investigations/{job_id}/evidence").status_code == 409
