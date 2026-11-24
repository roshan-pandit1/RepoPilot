"""Synthetic Ollama protocol and patch-workflow tests; never contact a model."""
import asyncio
from dataclasses import replace
from hashlib import sha256
import json
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import get_settings
from app.domain.models import CodeChunk, PatchOutbox, PatchProposal
from app.modules.ingestion.citations import github_citation
from app.modules.patches.generation import generate_candidate
from app.modules.patches.ollama_provider import OllamaPatchProvider, _LocalDraft
from app.modules.patches.service import get_candidate_provider
from app.modules.patches.validation import PatchError
from app.modules.patches.worker import process_patch
from test_auth_enrollment import csrf, github_auth as github_auth
from test_patch_proposals import DIFF as WORKER_DIFF
from test_patch_proposals import create, enable, parent_setup, proposal_root
from test_patch_provider_contract import DIFF, EVIDENCE_ID, FILE_ID, SOURCE, context


MODEL = "qwen2.5-coder:7b"
DIGEST = "a" * 64
ENDPOINT = "http://127.0.0.1:11434"


class _ResponseStream(httpx.AsyncByteStream):
    def __init__(self, content):
        self.content = content

    async def __aiter__(self):
        for offset in range(0, len(self.content), 64):
            yield self.content[offset:offset + 64]


def response(status=200, *, payload=None, content=None, headers=None):
    raw = json.dumps(payload).encode() if content is None and payload is not None else (content or b"")
    return httpx.Response(status, stream=_ResponseStream(raw), headers=headers)


@pytest.fixture(autouse=True)
def no_proxy_environment(monkeypatch):
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(key, raising=False)


def metadata(path):
    if path == "/api/status":
        return {"cloud": {"disabled": True}}
    if path == "/api/tags":
        return {"models": [{"name": MODEL, "model": MODEL, "digest": DIGEST, "size": 1,
                            "details": {"format": "gguf"}}]}
    if path == "/api/show":
        return {"details": {"format": "gguf"}, "capabilities": ["completion"]}
    raise AssertionError("unexpected metadata path")


def draft(*, diff=DIFF, source=None, evidence_ids=None):
    return {"status": "candidate", "diff": diff, "rationale": "Change the synthetic function.",
            "uncertainty": "The reported behavior is not reproduced.",
            "evidence_ids": [EVIDENCE_ID] if evidence_ids is None else evidence_ids,
            "source_files": [source or {"path": "src/add.py", "file_id": FILE_ID,
                                        "sha256": sha256(SOURCE).hexdigest()}]}


def chat(result):
    return {"model": MODEL, "done": True, "done_reason": "stop",
            "message": {"role": "assistant", "content": json.dumps(result)}}


def provider(handler=None, *, model=MODEL, digest=DIGEST, endpoint=ENDPOINT, **kwargs):
    if handler is None:
        def handler(request):
            return response(payload=chat(draft()) if request.url.path == "/api/chat"
                                  else metadata(request.url.path))
    return OllamaPatchProvider(model, digest, endpoint, transport=httpx.MockTransport(handler), **kwargs)


def test_default_registry_is_disabled_and_explicit_selection_is_required(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "patch_generation_provider", "unavailable")
    monkeypatch.setattr(settings, "patch_local_model_enabled", False)
    assert not settings.patch_proposals_enabled and not settings.index_multilingual_enabled
    assert not settings.index_multilingual_supervised_parser_enabled
    assert get_candidate_provider() is None
    monkeypatch.setattr(settings, "patch_generation_provider", "ollama")
    assert get_candidate_provider() is None
    monkeypatch.setattr(settings, "patch_local_model_enabled", True)
    assert isinstance(get_candidate_provider(), OllamaPatchProvider)


