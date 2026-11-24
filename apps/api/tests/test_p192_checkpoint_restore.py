"""Synthetic checkpoint restoration: no Ollama server or generated-code execution."""
import base64
from dataclasses import asdict, replace
from hashlib import sha1, sha256
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.domain.models import CodeChunk, IndexedFile, InvestigationJob, User
from app.modules.auth.session import Principal
from app.modules.ingestion.citations import github_citation
from app.modules.investigation.report_model import sanitize_issue_text
from app.modules.investigation.retrieval import Candidate, fingerprint_chunk
from app.modules.patches.checkpoint_restore import (CheckpointError, ExpectedFile, ExpectedPilot,
    capture_request, load_checkpoint, load_restored_checkpoint, submit_restoration, verify_restored_context)
from app.modules.patches.context import Evidence, PatchContext
from app.modules.patches.validation import PinnedFileIdentity, SourceFile
from app.workers.tasks import process_investigation
from test_auth_enrollment import csrf, github_auth as github_auth
from test_upstream_partial_investigation import BODY, SOURCE, setup


@pytest.fixture(autouse=True)
def no_proxy(monkeypatch):
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(key, raising=False)


def write_private(path, data):
    path.write_bytes(data)
    path.chmod(0o600)


def make_capture(tmp_path):
    parent = tmp_path / "capture"
    parent.mkdir(mode=0o700)
    root = parent / "frozen"
    root.mkdir(mode=0o700)
    source = SOURCE
    digest = sha256(source).hexdigest()
    blob = sha1(b"blob " + str(len(source)).encode() + b"\0" + source).hexdigest()
    path, repo, commit = "src/tasks.ts", "alice/public", "a" * 40
    file_id, evidence_id, chunk_id, snapshot_id, job_id = [str(uuid4()) for _ in range(5)]
    identity = PinnedFileIdentity(snapshot_id, commit, 902, 1, file_id, path, digest, len(source), True)
    file = SourceFile(path, source, digest, file_id, (evidence_id,), identity)
    chunk = SimpleNamespace(id=chunk_id, file_id=file_id, symbol=None, start_line=1, end_line=3,
                            source_text=source.decode())
    indexed = SimpleNamespace(snapshot_id=snapshot_id, path=path, content_hash=digest)
    evidence = Evidence(evidence_id, chunk_id, path, 1, 3, fingerprint_chunk(chunk, indexed),
                        github_citation(repo, commit, path, 1, 3))
    title = "process_sync fails"
    ctx = PatchContext(job_id, snapshot_id, commit, 990, sanitize_issue_text(title, 1024),
                       sanitize_issue_text(BODY, 16000), (file,), (evidence,), 902, repo, 1)
    manifest = {"version": "partial-source-manifest-v1", "repository_id": 902, "tenant_id": 1,
        "repository_full_name": repo, "commit_sha": commit, "inventory_coverage": "PARTIAL_INVENTORY",
        "files": [{"path": path, "git_blob_sha1": blob, "byte_length": len(source), "sha256": digest,
                   "encoding": "utf-8", "normalization": "identity", "coverage": "COMPLETE_FILE"}]}
    manifest_hash = sha256(json.dumps(manifest, ensure_ascii=True, sort_keys=True,
                                      separators=(",", ":")).encode("ascii")).hexdigest()
    model, model_hash = "qwen2.5-coder:7b", "b" * 64
    wire = capture_request(ctx, model=model, digest=model_hash)
    wire_hash = sha256(wire).hexdigest()
    body_hash = sha256(BODY.encode()).hexdigest()
    expected = ExpectedPilot(902, repo, 903, "bob/upstream", 990, 5, title, body_hash, commit,
        snapshot_id, job_id, manifest_hash, wire_hash, len(wire), model, model_hash,
        (ExpectedFile(path, len(source), digest, blob),))
    context_data = asdict(ctx)
    context_data["files"][0]["content"] = {"base64": base64.b64encode(source).decode()}
    metadata = {"issue_body_sha256": body_hash, "origin_repository_id": 903, "issue_id": 990,
        "model": model, "model_sha256": model_hash, "snapshot_id": snapshot_id, "job_id": job_id,
        "request_sha256": wire_hash, "request_bytes": len(wire), "manifest_sha256": manifest_hash,
        "evidence_ids": [evidence_id]}
    root_metadata = {"repository": repo, "repository_id": 902, "parent": "bob/upstream", "private": False,
        "pinned_commit": commit, "issue_number": 5, "issue_title": title,
        "issue_url": "https://github.com/bob/upstream/issues/5", "issue_body_sha256": body_hash}
    for name, value in (("context.json", context_data), ("metadata.json", metadata), ("manifest.json", manifest)):
        write_private(root / name, json.dumps(value).encode())
    write_private(root / "request.json", wire)
    write_private(parent / "metadata.json", json.dumps(root_metadata).encode())
    write_private(parent / "issue-body.txt", BODY.encode())
    return root, expected


def test_reconstructs_exact_old_bytes_without_a_network_or_model(tmp_path):
    root, expected = make_capture(tmp_path)
    verified = load_checkpoint(root, expected)
    assert sha256(verified.old_request).hexdigest() == expected.original_request_sha256
    assert len(verified.context.evidence) == 1


