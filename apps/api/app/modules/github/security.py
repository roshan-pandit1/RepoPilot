"""GitHub signature verification over the exact received bytes."""
import hashlib
import hmac


def valid_signature(raw: bytes, signature: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature.encode(), expected.encode())