def test_valid_mocked_chat_preserves_identity_and_validator_contract():
    seen = []
    def handler(request):
        seen.append(request)
        return response(payload=chat(draft()) if request.url.path == "/api/chat"
                              else metadata(request.url.path))
    result = generate_candidate(provider(handler), context())
    assert (result.diff, result.provider, result.model) == (DIFF, "ollama", f"{MODEL}@sha256:{DIGEST}")
    assert result.changed_files[0].path == "src/add.py"
    assert "Uncertainty:" in result.rationale
    assert [req.url.path for req in seen] == ["/api/status", "/api/tags", "/api/show", "/api/chat"]
    body = json.loads(seen[-1].content)
    assert body["stream"] is False and body["truncate"] is False and body["shift"] is False
    assert body["format"]["type"] == "object" and body["options"]["temperature"] == 0
    assert body["messages"][0]["role"] == "system" and body["messages"][1]["role"] == "user"
    assert "Ignore previous instructions" not in body["messages"][0]["content"]
    assert "Ignore previous instructions" in body["messages"][1]["content"]


def test_only_evidence_snippets_are_sent_and_no_credentials_are_added(caplog):
    original = context()
    source = (SOURCE + "# same\u2028line\n".encode() + b"# unrelated line\n" * 8
              + b"# do-not-transmit-unrelated-marker\n")
    changed = replace(original.files[0], content=source, sha256=sha256(source).hexdigest())
    original = replace(original, files=(changed,))
    seen = []
    def handler(request):
        seen.append(request)
        updated = {"path": changed.path, "file_id": changed.file_id, "sha256": changed.sha256}
        return response(payload=chat(draft(source=updated)) if request.url.path == "/api/chat"
                              else metadata(request.url.path))
    generate_candidate(provider(handler), original)
    body = json.loads(seen[-1].content)
    user = json.loads(body["messages"][1]["content"])
    assert "tenant_id" not in user and "repository_id" not in user
    assert "do-not-transmit-unrelated-marker" not in seen[-1].content.decode()
    assert "do-not-transmit-unrelated-marker" not in caplog.text
    assert original.body not in caplog.text and SOURCE.decode() not in caplog.text
    assert "authorization" not in seen[-1].headers and "cookie" not in seen[-1].headers
    assert user["files"][0]["sha256"] == changed.sha256
    assert user["snippets"][0]["start_line"] == 1 and user["snippets"][0]["end_line"] == 5
    assert user["snippets"][0]["text"] == SOURCE.decode() + "# same\u2028line\n" + "# unrelated line\n" * 2


