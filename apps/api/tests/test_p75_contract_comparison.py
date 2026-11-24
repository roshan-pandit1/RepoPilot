"""Offline comparison of the production and a test-only patch prompt/schema."""
from dataclasses import replace
from hashlib import sha256
import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.ingestion.citations import github_citation
from app.modules.patches.generation import generate_candidate
from app.modules.patches.ollama_provider import _LocalDraft
from app.modules.patches.validation import PatchError
from p75_contract_variant import ALTERNATIVE_DRAFT, alternative_payload, capture_alternative
from test_ollama_patch_provider import chat, metadata, provider, response
from test_patch_provider_contract import EVIDENCE_ID
from test_source_coverage import SOURCE, SOURCE_HASH, capture_request, synthetic_context


DIFF = ("--- a/src/arithmetic.py\n+++ b/src/arithmetic.py\n@@ -1,2 +1,2 @@\n"
        " def add(a: int, b: int) -> int:\n-    return a - b\n+    return a + b\n")


@pytest.fixture(autouse=True)
def no_proxy_environment(monkeypatch):
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(key, raising=False)


def candidate(context, **changes):
    file = context.files[0]
    value = {"status": "candidate", "diff": DIFF, "rationale": "Synthetic proposal.",
             "uncertainty": "Not tested.", "evidence_ids": [EVIDENCE_ID],
             "source_files": [{"path": file.path, "file_id": file.file_id, "sha256": file.sha256}]}
    value.update(changes)
    return value


def mocked_provider(value):
    def handler(request):
        return response(payload=chat(value) if request.url.path == "/api/chat" else metadata(request.url.path))
    return provider(handler)


def test_both_mocked_requests_keep_identical_source_identity_and_coverage(monkeypatch):
    secret = "p75-private-environment-canary"
    monkeypatch.setenv("REPOPILOT_P75_CANARY", secret)
    ctx = synthetic_context()
    production, original_raw = capture_request(ctx)
    alternative_raw = capture_alternative(ctx)
    alternative = json.loads(alternative_raw)
    assert sha256(original_raw).hexdigest() == "423ad6fde4f09064c7c1f5a3822d32a0b3bce7d0155fe54bdc211da9b0a5f88e"
    assert production["messages"][1]["content"] == alternative["messages"][1]["content"]
    assert production["model"] == alternative["model"]
    assert production["options"] == alternative["options"]
    assert all(production[key] is False and alternative[key] is False for key in ("stream", "truncate", "shift"))
    assert [message["role"] for message in production["messages"]] == ["system", "user"]
    assert [message["role"] for message in alternative["messages"]] == ["system", "user"]
    user = json.loads(alternative["messages"][1]["content"])
    assert user["snippets"][0]["text"].encode() == SOURCE
    assert user["files"][0]["sha256"] == SOURCE_HASH
    assert user["snippets"][0]["coverage"]["classification"] == "COMPLETE_FILE"
    assert user["evidence"][0]["id"] == EVIDENCE_ID
    assert "tenant_id" not in user and "repository_id" not in user
    assert secret.encode() not in original_raw and secret.encode() not in alternative_raw
    assert len(original_raw) < 524288 and len(alternative_raw) < 524288
    system = alternative["messages"][0]["content"]
    for expected in ("untrusted data", "do not invent unseen source", "otherwise abstain",
                     "does not prove a root cause or a tested fix", "nonempty unified diff"):
        assert expected in system
    assert "def add" not in system and production["format"] != alternative["format"]


def test_prompt_only_alternative_isolates_the_system_message():
    ctx = synthetic_context()
    production, _ = capture_request(ctx)
    prompt_only = json.loads(capture_alternative(ctx, prompt_only=True))
    for key in ("model", "format", "options", "stream", "truncate", "shift"):
        assert prompt_only[key] == production[key]
    assert prompt_only["messages"][1] == production["messages"][1]
    assert prompt_only["messages"][0]["role"] == production["messages"][0]["role"] == "system"
    assert prompt_only["messages"][0]["content"] != production["messages"][0]["content"]


def test_mocked_candidate_passes_existing_structured_evidence_and_diff_validation():
    ctx = synthetic_context()
    result = generate_candidate(mocked_provider(candidate(ctx)), ctx)
    assert result.diff == DIFF and result.evidence_ids == (EVIDENCE_ID,)
    assert result.changed_files[0].path == "src/arithmetic.py"
    assert result.changed_files[0].before_sha256 == SOURCE_HASH
    assert result.changed_files[0].content == SOURCE.replace(b"a - b", b"a + b")
    assert result.changed_files[0].after_sha256 == sha256(SOURCE.replace(b"a - b", b"a + b")).hexdigest()


