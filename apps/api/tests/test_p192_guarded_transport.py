"""Synthetic exact-byte local transport safety; no model or real network."""
import asyncio
from copy import deepcopy
from hashlib import sha256
import json

import httpx
import pytest

from app.modules.patches.guarded_transport import GuardedPilotTransport
from app.modules.patches.inference_ledger import LedgerError, PilotLedger
from test_p192_ledger import approve, identity


def setup(tmp_path):
    directory = tmp_path / "private"
    ledger = PilotLedger.create(directory)
    body = json.dumps({"model": "fixture:7b", "messages": [{"role": "user", "content": "synthetic"}],
        "format": {"type": "object"}, "stream": False, "truncate": False, "shift": False,
        "options": {"num_ctx": 8192, "num_predict": 2048}}, separators=(",", ":")).encode()
    item = identity()
    item["request_bytes"] = len(body)
    item["request_sha256"] = sha256(body).hexdigest()
    return item, body, ledger


def delegate(seen, *, failure=None, digest="f" * 64):
    async def handler(request):
        seen.append((request.url.path, request.content))
        if request.url.path == "/api/status":
            return httpx.Response(200, json={"cloud": {"disabled": True}})
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "fixture:7b", "digest": digest,
                "size": 1, "details": {"format": "gguf"}}]})
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"details": {"format": "gguf"}, "capabilities": ["completion"]})
        if failure:
            raise failure
        return httpx.Response(200, json={"ok": True})
    return httpx.MockTransport(handler)


async def preflight(client):
    await client.get("/api/status")
    await client.get("/api/tags")
    await client.post("/api/show", json={"model": "fixture:7b"})


def test_unapproved_and_without_preflight_never_reach_chat(tmp_path):
    item, body, ledger = setup(tmp_path)
    ledger.prepare(item)
    seen = []
    async def run():
        guard = GuardedPilotTransport(ledger=ledger, identity=item, frozen_request=body,
            resolve_current_identity=lambda: item, inner=delegate(seen))
        async with httpx.AsyncClient(base_url=item["endpoint"], transport=guard, trust_env=False) as client:
            with pytest.raises(LedgerError):
                await client.post("/api/chat", content=body)
            await preflight(client)
            with pytest.raises(LedgerError):
                await client.post("/api/chat", content=body)
    asyncio.run(run())
    assert all(path != "/api/chat" for path, _ in seen)


def test_approved_frozen_bytes_are_forwarded_once(tmp_path):
    item, body, ledger = setup(tmp_path)
    key = approve(ledger, item)
    seen = []
    async def run():
        guard = GuardedPilotTransport(ledger=ledger, identity=item, frozen_request=body,
            resolve_current_identity=lambda: item, inner=delegate(seen))
        async with httpx.AsyncClient(base_url=item["endpoint"], transport=guard, trust_env=False) as client:
            await preflight(client)
            assert (await client.post("/api/chat", content=body)).status_code == 200
            guard.finish("SUCCEEDED")
            with pytest.raises(LedgerError):
                await client.post("/api/chat", content=body)
    asyncio.run(run())
    assert [content for path, content in seen if path == "/api/chat"] == [body]
    assert PilotLedger(ledger.directory).status(key) == "SUCCEEDED"


@pytest.mark.parametrize("mutation", ["body", "current_identity", "model_digest"])
def test_changes_fail_before_claim_or_send(tmp_path, mutation):
    item, body, ledger = setup(tmp_path)
    key = approve(ledger, item)
    current = deepcopy(item)
    if mutation == "current_identity":
        current["tenant_id"] += 1
    seen = []
    async def run():
        guard = GuardedPilotTransport(ledger=ledger, identity=item, frozen_request=body,
            resolve_current_identity=lambda: current, inner=delegate(seen, digest="0" * 64 if mutation == "model_digest" else "f" * 64))
        async with httpx.AsyncClient(base_url=item["endpoint"], transport=guard, trust_env=False) as client:
            with pytest.raises(LedgerError):
                await preflight(client)
                await client.post("/api/chat", content=body + (b" " if mutation == "body" else b""))
    asyncio.run(run())
    assert all(path != "/api/chat" for path, _ in seen)
    assert ledger.status(key) == "APPROVED"


def test_failed_send_consumes_claim_and_records_unknown(tmp_path):
    item, body, ledger = setup(tmp_path)
    key = approve(ledger, item)
    seen = []
    async def run():
        guard = GuardedPilotTransport(ledger=ledger, identity=item, frozen_request=body,
            resolve_current_identity=lambda: item, inner=delegate(seen, failure=httpx.ReadTimeout("synthetic")))
        async with httpx.AsyncClient(base_url=item["endpoint"], transport=guard, trust_env=False) as client:
            await preflight(client)
            with pytest.raises(httpx.ReadTimeout):
                await client.post("/api/chat", content=body)
            with pytest.raises(LedgerError):
                await client.post("/api/chat", content=body)
    asyncio.run(run())
    assert len([path for path, _ in seen if path == "/api/chat"]) == 1
    assert ledger.status(key) == "OUTCOME_UNKNOWN"