def test_synthetic_add_implementation_reaches_final_mocked_chat_request(monkeypatch):
    """Exercise the actual adapter serialization; no daemon or model is contacted."""
    secret = "p73-private-environment-canary"
    monkeypatch.setenv("REPOPILOT_P73_CANARY", secret)
    source = b"def add(a: int, b: int) -> int:\n    return a - b\n"
    path = "src/synthetic_add.py"
    diff = ("--- a/src/synthetic_add.py\n+++ b/src/synthetic_add.py\n@@ -1,2 +1,2 @@\n"
            " def add(a: int, b: int) -> int:\n-    return a - b\n+    return a + b\n")
    original = context()
    file = replace(original.files[0], path=path, content=source, sha256=sha256(source).hexdigest())
    assert file.sha256 == "9445c47952abb8a7fc5d4a905d55b5be05771df1d69362ec597f9a50f7ede40d"
    repository = "synthetic-lab/arithmetic"
    evidence = replace(original.evidence[0], path=path,
                       citation=github_citation(repository, original.commit_sha, path, 1, 2))
    original = replace(original, files=(file,), evidence=(evidence,), repository_full_name=repository,
                       repository_id=1002, tenant_id=1003, issue_id=1001, title="Synthetic addition issue",
                       body="The add function incorrectly subtracts the second argument. It should return the sum.")
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path != "/api/chat":
            return response(payload=metadata(request.url.path))
        identity = {"path": file.path, "file_id": file.file_id, "sha256": file.sha256}
        return response(payload=chat(draft(diff=diff, source=identity)))

    candidate = generate_candidate(provider(handler), original)
    assert candidate.diff == diff
    assert candidate.changed_files[0].content == source.replace(b"a - b", b"a + b")
    assert [request.url.path for request in requests] == ["/api/status", "/api/tags", "/api/show", "/api/chat"]
    request = requests[-1]
    assert request.url.host == "127.0.0.1" and request.url.port == 11434
    payload = json.loads(request.content)
    assert len(request.content) <= 524288
    assert payload["model"] == MODEL and payload["stream"] is False
    assert payload["format"] == _LocalDraft.model_json_schema()
    assert payload["truncate"] is False and payload["shift"] is False
    assert payload["options"] == {"temperature": 0, "num_ctx": 8192, "num_predict": 2048}
    assert [message["role"] for message in payload["messages"]] == ["system", "user"]
    instructions = payload["messages"][0]["content"]
    assert "only for the supplied evidence-backed files" in instructions
    assert "--- a/path, +++ b/path and @@ hunks" in instructions
    assert "no diff --git headers, renames, or deletions" in instructions
    assert "If the evidence is insufficient" in instructions
    user = json.loads(payload["messages"][1]["content"])
    assert user["issue"] == {"title": original.title, "body": original.body}
    assert user["files"] == [{"path": file.path, "file_id": file.file_id, "sha256": file.sha256}]
    snippet = user["snippets"][0]
    assert {key: snippet[key] for key in ("evidence_id", "path", "start_line", "end_line", "text")} == {
        "evidence_id": EVIDENCE_ID, "path": file.path, "start_line": 1, "end_line": 2, "text": source.decode()}
    assert snippet["coverage"]["classification"] == "UNKNOWN_COVERAGE"
    assert user["evidence"][0]["id"] == EVIDENCE_ID
    assert (user["evidence"][0]["start_line"], user["evidence"][0]["end_line"]) == (1, 2)
    assert user["evidence"][0]["citation"] == original.evidence[0].citation
    assert (user["repository"], user["investigation_id"], user["snapshot_id"], user["commit_sha"]) == (
        original.repository_full_name, original.investigation_id, original.snapshot_id, original.commit_sha)
    assert secret not in request.content.decode()
    assert "authorization" not in request.headers and "cookie" not in request.headers


def test_synthetic_subtract_implementation_reaches_final_mocked_chat_request():
    source = b"def subtract(a: int, b: int) -> int:\n    return a + b\n"
    original = context()
    path, repository = "src/synthetic_subtract.py", "synthetic-lab/arithmetic"
    file = replace(original.files[0], path=path, content=source, sha256=sha256(source).hexdigest())
    assert file.sha256 == "d95d69ddc17091cc1064e45765706616a84f7558bba4b57dc1b968d3b3bc8b73"
    evidence = replace(original.evidence[0], path=path,
                       citation=github_citation(repository, original.commit_sha, path, 1, 2))
    original = replace(original, files=(file,), evidence=(evidence,), repository_full_name=repository,
        repository_id=1002, tenant_id=1003, issue_id=1001, title="Synthetic subtraction issue",
        body="The subtract function incorrectly adds the second argument. "
             "It should return the first argument minus the second.")
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path != "/api/chat":
            return response(payload=metadata(request.url.path))
        abstention = {"status": "insufficient_evidence", "diff": "", "rationale": "The model abstained.",
                      "uncertainty": "high", "evidence_ids": [], "source_files": []}
        return response(payload=chat(abstention))

    with pytest.raises(PatchError, match="local_model_insufficient_evidence"):
        generate_candidate(provider(handler), original)
    payload = json.loads(seen[-1].content)
    user = json.loads(payload["messages"][1]["content"])
    assert user["issue"] == {"title": original.title, "body": original.body}
    assert user["files"] == [{"path": path, "file_id": file.file_id, "sha256": file.sha256}]
    snippet = user["snippets"][0]
    assert {key: snippet[key] for key in ("evidence_id", "path", "start_line", "end_line", "text")} == {
        "evidence_id": EVIDENCE_ID, "path": path, "start_line": 1, "end_line": 2, "text": source.decode()}
    assert snippet["coverage"]["classification"] == "UNKNOWN_COVERAGE"
    assert user["evidence"][0]["citation"] == evidence.citation


