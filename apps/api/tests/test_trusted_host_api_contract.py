"""The production service must not call a host execution result sandboxed."""
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.patches import routes
from app.modules.patches.native_specs import COMMIT, REPOSITORY, SNAPSHOT, SOURCE_PATH, SPECS
from app.modules.patches.service import verify_saved
from app.modules.patches.validation import PatchError, SourceFile


def test_actual_host_report_is_rejected_by_sandbox_service_and_api(monkeypatch):
    path = os.environ.get("REPOPILOT_TRUSTED_HOST_REPORT")
    if not path:
        pytest.skip("actual trusted host report was not provided")
    report = json.loads(Path(path).read_text())["baseline_patch"]
    assert report["status"] == "COMPLETED"
    assert report["sandbox_used"] is False and report["test_executed"] is True
    assert report["outcome"] == "BASELINE_FAILED_PATCH_PASSED"

    spec = SPECS[0]
    source = SourceFile(SOURCE_PATH, spec.source, spec.source_sha256, "file", ("evidence",))
    context = SimpleNamespace(snapshot_id=SNAPSHOT, commit_sha=COMMIT, investigation_id="investigation",
                              files=(source,))
    task = SimpleNamespace(id="proposal", status="tests_passed", snapshot_id=SNAPSHOT, commit_sha=COMMIT,
                           investigation_id="investigation", review_state="unreviewed", error_code=None,
                           created_at=None, updated_at=None, evidence=[], diff=spec.patch,
                           static_result={"status": "passed", "checks": ["snapshot", "source_hash", "evidence", "diff"]},
                           test_result=report)
    with pytest.raises(PatchError, match="invalid_test_result"):
        verify_saved(task, context, REPOSITORY)

    parent = SimpleNamespace(source_repository_name=REPOSITORY)
    monkeypatch.setattr(routes, "_access", lambda *args, **kwargs: (parent, object()))
    monkeypatch.setattr(routes, "_enabled", lambda: None)
    monkeypatch.setattr(routes, "_item", lambda *args, **kwargs: task)
    monkeypatch.setattr(routes, "assemble_context", lambda *args, **kwargs: context)
    db = SimpleNamespace(get=lambda *args: None)
    with pytest.raises(HTTPException) as error:
        routes.get_proposal(object(), 1, object(), object(), object(), db, object())
    assert error.value.status_code == 409