@pytest.mark.parametrize("corrupt", ["request", "manifest", "source", "evidence", "issue", "metadata", "permissions"])
def test_checkpoint_corruption_fails_closed(tmp_path, corrupt):
    root, expected = make_capture(tmp_path)
    if corrupt == "permissions":
        (root / "request.json").chmod(0o644)
    elif corrupt == "request":
        write_private(root / "request.json", b"{}")
    elif corrupt == "issue":
        write_private(root.parent / "issue-body.txt", b"changed")
    else:
        name = {"manifest": "manifest.json", "source": "context.json", "evidence": "context.json",
                "metadata": "metadata.json"}[corrupt]
        path = root / name
        value = json.loads(path.read_bytes())
        if corrupt == "manifest":
            value["files"][0]["byte_length"] += 1
        elif corrupt == "source":
            value["files"][0]["content"]["base64"] = base64.b64encode(b"changed\n").decode()
        elif corrupt == "evidence":
            value["evidence"][0]["fingerprint"] = "f" * 64
        else:
            value["issue_id"] += 1
        write_private(path, json.dumps(value).encode())
    with pytest.raises(CheckpointError):
        load_checkpoint(root, expected)


def test_restores_through_authenticated_application_with_new_identities(client, factory, github_auth, monkeypatch, tmp_path):
    setup(client, github_auth)
    root, expected = make_capture(tmp_path)
    checkpoint = load_checkpoint(root, expected)
    restored_id = submit_restoration(client, checkpoint, csrf_headers=csrf(client))
    assert restored_id != expected.original_investigation_id
    with factory() as db:
        job = db.get(InvestigationJob, restored_id)
        assert job.snapshot_id != expected.original_snapshot_id
        chunk = db.scalar(select(CodeChunk).join(IndexedFile, CodeChunk.file_id == IndexedFile.id)
                          .where(IndexedFile.snapshot_id == job.snapshot_id))
        chunk_id = chunk.id
    def retrieve(_factory, **kwargs):
        with factory() as db:
            chunk = db.get(CodeChunk, chunk_id)
            file = db.get(IndexedFile, chunk.file_id)
            query = kwargs["queries"][0]
            return [Candidate(chunk.id, file.id, file.path, chunk.symbol, chunk.start_line, chunk.end_line,
                fingerprint_chunk(chunk, file), query.id, sha256(query.text.encode()).hexdigest(), 1, 0)]
    monkeypatch.setattr("app.modules.investigation.retrieval.retrieve_candidates", retrieve)
    process_investigation(restored_id, factory, github_auth)
    with factory() as db:
        job = db.get(InvestigationJob, restored_id)
        user = db.get(User, job.user_id)
        identity = Principal(user.id, job.tenant_id, user.github_user_id, "sensitive-github-token", job.session_hash)
        context = verify_restored_context(db, restored_id, checkpoint, identity=identity, github=github_auth)
    assert context.evidence[0].id != checkpoint.context.evidence[0].id
    new_wire = capture_request(context, model=expected.model, digest=expected.model_sha256)
    assert sha256(new_wire).hexdigest() != expected.original_request_sha256
    assert client.post(f"/v1/repositories/902/investigations/{restored_id}/patch-proposals",
        json={"request_id": str(uuid4())}, headers=csrf(client)).status_code in {409, 503}


def test_restoration_submission_requires_authentication(client, tmp_path):
    root, expected = make_capture(tmp_path)
    checkpoint = load_checkpoint(root, expected)
    with pytest.raises(CheckpointError, match="restoration_submission_failed"):
        submit_restoration(client, checkpoint, csrf_headers={})


def test_restored_capture_can_be_locally_verified_again_without_transferring_approval(tmp_path):
    old_base, new_base = tmp_path / "old", tmp_path / "new"
    old_base.mkdir(mode=0o700)
    new_base.mkdir(mode=0o700)
    old_root, old_expected = make_capture(old_base)
    new_root, new_expected = make_capture(new_base)
    previous = load_checkpoint(old_root, old_expected)
    meta_path = new_root / "metadata.json"
    metadata = json.loads(meta_path.read_bytes())
    for name in ("issue_body_sha256", "origin_repository_id", "issue_id", "model", "model_sha256"):
        del metadata[name]
    metadata.update(run="p192_restored", old_request_transferred=False,
                    actual_model_inference=0, source_provider_network_calls=0)
    write_private(meta_path, json.dumps(metadata).encode())
    verified = load_restored_checkpoint(new_root, new_expected, predecessor=previous)
    assert verified.context.investigation_id != previous.context.investigation_id
    assert sha256(verified.old_request).hexdigest() == new_expected.original_request_sha256
    assert new_expected.original_request_sha256 != old_expected.original_request_sha256
    with pytest.raises(CheckpointError):
        load_restored_checkpoint(new_root, replace(new_expected, origin_repository_id=999), predecessor=previous)
    with pytest.raises(CheckpointError):
        load_restored_checkpoint(new_root, old_expected, predecessor=previous)
    metadata["actual_model_inference"] = 1
    write_private(meta_path, json.dumps(metadata).encode())
    with pytest.raises(CheckpointError):
        load_restored_checkpoint(new_root, new_expected, predecessor=previous)