def test_chat_schema_allows_candidate_and_abstention_but_not_extra_fields():
    schema = _LocalDraft.model_json_schema()
    assert set(schema["required"]) == {"status", "diff", "rationale", "uncertainty", "evidence_ids", "source_files"}
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]["status"]["enum"]) == {"candidate", "insufficient_evidence"}
    assert "discriminator" not in schema
    candidate = _LocalDraft.model_validate(draft())
    abstention = _LocalDraft.model_validate({"status": "insufficient_evidence", "diff": "",
        "rationale": "The evidence is not enough.", "uncertainty": "high", "evidence_ids": [], "source_files": []})
    assert candidate.status == "candidate" and candidate.diff == DIFF
    assert abstention.status == "insufficient_evidence" and abstention.diff == ""


def test_chat_request_byte_limit_applies_to_the_final_utf8_payload():
    original = replace(context(), body="The synthetic addition result is incorrect. Café.")
    seen = []

    def handler(request):
        seen.append(request)
        return response(payload=chat(draft()) if request.url.path == "/api/chat"
                        else metadata(request.url.path))

    generate_candidate(provider(handler), original)
    size = len(seen[-1].content)
    assert "Café" in seen[-1].content.decode()
    seen.clear()
    generate_candidate(provider(handler, input_bytes=size), original)
    assert len(seen[-1].content) == size
    seen.clear()
    with pytest.raises(PatchError, match="provider_input_too_large"):
        generate_candidate(provider(handler, input_bytes=size - 1), original)
    assert "/api/chat" not in [request.url.path for request in seen]


def test_missing_source_is_rejected_before_any_model_transport():
    seen = []

    def handler(request):
        seen.append(request)
        raise AssertionError("missing source must not reach the provider")

    with pytest.raises(PatchError, match="invalid_provider_request"):
        generate_candidate(provider(handler), replace(context(), files=(), evidence=()))
    assert not seen


def test_ambiguous_issue_with_unrelated_source_can_abstain_without_a_patch():
    original = context()
    source = b"def unrelated():\n    return 7\n"
    file = replace(original.files[0], content=source, sha256=sha256(source).hexdigest())
    original = replace(original, title="Synthetic issue", body="The program behaves incorrectly.", files=(file,))
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path != "/api/chat":
            return response(payload=metadata(request.url.path))
        abstention = {"status": "insufficient_evidence", "diff": "", "rationale": "The issue is ambiguous.",
                      "uncertainty": "high", "evidence_ids": [], "source_files": []}
        return response(payload=chat(abstention))

    with pytest.raises(PatchError, match="local_model_insufficient_evidence"):
        generate_candidate(provider(handler), original)
    payload = json.loads(seen[-1].content)
    user = json.loads(payload["messages"][1]["content"])
    assert user["issue"]["body"] == original.body
    assert user["snippets"][0]["text"] == source.decode()


def test_empty_candidate_is_rejected_at_structured_validation(monkeypatch):
    empty = draft(diff="")
    # The transmitted flat JSON schema is intentionally unchanged for wire compatibility.
    assert "minLength" not in _LocalDraft.model_json_schema()["properties"]["diff"]
    with pytest.raises(ValidationError):
        _LocalDraft.model_validate(empty)

    def unexpected_diff_validation(*args):
        pytest.fail("an empty candidate must fail structured validation first")

    monkeypatch.setattr("app.modules.patches.ollama_provider.validate_patch", unexpected_diff_validation)

    def handler(request):
        return response(payload=chat(empty) if request.url.path == "/api/chat" else metadata(request.url.path))

    with pytest.raises(PatchError, match="local_provider_invalid_response"):
        generate_candidate(provider(handler), context())


