"""Repository-scoped, short-lived GitHub App installation tokens.

Call only after existing tenant, membership, installation and repository authorization.
Tokens and JWTs remain in process memory and are never returned to browser clients.
The lock deduplicates refreshes within one process, not across application processes.
"""

import base64
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import json
import threading

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.core.config import get_settings
from app.modules.github.client import GitHubFailure, github_http_failure


def _encoded(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


class InstallationTokenIssuer:
    def __init__(self, app_id, private_key, *, transport=None, clock=None):
        try:
            key = serialization.load_pem_private_key(private_key.encode(), password=None)
            if (
                type(app_id) is not int
                or app_id <= 0
                or not isinstance(key, rsa.RSAPrivateKey)
                or key.key_size < 2048
            ):
                raise ValueError
        except (ValueError, TypeError, AttributeError):
            raise GitHubFailure("github_app_configuration_invalid") from None
        self.app_id = app_id
        self.key = key
        self.transport = transport
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.lock = threading.Lock()
        self.cache = {}

    def _jwt(self, current):
        header = _encoded(
            json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode()
        )
        epoch = int(current.timestamp())
        payload = _encoded(
            json.dumps(
                {"iat": epoch - 60, "exp": epoch + 540, "iss": str(self.app_id)},
                separators=(",", ":"),
            ).encode()
        )
        unsigned = (header + "." + payload).encode("ascii")
        return (
            unsigned.decode("ascii")
            + "."
            + _encoded(self.key.sign(unsigned, padding.PKCS1v15(), hashes.SHA256()))
        )

    def token(self, installation_id, repository_id):
        if any(
            type(value) is not int or not 0 < value < 2**63
            for value in (installation_id, repository_id)
        ):
            raise GitHubFailure("github_app_scope_invalid")
        scope = (installation_id, repository_id)
        with self.lock:
            current = self.clock()
            cached = self.cache.get(scope)
            if cached and cached[1] > current + timedelta(seconds=120):
                return cached[0]
            # Drop old credentials before refreshing; never silently reuse them after an error.
            self.cache.pop(scope, None)
            try:
                with httpx.Client(
                    timeout=10, follow_redirects=False, transport=self.transport, trust_env=False
                ) as client:
                    with client.stream(
                        "POST",
                        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
                        headers={
                            "Accept": "application/vnd.github+json",
                            "Authorization": "Bearer " + self._jwt(current),
                            "X-GitHub-Api-Version": "2022-11-28",
                            "User-Agent": "RepoPilot-ReadOnly/1",
                        },
                        json={
                            "repository_ids": [repository_id],
                            "permissions": {"contents": "read", "pull_requests": "read"},
                        },
                    ) as response:
                        if response.is_error:
                            raise github_http_failure(response.status_code, response.headers)
                        if response.status_code != 201:
                            raise GitHubFailure("github_app_token_unavailable")
                        raw = bytearray()
                        for chunk in response.iter_bytes():
                            if len(raw) + len(chunk) > 65536:
                                raise GitHubFailure("github_app_response_invalid")
                            raw.extend(chunk)
                data = json.loads(raw)
                token, expiry, permissions, repos = (
                    data["token"],
                    data["expires_at"],
                    data["permissions"],
                    data["repositories"],
                )
                expiry = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
                if (
                    not isinstance(token, str)
                    or not 1 <= len(token) <= 4096
                    or "\n" in token
                    or "\r" in token
                    or not token.isascii()
                    or any(char.isspace() for char in token)
                    or expiry.tzinfo is None
                    or not current + timedelta(seconds=120)
                    < expiry
                    <= current + timedelta(minutes=65)
                    or not isinstance(permissions, dict)
                    or permissions.get("contents") != "read"
                    or permissions.get("pull_requests") != "read"
                    or not set(permissions).issubset({"contents", "pull_requests", "metadata"})
                    or any(value not in {"read", None} for value in permissions.values())
                    or not isinstance(repos, list)
                    or len(repos) != 1
                    or not isinstance(repos[0], dict)
                    or type(repos[0].get("id")) is not int
                    or repos[0]["id"] != repository_id
                ):
                    raise ValueError
            except GitHubFailure:
                raise
            except (httpx.TimeoutException, httpx.NetworkError):
                raise GitHubFailure("github_temporarily_unavailable") from None
            except (
                httpx.HTTPError,
                ValueError,
                TypeError,
                KeyError,
                AttributeError,
                OverflowError,
            ):
                raise GitHubFailure("github_app_response_invalid") from None
            if len(self.cache) >= 128:
                self.cache.clear()
            self.cache[scope] = (token, expiry)
            return token

    def invalidate(self, installation_id, repository_id):
        with self.lock:
            self.cache.pop((installation_id, repository_id), None)


@lru_cache(maxsize=1)
def get_installation_issuer():
    settings = get_settings()
    return InstallationTokenIssuer(
        settings.github_app_id, settings.github_app_private_key.get_secret_value()
    )


def review_token(identity, installation_id, repository_id):
    """Caller must have just authorized this user, tenant and selected repository."""
    if not get_settings().github_installation_auth_enabled:
        if not identity.token:
            raise GitHubFailure("github_authentication_failed")
        return identity.token
    return get_installation_issuer().token(installation_id, repository_id)


def invalidate_review_token(installation_id, repository_id):
    """Discard a cached scoped token after an authoritative access failure."""
    if get_settings().github_installation_auth_enabled:
        get_installation_issuer().invalidate(installation_id, repository_id)
