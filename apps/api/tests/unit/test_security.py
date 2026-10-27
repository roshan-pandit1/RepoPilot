import hashlib
import hmac

import pytest

from app.modules.github.security import valid_signature


def test_github_documented_test_vector():
    assert valid_signature(
        b"Hello, World!",
        "sha256=757107ea0eb2509fc211221cce984b8a37570b6d7586c22c46f4379c8b043e17",
        "It's a Secret to Everybody",
    )


@pytest.mark.parametrize("signature", ["", "sha1=bad", "sha256=bad", "sha256=", "é"])
def test_invalid_signature(signature):
    assert not valid_signature(b"payload", signature, "secret")


def test_raw_bytes_are_not_normalized():
    raw = b'{ "title": "hello" }'
    signature = "sha256=" + hmac.new(b"secret", raw, hashlib.sha256).hexdigest()
    assert valid_signature(raw, signature, "secret")
    assert not valid_signature(b'{"title":"hello"}', signature, "secret")
    assert not valid_signature(raw, signature, "other secret")