class SyntheticTransportProvider:
    """Test-only provider facade; caller must supply an isolated httpx mock transport."""

    def __init__(self, adapter):
        assert isinstance(adapter._transport, httpx.MockTransport)
        self._adapter = adapter

    def __getattr__(self, name):
        return getattr(self._adapter, name)


def test_mocked_abstention_is_recorded_without_publishing_a_patch(client, factory, github_auth, monkeypatch):
    parent, _, _ = parent_setup(client, factory, github_auth, monkeypatch)

    def handler(request):
        if request.url.path != "/api/chat":
            return response(payload=metadata(request.url.path))
        abstention = {"status": "insufficient_evidence", "diff": "", "rationale": "More evidence is needed.",
                      "uncertainty": "high", "evidence_ids": [], "source_files": []}
        return response(payload=chat(abstention))

    selected = SyntheticTransportProvider(provider(handler))
    enable(monkeypatch, selected)
    proposal = create(client, parent)
    process_patch(proposal, factory, github_auth, selected)
    with factory() as db:
        row = db.get(PatchProposal, proposal)
        assert (row.status, row.error_code) == ("failed", "local_model_insufficient_evidence")
        assert row.diff is None and row.changed_files is None


@pytest.mark.parametrize("endpoint", [
    "https://127.0.0.1:11434", "http://localhost:11434", "http://127.0.0.2:11434",
    "http://127.1:11434", "http://[::1]:11434", "http://127.0.0.1:11434/path",
    "http://127.0.0.1:11434?x=1", "http://127.0.0.1:11434#x", "http://u@127.0.0.1:11434",
    "http://127.0.0.1:11434@evil.invalid", "http://127.0.0.1", "http://127.0.0.1:0",
])
def test_non_loopback_or_ambiguous_endpoints_fail_before_transport(endpoint):
    with pytest.raises(PatchError, match="local_provider_invalid_endpoint"):
        provider(endpoint=endpoint).check_readiness()


@pytest.mark.parametrize("model", ["", "qwen:cloud", "qwen:7b-cloud", "host/model:7b", "qwen", "Qwen:7b"])
def test_cloud_or_unqualified_models_are_rejected(model):
    with pytest.raises(PatchError, match="local_model_(invalid|not_configured)"):
        provider(model=model).check_readiness()


def test_missing_model_digest_is_rejected():
    with pytest.raises(PatchError, match="local_model_digest_not_configured"):
        provider(digest="").check_readiness()


@pytest.mark.parametrize("proxy", ["HTTP_PROXY", "https_proxy", "ALL_PROXY"])
def test_proxy_environment_fails_closed_before_transport(monkeypatch, proxy):
    monkeypatch.setenv(proxy, "http://proxy.invalid:8080")
    with pytest.raises(PatchError, match="local_provider_proxy_configured"):
        provider().check_readiness()


@pytest.mark.parametrize("change,code", [
    ("cloud_enabled", "local_provider_cloud_not_disabled"),
    ("status_missing", "local_provider_cloud_not_disabled"),
    ("missing_model", "local_model_not_found"),
    ("wrong_digest", "local_model_incompatible"),
    ("remote_model", "local_model_incompatible"),
    ("wrong_format", "local_model_incompatible"),
    ("missing_capability", "local_model_incompatible"),
    ("remote_show", "local_model_incompatible"),
])
def test_readiness_fails_without_safe_local_model_metadata(change, code):
    paths = []
    def handler(request):
        paths.append(request.url.path)
        data = metadata(request.url.path)
        if change == "cloud_enabled" and request.url.path == "/api/status":
            data["cloud"]["disabled"] = False
        if change == "status_missing" and request.url.path == "/api/status":
            data = {}
        if change == "missing_model" and request.url.path == "/api/tags":
            data["models"] = []
        if request.url.path == "/api/tags" and change in {"wrong_digest", "remote_model", "wrong_format"}:
            if change == "wrong_digest":
                data["models"][0]["digest"] = "b" * 64
            elif change == "remote_model":
                data["models"][0]["remote_host"] = "https://example.invalid"
            else:
                data["models"][0]["details"]["format"] = "remote"
        if request.url.path == "/api/show" and change == "missing_capability":
            data["capabilities"] = []
        if request.url.path == "/api/show" and change == "remote_show":
            data["remote_model"] = "cloud"
        return response(payload=data)
    with pytest.raises(PatchError, match=code):
        generate_candidate(provider(handler), context())
    assert "/api/chat" not in paths