def test_failed_metadata_recheck_invalidates_previous_success(tmp_path):
    item, body, ledger = setup(tmp_path)
    key = approve(ledger, item)
    seen = []
    wrong_digest = False

    async def handler(request):
        seen.append(request.url.path)
        if request.url.path == "/api/status":
            return httpx.Response(200, json={"cloud": {"disabled": True}})
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{
                "name": "fixture:7b", "digest": "0" * 64 if wrong_digest else "f" * 64,
                "size": 1, "details": {"format": "gguf"},
            }]})
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"details": {"format": "gguf"},
                                             "capabilities": ["completion"]})
        return httpx.Response(200, json={"ok": True})

    async def run():
        nonlocal wrong_digest
        guard = GuardedPilotTransport(ledger=ledger, identity=item, frozen_request=body,
            resolve_current_identity=lambda: item, inner=httpx.MockTransport(handler))
        async with httpx.AsyncClient(base_url=item["endpoint"], transport=guard, trust_env=False) as client:
            await preflight(client)
            wrong_digest = True
            with pytest.raises(LedgerError, match="invalid_transport_metadata"):
                await client.get("/api/tags")
            with pytest.raises(LedgerError, match="approved_identity_mismatch"):
                await client.post("/api/chat", content=body)

    asyncio.run(run())
    assert "/api/chat" not in seen
    assert ledger.status(key) == "APPROVED"


def test_inflight_failed_metadata_recheck_blocks_chat(tmp_path):
    item, body, ledger = setup(tmp_path)
    key = approve(ledger, item)
    seen = []

    async def run():
        started, release = asyncio.Event(), asyncio.Event()
        rechecking = False

        async def handler(request):
            seen.append(request.url.path)
            if request.url.path == "/api/status":
                return httpx.Response(200, json={"cloud": {"disabled": True}})
            if request.url.path == "/api/tags":
                if rechecking:
                    started.set()
                    await release.wait()
                return httpx.Response(200, json={"models": [{
                    "name": "fixture:7b", "digest": "0" * 64 if rechecking else "f" * 64,
                    "size": 1, "details": {"format": "gguf"},
                }]})
            if request.url.path == "/api/show":
                return httpx.Response(200, json={"details": {"format": "gguf"},
                                                 "capabilities": ["completion"]})
            return httpx.Response(200, json={"ok": True})

        guard = GuardedPilotTransport(ledger=ledger, identity=item, frozen_request=body,
            resolve_current_identity=lambda: item, inner=httpx.MockTransport(handler))
        async with httpx.AsyncClient(base_url=item["endpoint"], transport=guard, trust_env=False) as client:
            await preflight(client)
            rechecking = True
            check = asyncio.create_task(client.get("/api/tags"))
            await asyncio.wait_for(started.wait(), timeout=1)
            chat = asyncio.create_task(client.post("/api/chat", content=body))
            release.set()
            with pytest.raises(LedgerError, match="invalid_transport_metadata"):
                await check
            with pytest.raises(LedgerError, match="approved_identity_mismatch"):
                await chat

    asyncio.run(run())
    assert "/api/chat" not in seen
    assert ledger.status(key) == "APPROVED"


def test_unsafe_model_settings_and_external_endpoint_rejected(tmp_path):
    item, body, ledger = setup(tmp_path)
    altered = json.loads(body)
    altered["stream"] = True
    bad = json.dumps(altered, separators=(",", ":")).encode()
    item["request_bytes"], item["request_sha256"] = len(bad), sha256(bad).hexdigest()
    with pytest.raises(LedgerError):
        GuardedPilotTransport(ledger=ledger, identity=item, frozen_request=bad,
            resolve_current_identity=lambda: item, inner=delegate([]))
    item["endpoint"] = "http://example.com:11434"
    with pytest.raises(LedgerError):
        GuardedPilotTransport(ledger=ledger, identity=item, frozen_request=bad,
            resolve_current_identity=lambda: item, inner=delegate([]))


def test_actual_provider_uses_guarded_exact_transport_with_mock_only(tmp_path, monkeypatch):
    """Capture and forward the actual adapter's wire bytes without any socket."""
    from app.modules.patches.generation import generate_candidate
    from app.modules.patches.ollama_provider import OllamaPatchProvider
    from test_ollama_patch_provider import DIGEST, ENDPOINT, MODEL, chat, draft, metadata, response
    from test_patch_provider_contract import DIFF, context

    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(name, raising=False)
    seen = []
    def handler(request):
        seen.append((request.url.path, request.content))
        return response(payload=chat(draft()) if request.url.path == "/api/chat" else metadata(request.url.path))
    candidate = context()
    capture = OllamaPatchProvider(MODEL, DIGEST, ENDPOINT, transport=httpx.MockTransport(handler))
    assert generate_candidate(capture, candidate).diff == DIFF
    body = next(content for path, content in seen if path == "/api/chat")
    directory = tmp_path / "actual-provider-private"
    ledger = PilotLedger.create(directory)
    item = identity()
    item.update(model=MODEL, model_sha256=DIGEST, request_sha256=sha256(body).hexdigest(),
                request_bytes=len(body), input_bytes=524288, output_bytes=307200)
    key = approve(ledger, item)
    sent = []
    async def inner_handler(request):
        sent.append((request.url.path, request.content))
        return response(payload=chat(draft()) if request.url.path == "/api/chat" else metadata(request.url.path))
    guard = GuardedPilotTransport(ledger=ledger, identity=item, frozen_request=body,
        resolve_current_identity=lambda: item, inner=httpx.MockTransport(inner_handler))
    real_adapter_with_mock = OllamaPatchProvider(MODEL, DIGEST, ENDPOINT, transport=guard)
    assert generate_candidate(real_adapter_with_mock, candidate).diff == DIFF
    guard.finish("SUCCEEDED")
    assert [content for path, content in sent if path == "/api/chat"] == [body]
    assert ledger.status(key) == "SUCCEEDED"
