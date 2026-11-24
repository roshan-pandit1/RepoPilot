"""Single-use exact-byte transport for a separately revalidated local pilot.

Not registered as a production provider. This cannot authenticate an Ollama process,
prove host egress policy, or reconstruct the database. Existing scoped-job guards must
remain until the application independently verifies and integrates those boundaries.
"""
from __future__ import annotations

import asyncio
from hashlib import sha256
from hmac import compare_digest
import json
from typing import Callable

import httpx

from app.modules.patches.inference_ledger import LedgerError, canonical_identity


def _no_duplicates(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _json(raw):
    try:
        result = json.loads(raw, object_pairs_hook=_no_duplicates)
        if not isinstance(result, dict):
            raise ValueError("not an object")
        return result
    except (ValueError, UnicodeError, RecursionError, TypeError):
        raise LedgerError("invalid_transport_payload") from None


class _BytesStream(httpx.AsyncByteStream):
    def __init__(self, content: bytes):
        self._content = content

    async def __aiter__(self):
        yield self._content


class GuardedPilotTransport(httpx.AsyncBaseTransport):
    """Claim a durable entitlement immediately before forwarding exact chat bytes.

    The inner transport, resolver and ledger are trusted application-owned dependencies,
    not values accepted from an HTTP request or a model. A claim is never released after
    an exception, cancellation or ambiguous network outcome.
    """

    def __init__(self, *, ledger, identity: dict, frozen_request: bytes,
                 resolve_current_identity: Callable[[], dict], inner: httpx.AsyncBaseTransport):
        if not isinstance(frozen_request, bytes) or not frozen_request or not callable(resolve_current_identity):
            raise LedgerError("invalid_transport_configuration")
        if not isinstance(inner, httpx.AsyncBaseTransport):
            raise LedgerError("invalid_transport_configuration")
        self._ledger = ledger
        self._identity = identity
        self._identity_bytes = canonical_identity(identity)
        self._identity_sha256 = sha256(self._identity_bytes).hexdigest()
        self._frozen = frozen_request
        self._digest = sha256(frozen_request).hexdigest()
        self._resolve = resolve_current_identity
        self._inner = inner
        self._claim_token: str | None = None
        self._preflight: set[str] = set()
        # Metadata revalidation and claim must not race on one transport.
        self._request_lock = asyncio.Lock()
        payload = _json(frozen_request)
        options = payload.get("options")
        if (identity.get("endpoint") != "http://127.0.0.1:11434"
                or identity.get("request_sha256") != self._digest
                or type(identity.get("request_bytes")) is not int
                or identity["request_bytes"] != len(frozen_request)
                or payload.get("model") != identity["model"] or payload.get("stream") is not False
                or payload.get("truncate") is not False or payload.get("shift") is not False
                or not isinstance(payload.get("messages"), list) or not isinstance(payload.get("format"), dict)
                or not isinstance(options, dict) or type(options.get("num_ctx")) is not int
                or not 1 <= options["num_ctx"] <= 8192 or type(options.get("num_predict")) is not int
                or not 1 <= options["num_predict"] <= 2048):
            raise LedgerError("invalid_transport_configuration")

    async def _metadata(self, request: httpx.Request) -> httpx.Response:
        # A failed or interrupted recheck must not retain earlier evidence.
        self._preflight.discard(request.url.path)
        if request.url.path == "/api/show" and _json(request.content) != {"model": self._identity["model"]}:
            raise LedgerError("invalid_transport_payload")
        response = await self._inner.handle_async_request(request)
        raw = bytearray()
        try:
            if response.is_stream_consumed:
                if len(response.content) > 65536:
                    raise LedgerError("invalid_transport_metadata")
                raw.extend(response.content)
            else:
                async for chunk in response.aiter_raw():
                    if len(chunk) > 65536 - len(raw):
                        raise LedgerError("invalid_transport_metadata")
                    raw.extend(chunk)
        finally:
            await response.aclose()
        data = _json(bytes(raw))
        if response.status_code != 200 or response.headers.get("content-encoding", "identity").lower() != "identity":
            raise LedgerError("invalid_transport_metadata")
        path = request.url.path
        if path == "/api/status":
            valid = isinstance(data.get("cloud"), dict) and data["cloud"].get("disabled") is True
        elif path == "/api/tags":
            models = data.get("models")
            matches = [row for row in models if isinstance(row, dict) and row.get("name") == self._identity["model"]] if isinstance(models, list) and len(models) <= 1024 else []
            valid = (len(matches) == 1 and matches[0].get("digest") == self._identity["model_sha256"]
                     and type(matches[0].get("size")) is int and matches[0]["size"] > 0
                     and isinstance(matches[0].get("details"), dict) and matches[0]["details"].get("format") == "gguf"
                     and not matches[0].get("remote_host") and not matches[0].get("remote_model"))
        else:
            valid = (isinstance(data.get("details"), dict) and data["details"].get("format") == "gguf"
                     and isinstance(data.get("capabilities"), list) and "completion" in data["capabilities"]
                     and not data.get("remote_host") and not data.get("remote_model"))
        if not valid:
            raise LedgerError("invalid_transport_metadata")
        self._preflight.add(path)
        return httpx.Response(response.status_code, headers=response.headers, stream=_BytesStream(bytes(raw)), request=request)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        async with self._request_lock:
            return await self._handle_async_request(request)

    async def _handle_async_request(self, request: httpx.Request) -> httpx.Response:
        target = request.url
        if (target.scheme != "http" or target.host != "127.0.0.1" or target.port != 11434
                or target.username or target.password or target.query or target.fragment
                or request.headers.get("host") != "127.0.0.1:11434"
                or any(name in request.headers for name in ("authorization", "proxy-authorization", "cookie"))):
            raise LedgerError("invalid_transport_endpoint")
        allowed = {("GET", "/api/status"), ("GET", "/api/tags"),
                   ("POST", "/api/show"), ("POST", "/api/chat")}
        if (request.method, target.path) not in allowed:
            raise LedgerError("invalid_transport_endpoint")
        if target.path != "/api/chat":
            return await self._metadata(request)
        if self._claim_token is not None:
            raise LedgerError("attempt_already_claimed")
        body = request.content
        if (self._preflight != {"/api/status", "/api/tags", "/api/show"}
                or not isinstance(body, bytes) or len(body) != len(self._frozen)
                or not compare_digest(body, self._frozen)
                or not compare_digest(sha256(body).hexdigest(), self._digest)
                or canonical_identity(self._identity) != self._identity_bytes
                or canonical_identity(self._resolve()) != self._identity_bytes):
            raise LedgerError("approved_identity_mismatch")
        # claim() must commit with FULL synchronous durability before it returns.
        token = self._ledger.claim(self._identity, request_sha256=self._digest, request_bytes=len(body))
        self._claim_token = token
        try:
            return await self._inner.handle_async_request(request)
        except (Exception, asyncio.CancelledError):
            try:
                self._ledger.finish(self._identity_sha256, token, "OUTCOME_UNKNOWN")
            except Exception:
                # The committed claim remains spent even if terminal recording fails.
                pass
            raise

    def finish(self, outcome: str) -> None:
        """Record a result only after the trusted caller has validated the response."""
        if self._claim_token is None:
            raise LedgerError("attempt_not_claimed")
        self._ledger.finish(self._identity_sha256, self._claim_token, outcome)

    async def aclose(self) -> None:
        await self._inner.aclose()