def test_redirect_is_never_followed():
    paths = []
    def handler(request):
        paths.append(str(request.url))
        return response(status=302, headers={"Location": "http://example.invalid/steal"})
    with pytest.raises(PatchError, match="local_provider_redirect"):
        provider(handler).check_readiness()
    assert paths == [ENDPOINT + "/api/status"]


def test_unreachable_service_has_a_sanitized_failure():
    def handler(request):
        raise httpx.ConnectError("synthetic private diagnostic", request=request)
    with pytest.raises(PatchError, match="local_provider_unreachable") as exc:
        provider(handler).check_readiness()
    assert "private diagnostic" not in str(exc.value)


@pytest.mark.parametrize("variant", ["bad_envelope", "missing_field", "duplicate_keys", "remote_chat", "unfinished",
                                      "wrong_model", "truncated", "bad_identity", "missing_inventory"])
def test_invalid_chat_responses_are_rejected(variant):
    def handler(request):
        if request.url.path != "/api/chat":
            return response(payload=metadata(request.url.path))
        result = chat(draft())
        if variant == "bad_envelope":
            return response(content=b"not-json")
        if variant == "missing_field":
            value = draft()
            del value["uncertainty"]
            result = chat(value)
        elif variant == "duplicate_keys":
            result["message"]["content"] = '{"status":"candidate","status":"candidate"}'
        elif variant == "remote_chat":
            result["remote_host"] = "https://example.invalid"
        elif variant == "unfinished":
            result["done"] = False
        elif variant == "wrong_model":
            result["model"] = "other:7b"
        elif variant == "truncated":
            result["done_reason"] = "length"
        elif variant == "bad_identity":
            value = draft()
            value["source_files"][0]["sha256"] = "b" * 64
            result = chat(value)
        elif variant == "missing_inventory":
            value = draft()
            value["source_files"] = []
            result = chat(value)
        return response(payload=result)
    with pytest.raises(PatchError, match="local_provider_invalid_response"):
        generate_candidate(provider(handler), context())


@pytest.mark.parametrize("value", ["diff --git a/src/add.py b/src/add.py\n" + DIFF,
                                   DIFF.replace("+++ b/src/add.py", "+++ b/../secret.py")])
def test_unsupported_diff_or_invalid_path_is_rejected(value):
    def handler(request):
        return response(payload=chat(draft(diff=value)) if request.url.path == "/api/chat"
                              else metadata(request.url.path))
    with pytest.raises(PatchError, match="local_provider_invalid_response"):
        generate_candidate(provider(handler), context())


def test_wrong_evidence_is_rejected_by_existing_candidate_validator():
    def handler(request):
        return response(payload=chat(draft(evidence_ids=[str(uuid4())])) if request.url.path == "/api/chat"
                              else metadata(request.url.path))
    with pytest.raises(PatchError, match="invalid_evidence_reference"):
        generate_candidate(provider(handler), context())


def test_oversized_response_is_rejected_without_partial_candidate():
    def handler(request):
        return (response(content=b"x" * 1025) if request.url.path == "/api/chat"
                else response(payload=metadata(request.url.path)))
    with pytest.raises(PatchError, match="local_provider_invalid_response"):
        generate_candidate(provider(handler, output_bytes=1024), context())


