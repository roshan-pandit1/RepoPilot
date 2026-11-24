"""Synthetic GitHub App token contracts. No GitHub network is contacted."""

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import threading

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.core.config import Settings
from app.modules.github.client import GitHubFailure
from app.modules.github.installation_token import InstallationTokenIssuer


@pytest.fixture(scope="module")
def signing_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    return key, pem


def decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def response(now, *, token="synthetic-token", repo=902, permissions=None, expiry=None):
    return {
        "token": token,
        "expires_at": (expiry or now + timedelta(minutes=55)).isoformat(),
        "permissions": permissions
        or {"contents": "read", "pull_requests": "read", "metadata": "read"},
        "repositories": [{"id": repo}],
    }


def test_scoped_jwt_signature_expiration_and_cache(signing_key):
    key, pem = signing_key
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    calls = []

    def handler(request):
        calls.append(request)
        assert request.method == "POST" and request.url.host == "api.github.com"
        assert request.url.path == "/app/installations/901/access_tokens"
        assert json.loads(request.content) == {
            "repository_ids": [902],
            "permissions": {"contents": "read", "pull_requests": "read"},
        }
        jwt = request.headers["authorization"].removeprefix("Bearer ")
        head, payload, signature = jwt.split(".")
        assert json.loads(decode(head)) == {"alg": "RS256", "typ": "JWT"}
        assert json.loads(decode(payload)) == {
            "iat": int(now.timestamp()) - 60,
            "exp": int(now.timestamp()) + 540,
            "iss": "123",
        }
        key.public_key().verify(
            decode(signature), (head + "." + payload).encode(), padding.PKCS1v15(), hashes.SHA256()
        )
        return httpx.Response(201, json=response(now))

    issuer = InstallationTokenIssuer(
        123, pem, transport=httpx.MockTransport(handler), clock=lambda: now
    )
    assert issuer.token(901, 902) == "synthetic-token"
    assert issuer.token(901, 902) == "synthetic-token" and len(calls) == 1
    issuer.invalidate(901, 902)
    assert issuer.token(901, 902) == "synthetic-token" and len(calls) == 2


def test_concurrent_refresh_deduplicated_in_process(signing_key):
    _, pem = signing_key
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    calls = []
    lock = threading.Lock()

    def handler(request):
        with lock:
            calls.append(1)
        return httpx.Response(201, json=response(now))

    issuer = InstallationTokenIssuer(
        123, pem, transport=httpx.MockTransport(handler), clock=lambda: now
    )
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert (
            list(pool.map(lambda _: issuer.token(901, 902), range(16))) == ["synthetic-token"] * 16
        )
    assert len(calls) == 1


def test_expiry_refresh_and_failed_refresh_never_uses_old_token(signing_key):
    _, pem = signing_key
    current = [datetime(2026, 1, 1, tzinfo=timezone.utc)]
    calls = []

    def handler(request):
        calls.append(1)
        return (
            httpx.Response(201, json=response(current[0], expiry=current[0] + timedelta(minutes=5)))
            if len(calls) == 1
            else httpx.Response(403)
        )

    issuer = InstallationTokenIssuer(
        123, pem, transport=httpx.MockTransport(handler), clock=lambda: current[0]
    )
    assert issuer.token(901, 902) == "synthetic-token"
    current[0] += timedelta(minutes=4)
    with pytest.raises(GitHubFailure, match="github_permission_denied"):
        issuer.token(901, 902)
    assert not issuer.cache


@pytest.mark.parametrize(
    "override",
    [
        {"repo": 903},
        {"permissions": {"contents": "write", "pull_requests": "read"}},
        {"permissions": {"contents": "read"}},
        {"permissions": {"contents": "read", "pull_requests": "read", "issues": "read"}},
        {"token": "bad\nvalue"},
    ],
)
def test_wrong_scope_and_permissions_fail_closed(signing_key, override):
    _, pem = signing_key
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    issuer = InstallationTokenIssuer(
        123,
        pem,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(201, json=response(now, **override))
        ),
        clock=lambda: now,
    )
    with pytest.raises(GitHubFailure, match="github_app_response_invalid"):
        issuer.token(901, 902)
    assert not issuer.cache


def test_bad_keys_scope_and_default_setting_fail_closed(signing_key):
    _, pem = signing_key
    settings = Settings(
        _env_file=None, app_env="test", database_url="sqlite://", github_webhook_secret="x" * 40
    )
    assert not settings.github_installation_auth_enabled
    with pytest.raises(ValueError, match="signing key"):
        Settings(
            _env_file=None,
            app_env="test",
            database_url="sqlite://",
            github_webhook_secret="x" * 40,
            github_installation_auth_enabled=True,
            github_app_id=123,
            github_app_private_key="invalid",
        )
    issuer = InstallationTokenIssuer(
        123,
        pem,
        transport=httpx.MockTransport(lambda request: pytest.fail("network should not be called")),
    )
    with pytest.raises(GitHubFailure, match="github_app_scope_invalid"):
        issuer.token(0, 902)
