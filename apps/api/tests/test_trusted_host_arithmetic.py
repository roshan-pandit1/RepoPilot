"""Negative checks only: these tests never execute the trusted fixture."""
import pytest

from app.modules.patches.validation import PatchError
from evaluation import trusted_host_arithmetic as runner


@pytest.mark.parametrize("attribute,replacement", [
    ("BAD", b"def add(a: int, b: int) -> int:\n    return a * b\n"),
    ("GOOD", b"def add(a: int, b: int) -> int:\n    return a * b\n"),
    ("TEST", b"assert add(2, 3) == 6\n"),
    ("PATCH", "unexpected diff"),
])
def test_mutated_bytes_never_reach_subprocess(monkeypatch, attribute, replacement):
    monkeypatch.setattr(runner, attribute, replacement)
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **kw: pytest.fail("subprocess started"))
    with pytest.raises(PatchError, match="trusted_fixture_mismatch"):
        runner.run_trusted()


@pytest.mark.parametrize("control", [None, 0, 1, "yes", object()])
def test_unapproved_selector_is_rejected_before_subprocess(monkeypatch, control):
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **kw: pytest.fail("subprocess started"))
    with pytest.raises(PatchError, match="trusted_fixture_mismatch"):
        runner.run_trusted(control=control)


def test_retained_patch_mismatch_fails_closed(tmp_path, monkeypatch):
    path = tmp_path / "wrong.diff"
    path.write_bytes(b"wrong")
    monkeypatch.setattr(runner, "RETAINED_PATCH", path)
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **kw: pytest.fail("subprocess started"))
    with pytest.raises(PatchError, match="retained_patch_mismatch"):
        runner.run_trusted()


def test_missing_retained_patch_is_distinguished_as_deterministic(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RETAINED_PATCH", tmp_path / "missing.diff")
    assert runner._verify_fixed_bytes() == "deterministic_fixture"