def test_wrong_source_hash_never_reaches_transport():
    called = []
    def handler(request):
        called.append(request)
        raise AssertionError("no request should occur")
    original = context()
    with pytest.raises(PatchError, match="invalid_provider_request"):
        generate_candidate(provider(handler), replace(original, files=(replace(original.files[0], sha256="0" * 64),)))
    assert not called


def test_insufficient_evidence_abstains():
    value = draft()
    value["status"] = "insufficient_evidence"
    def handler(request):
        return response(payload=chat(value) if request.url.path == "/api/chat"
                              else metadata(request.url.path))
    with pytest.raises(PatchError, match="local_model_insufficient_evidence"):
        generate_candidate(provider(handler), context())


def test_generation_timeout_cancels_the_http_operation():
    from app.modules.patches.generation import ProviderLimits
    cancelled = []
    async def handler(request):
        if request.url.path == "/api/chat":
            try:
                await asyncio.sleep(5)
            finally:
                cancelled.append(True)
        return response(payload=metadata(request.url.path))
    with pytest.raises(TimeoutError):
        generate_candidate(provider(handler), context(), provider_limits=ProviderLimits(timeout_seconds=1))
    assert cancelled == [True]


def test_cancellation_closes_the_inflight_mocked_request():
    state = {"started": False, "closed": False}
    async def handler(request):
        if request.url.path == "/api/chat":
            state["started"] = True
            try:
                await asyncio.sleep(5)
            finally:
                state["closed"] = True
        return response(payload=metadata(request.url.path))
    with pytest.raises(PatchError, match="local_provider_cancelled"):
        generate_candidate(provider(handler), context(), cancelled=lambda: state["started"])
    assert state == {"started": True, "closed": True}


def test_mocked_ollama_full_worker_path_preserves_fencing_and_unavailable_tests(
        client, factory, github_auth, monkeypatch):
    parent, snapshot, _ = parent_setup(client, factory, github_auth, monkeypatch)
    calls = []
    def handler(request):
        calls.append(request.url.path)
        if request.url.path != "/api/chat":
            return response(payload=metadata(request.url.path))
        prompt = json.loads(json.loads(request.content)["messages"][1]["content"])
        # IndexedFile currently has no independently persisted byte length.
        assert all(item["coverage"]["classification"] == "UNKNOWN_COVERAGE" for item in prompt["snippets"])
        output = draft(diff=WORKER_DIFF, source=prompt["files"][0], evidence_ids=[prompt["evidence"][0]["id"]])
        return response(payload=chat(output))
    settings = get_settings()
    monkeypatch.setattr(settings, "patch_proposals_enabled", True)
    monkeypatch.setattr(settings, "patch_generation_provider", "ollama")
    monkeypatch.setattr(settings, "patch_local_model_enabled", True)
    monkeypatch.setattr(settings, "patch_local_model_name", MODEL)
    monkeypatch.setattr(settings, "patch_local_model_digest", DIGEST)
    monkeypatch.setattr(settings, "patch_local_model_endpoint", ENDPOINT)
    configured_adapter = SyntheticTransportProvider(provider(handler))
    monkeypatch.setattr("app.modules.patches.routes.get_candidate_provider", lambda: configured_adapter)
    monkeypatch.setattr("app.modules.patches.worker.get_candidate_provider", lambda: configured_adapter)
    key = uuid4()
    proposal = create(client, parent, key)
    assert create(client, parent, key) == proposal
    process_patch(proposal, factory, github_auth)
    process_patch(proposal, factory, github_auth)
    assert calls.count("/api/chat") == 1
    with factory() as db:
        row = db.get(PatchProposal, proposal)
        assert row.status == "static_validated" and row.snapshot_id == snapshot
        assert row.model == f"{MODEL}@sha256:{DIGEST}"
        assert row.test_result["status"] == "VALIDATION_UNAVAILABLE"
        assert db.get(PatchOutbox, proposal).status == "processed"
    result = client.get(proposal_root(parent) + "/" + proposal)
    assert result.status_code == 200 and result.json()["diff"] == WORKER_DIFF


