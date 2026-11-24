"""Synthetic-only single-host durable approval ledger contracts."""
from copy import deepcopy
from hashlib import sha256
import multiprocessing
import os
from pathlib import Path
from uuid import uuid4

import pytest

from app.modules.patches.inference_ledger import LedgerError, PilotLedger, canonical_identity


def identity():
    return {"version": "pilot-inference-identity-v1", "tenant_id": 1, "target_repository_id": 2,
        "target_repository_name": "synthetic/fork", "origin_repository_id": 3,
        "origin_repository_name": "synthetic/parent", "issue_id": 4, "issue_number": 5,
        "issue_body_sha256": "a" * 64, "commit_sha": "b" * 40,
        "investigation_id": str(uuid4()), "snapshot_id": str(uuid4()), "manifest_sha256": "c" * 64,
        "evidence": [{"id": str(uuid4()), "path": "src/example.py", "start_line": 1,
                      "end_line": 2, "fingerprint": "d" * 64}],
        "sources": [{"path": "src/example.py", "byte_length": 12, "sha256": "e" * 64}],
        "model": "fixture:7b", "model_sha256": "f" * 64, "endpoint": "http://127.0.0.1:11434",
        "timeout_seconds": 30, "input_bytes": 10000, "output_bytes": 2000,
        "request_sha256": sha256(b"synthetic outbound bytes").hexdigest(), "request_bytes": 24,
        "transport": {"cloud_disabled": True, "deny_nonloopback": True,
                      "follow_redirects": False, "trust_env": False}}


@pytest.fixture
def ledger_dir(tmp_path):
    root = tmp_path / "ledger"
    PilotLedger.create(root)
    return root


def approve(ledger, item):
    key = ledger.prepare(item)
    ledger.approve(key, request_sha256=item["request_sha256"], request_bytes=item["request_bytes"],
                   confirmation=f"APPROVE {key} {item['request_sha256']}")
    return key


def race_worker(root, item, start, results):
    try:
        ledger = PilotLedger(Path(root))
        start.wait(15)
        token = ledger.claim(item, request_sha256=item["request_sha256"], request_bytes=item["request_bytes"])
        results.put(("claimed", token))
    except Exception as exc:
        results.put(("rejected", type(exc).__name__))


def test_unapproved_claim_rejected_and_approval_requires_explicit_match(ledger_dir):
    item = identity()
    ledger = PilotLedger(ledger_dir)
    key = ledger.prepare(item)
    assert ledger.status(key) == "AWAITING_EXPLICIT_APPROVAL"
    with pytest.raises(LedgerError):
        ledger.claim(item, request_sha256=item["request_sha256"], request_bytes=item["request_bytes"])
    with pytest.raises(LedgerError):
        ledger.approve(key, request_sha256=item["request_sha256"], request_bytes=item["request_bytes"], confirmation="")
    assert ledger.status(key) == "AWAITING_EXPLICIT_APPROVAL"


def test_claim_survives_restart_and_cannot_be_recycled(ledger_dir):
    item = identity()
    key = approve(PilotLedger(ledger_dir), item)
    token = PilotLedger(ledger_dir).claim(item, request_sha256=item["request_sha256"], request_bytes=item["request_bytes"])
    assert PilotLedger(ledger_dir).status(key) == "ATTEMPT_CLAIMED"
    with pytest.raises(LedgerError):
        PilotLedger(ledger_dir).claim(item, request_sha256=item["request_sha256"], request_bytes=item["request_bytes"])
    PilotLedger(ledger_dir).finish(key, token, "OUTCOME_UNKNOWN")
    with pytest.raises(LedgerError):
        PilotLedger(ledger_dir).claim(item, request_sha256=item["request_sha256"], request_bytes=item["request_bytes"])
    with pytest.raises(LedgerError):
        PilotLedger(ledger_dir).finish(key, token, "SUCCEEDED")
    assert PilotLedger(ledger_dir).status(key) == "OUTCOME_UNKNOWN"


def test_cross_process_claim_race_has_one_winner(ledger_dir):
    item = identity()
    key = approve(PilotLedger(ledger_dir), item)
    ctx = multiprocessing.get_context("spawn")
    ready = ctx.Event()
    results = ctx.Queue()
    workers = [ctx.Process(target=race_worker, args=(str(ledger_dir), item, ready, results)) for _ in range(2)]
    for worker in workers:
        worker.start()
    ready.set()
    for worker in workers:
        worker.join(20)
        assert worker.exitcode == 0
    statuses = [results.get(timeout=3)[0] for _ in workers]
    assert sorted(statuses) == ["claimed", "rejected"]
    assert PilotLedger(ledger_dir).status(key) == "ATTEMPT_CLAIMED"


@pytest.mark.parametrize("field", ["tenant_id", "target_repository_id", "origin_repository_id", "issue_id", "issue_number",
                                   "commit_sha", "manifest_sha256", "issue_body_sha256", "model_sha256", "request_sha256"])
def test_changed_bound_identity_cannot_claim(ledger_dir, field):
    item = identity()
    approve(PilotLedger(ledger_dir), item)
    altered = deepcopy(item)
    altered[field] = altered[field] + 1 if isinstance(altered[field], int) else "1" * len(altered[field])
    with pytest.raises(LedgerError):
        PilotLedger(ledger_dir).claim(altered, request_sha256=altered["request_sha256"], request_bytes=altered["request_bytes"])