def test_alternative_schema_requires_candidate_diff_and_preserves_explicit_abstention():
    ctx = synthetic_context()
    value = candidate(ctx)
    assert ALTERNATIVE_DRAFT.validate_python(value).status == "candidate"
    for change in ({"diff": ""}, {"evidence_ids": []}, {"source_files": []}):
        with pytest.raises(ValidationError):
            ALTERNATIVE_DRAFT.validate_python({**value, **change})
    abstention = {"status": "insufficient_evidence", "rationale": "The required evidence is absent.",
                  "uncertainty": "high", "missing_evidence": "The relevant implementation."}
    assert ALTERNATIVE_DRAFT.validate_python(abstention).status == "insufficient_evidence"
    # The proposed four-field abstention is not silently compatible with the production parser.
    with pytest.raises(ValidationError):
        _LocalDraft.model_validate(abstention)
    with pytest.raises(PatchError, match="local_provider_invalid_response"):
        generate_candidate(mocked_provider(abstention), ctx)
    legacy = {"status": "insufficient_evidence", "diff": "", "rationale": "More evidence is needed.",
              "uncertainty": "high", "evidence_ids": [], "source_files": []}
    with pytest.raises(ValidationError):
        ALTERNATIVE_DRAFT.validate_python(legacy)
    with pytest.raises(PatchError, match="local_model_insufficient_evidence"):
        generate_candidate(mocked_provider(legacy), ctx)


@pytest.mark.parametrize("case", ["missing_source", "wrong_source_hash", "wrong_snapshot"])
def test_unverified_context_never_reaches_either_contract(case):
    ctx = synthetic_context()
    if case == "missing_source":
        ctx = replace(ctx, files=(), evidence=())
    elif case == "wrong_source_hash":
        ctx = replace(ctx, files=(replace(ctx.files[0], sha256="0" * 64),))
    else:
        identity = replace(ctx.files[0].pinned_identity, snapshot_id=str(uuid4()))
        ctx = replace(ctx, files=(replace(ctx.files[0], pinned_identity=identity),))
    seen = []
    with pytest.raises(PatchError, match="invalid_provider_request"):
        generate_candidate(provider(lambda request: seen.append(request)), ctx)
    with pytest.raises(PatchError, match="invalid_provider_request"):
        alternative_payload(ctx)
    assert not seen


@pytest.mark.parametrize("issue", ["The program behaves incorrectly.", "The release notes need updating."])
def test_ambiguous_or_unrelated_issue_may_abstain_without_a_patch(issue):
    ctx = replace(synthetic_context(), body=issue)
    abstention = {"status": "insufficient_evidence", "diff": "", "rationale": "Evidence is insufficient.",
                  "uncertainty": "high", "evidence_ids": [], "source_files": []}
    with pytest.raises(PatchError, match="local_model_insufficient_evidence"):
        generate_candidate(mocked_provider(abstention), ctx)


def test_incomplete_source_can_remain_unknown_and_abstain():
    ctx = synthetic_context(include_identity=False)
    partial = b"def add(a: int, b: int) -> int:\n"
    file = replace(ctx.files[0], content=partial, sha256=sha256(partial).hexdigest())
    evidence = replace(ctx.evidence[0], end_line=1,
                       citation=github_citation(ctx.repository_full_name, ctx.commit_sha, file.path, 1, 1))
    ctx = replace(ctx, files=(file,), evidence=(evidence,), body="The function behaves incorrectly.")
    payload, _ = capture_request(ctx)
    user = json.loads(payload["messages"][1]["content"])
    assert user["snippets"][0]["coverage"]["classification"] == "UNKNOWN_COVERAGE"
    assert user["snippets"][0]["text"].encode() == partial


@pytest.mark.parametrize("case,code", [
    ("empty_diff", "local_provider_invalid_response"),
    ("unsupported_operation", "local_provider_invalid_response"),
    ("wrong_path", "local_provider_invalid_response"),
    ("wrong_source_identity", "local_provider_invalid_response"),
    ("invalid_evidence", "invalid_evidence_reference"),
    ("oversized_patch", "local_provider_invalid_response"),
])
def test_invalid_candidate_never_bypasses_existing_validators(case, code):
    ctx = synthetic_context()
    value = candidate(ctx)
    if case == "empty_diff":
        value["diff"] = ""
    elif case == "unsupported_operation":
        value["diff"] = DIFF.replace("--- a/src/arithmetic.py", "--- /dev/null")
    elif case == "wrong_path":
        value["diff"] = DIFF.replace("+++ b/src/arithmetic.py", "+++ b/../outside.py")
    elif case == "wrong_source_identity":
        value["source_files"][0]["sha256"] = "0" * 64
    elif case == "invalid_evidence":
        value["evidence_ids"] = [str(uuid4())]
    else:
        value["diff"] = "x" * (256 * 1024 + 1)
    with pytest.raises(PatchError, match=code):
        generate_candidate(mocked_provider(value), ctx)