def test_api_reports_unavailable_without_submitting_a_job(client, factory, github_auth, monkeypatch):
    parent, _, _ = parent_setup(client, factory, github_auth, monkeypatch)
    def handler(request):
        raise httpx.ConnectError("private detail", request=request)
    enable(monkeypatch, provider(handler))
    response = client.get(proposal_root(parent))
    assert response.status_code == 200 and response.json()["available"] is False
    assert "private detail" not in response.text
    response = client.post(proposal_root(parent), headers=csrf(client), json={"request_id": str(uuid4())})
    assert response.status_code == 503 and "private detail" not in response.text
    with factory() as db:
        assert db.query(PatchProposal).count() == 0


@pytest.mark.parametrize("method", ["get", "post"])
def test_access_is_rechecked_after_the_local_metadata_probe(client, factory, github_auth, monkeypatch, method):
    parent, _, _ = parent_setup(client, factory, github_auth, monkeypatch)
    def handler(request):
        if request.url.path == "/api/show":
            github_auth.include_repository = False
        return response(payload=metadata(request.url.path))
    enable(monkeypatch, SyntheticTransportProvider(provider(handler)))
    if method == "get":
        result = client.get(proposal_root(parent))
    else:
        result = client.post(proposal_root(parent), headers=csrf(client), json={"request_id": str(uuid4())})
    assert result.status_code == 404
    with factory() as db:
        assert db.query(PatchProposal).count() == 0


def test_cancelling_during_mocked_ollama_generation_closes_request_and_fences_publication(
        client, factory, github_auth, monkeypatch):
    parent, _, _ = parent_setup(client, factory, github_auth, monkeypatch)
    state = {"proposal": None, "closed": False}
    async def handler(request):
        if request.url.path != "/api/chat":
            return response(payload=metadata(request.url.path))
        result = client.post(proposal_root(parent) + f"/{state['proposal']}/review", headers=csrf(client),
                             json={"decision": "rejected"})
        assert result.status_code == 200
        try:
            await asyncio.sleep(5)
        finally:
            state["closed"] = True
    selected = SyntheticTransportProvider(provider(handler))
    enable(monkeypatch, selected)
    state["proposal"] = create(client, parent)
    process_patch(state["proposal"], factory, github_auth, selected)
    assert state["closed"] is True
    with factory() as db:
        row = db.get(PatchProposal, state["proposal"])
        assert (row.status, row.error_code, row.review_state) == ("failed", "reviewer_cancelled", "rejected")
        assert row.diff is None and row.changed_files is None


def test_changed_source_during_mocked_ollama_generation_cannot_publish(
        client, factory, github_auth, monkeypatch):
    parent, _, chunk_id = parent_setup(client, factory, github_auth, monkeypatch)
    def handler(request):
        if request.url.path != "/api/chat":
            return response(payload=metadata(request.url.path))
        prompt = json.loads(json.loads(request.content)["messages"][1]["content"])
        with factory.begin() as db:
            db.get(CodeChunk, chunk_id).source_text = "def process_sync():\n    return 3\n"
        output = draft(diff=WORKER_DIFF, source=prompt["files"][0], evidence_ids=[prompt["evidence"][0]["id"]])
        return response(payload=chat(output))
    selected = SyntheticTransportProvider(provider(handler))
    enable(monkeypatch, selected)
    proposal = create(client, parent)
    process_patch(proposal, factory, github_auth, selected)
    with factory() as db:
        row = db.get(PatchProposal, proposal)
        assert row.status == "stale" and row.error_code == "issue_or_snapshot_changed"
        assert row.diff is None and row.changed_files is None