def test_changed_length_source_evidence_and_transport_cannot_claim(ledger_dir):
    item = identity()
    approve(PilotLedger(ledger_dir), item)
    variants = []
    for change in ("length", "source", "evidence", "transport", "endpoint"):
        altered = deepcopy(item)
        if change == "length":
            altered["request_bytes"] += 1
        elif change == "source":
            altered["sources"][0]["sha256"] = "1" * 64
        elif change == "evidence":
            altered["evidence"][0]["fingerprint"] = "1" * 64
        elif change == "transport":
            altered["transport"]["deny_nonloopback"] = False
        else:
            altered["endpoint"] = "http://localhost:11434"
        variants.append(altered)
    for altered in variants:
        with pytest.raises(LedgerError):
            PilotLedger(ledger_dir).claim(altered, request_sha256=altered["request_sha256"], request_bytes=altered["request_bytes"])


def test_same_request_cannot_be_reprepared_under_different_tenant(ledger_dir):
    item = identity()
    ledger = PilotLedger(ledger_dir)
    ledger.prepare(item)
    changed = deepcopy(item)
    changed["tenant_id"] += 1
    with pytest.raises(LedgerError):
        ledger.prepare(changed)


def test_invalid_permissions_symlink_hardlink_or_missing_db_fail_closed(ledger_dir, tmp_path):
    ledger = PilotLedger(ledger_dir)
    os.chmod(ledger.path, 0o644)
    with pytest.raises(LedgerError):
        PilotLedger(ledger_dir)
    os.chmod(ledger.path, 0o600)
    link = tmp_path / "hardlink"
    os.link(ledger.path, link)
    with pytest.raises(LedgerError):
        PilotLedger(ledger_dir)
    link.unlink()
    ledger.path.unlink()
    ledger.path.symlink_to(tmp_path / "missing")
    with pytest.raises(LedgerError):
        PilotLedger(ledger_dir)


def test_corrupted_ledger_does_not_reset_spent_state(ledger_dir):
    item = identity()
    ledger = PilotLedger(ledger_dir)
    approve(ledger, item)
    ledger.path.write_bytes(b"corrupt")
    os.chmod(ledger.path, 0o600)
    with pytest.raises(LedgerError):
        PilotLedger(ledger_dir)


def test_identity_serialization_is_stable_and_rejects_bool_transport():
    item = identity()
    assert canonical_identity(item) == canonical_identity(deepcopy(item))
    item["transport"]["deny_nonloopback"] = 1
    with pytest.raises(LedgerError):
        canonical_identity(item)


def crash_worker(root, item, send_before_crash):
    ledger = PilotLedger(Path(root))
    ledger.claim(item, request_sha256=item["request_sha256"], request_bytes=item["request_bytes"])
    if send_before_crash:
        fd = os.open(Path(root) / "synthetic-send-record", os.O_CREAT | os.O_WRONLY | os.O_EXCL, 0o600)
        os.write(fd, b"one mocked send\n")
        os.fsync(fd)
        os.close(fd)
    os._exit(17)


@pytest.mark.parametrize("send_before_crash", [False, True])
def test_real_child_crash_after_claim_never_recycles_attempt(ledger_dir, send_before_crash):
    item = identity()
    key = approve(PilotLedger(ledger_dir), item)
    ctx = multiprocessing.get_context("spawn")
    worker = ctx.Process(target=crash_worker, args=(str(ledger_dir), item, send_before_crash))
    worker.start()
    worker.join(20)
    assert worker.exitcode == 17
    assert (ledger_dir / "synthetic-send-record").exists() is send_before_crash
    ledger = PilotLedger(ledger_dir)
    assert ledger.status(key) == "ATTEMPT_CLAIMED"
    with pytest.raises(LedgerError):
        ledger.claim(item, request_sha256=item["request_sha256"], request_bytes=item["request_bytes"])
    ledger.mark_outcome_unknown(key)
    assert PilotLedger(ledger_dir).status(key) == "OUTCOME_UNKNOWN"
    with pytest.raises(LedgerError):
        PilotLedger(ledger_dir).claim(item, request_sha256=item["request_sha256"], request_bytes=item["request_bytes"])


def test_invalidation_is_final_and_never_recycles_claim(ledger_dir):
    item = identity()
    ledger = PilotLedger(ledger_dir)
    key = approve(ledger, item)
    ledger.invalidate(key)
    assert ledger.status(key) == "INVALIDATED"
    with pytest.raises(LedgerError):
        ledger.claim(item, request_sha256=item["request_sha256"], request_bytes=item["request_bytes"])
    with pytest.raises(LedgerError):
        ledger.approve(key, request_sha256=item["request_sha256"], request_bytes=item["request_bytes"],
                       confirmation=f"APPROVE {key} {item['request_sha256']}")


def test_missing_spent_authority_never_recreates_itself(ledger_dir):
    item = identity()
    ledger = PilotLedger(ledger_dir)
    key = approve(ledger, item)
    ledger.claim(item, request_sha256=item["request_sha256"], request_bytes=item["request_bytes"])
    assert ledger.status(key) == "ATTEMPT_CLAIMED"
    ledger.path.unlink()
    with pytest.raises(LedgerError):
        PilotLedger(ledger_dir)
    assert not ledger.path.exists()
    with pytest.raises(LedgerError):
        PilotLedger.create(ledger_dir)
    assert not ledger.path.exists()
