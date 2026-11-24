import json
from pathlib import Path

import pytest

from app.modules.patches.trusted_demo import validate_and_present
from app.modules.patches.validation import PatchError

EVIDENCE = Path("/Users/roshan/Library/Application Support/RepoPilot/toolchains/p9-final-39f65ce2a574/results.json")


def test_retained_actual_evidence_presents_honest_trusted_demo():
    result = validate_and_present(EVIDENCE.read_bytes())
    assert result["outcome"] == "BASELINE_FAILED_PATCH_PASSED"
    assert result["control_outcome"] == "BOTH_PASSED"
    assert result["sandbox_used"] is False and result["production_validation"] is False


@pytest.mark.parametrize("mutate", [
    lambda d: d.pop("control"),
    lambda d: d["baseline_patch"].update(source_sha256="0" * 64),
    lambda d: d["baseline_patch"].update(patch_sha256="0" * 64),
    lambda d: d["baseline_patch"].update(sandbox_used=True),
    lambda d: d["baseline_patch"].update(outcome="BOTH_PASSED"),
    lambda d: d["baseline_patch"].pop("patched"),
])
def test_forged_or_incomplete_evidence_rejected(mutate):
    doc = json.loads(EVIDENCE.read_text())
    mutate(doc)
    with pytest.raises(PatchError, match="invalid_trusted_synthetic_evidence"):
        validate_and_present(json.dumps(doc).encode())
