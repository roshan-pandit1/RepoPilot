from hashlib import sha256

import pytest

from app.modules.patches.validation import Limits, PatchError, SourceFile, safe_path, validate_patch
from app.modules.patches.workspace import workspace_pair


SOURCE = b"def add(a, b):\n    return a - b\n"
DIFF = "--- a/src/math.py\n+++ b/src/math.py\n@@ -1,2 +1,2 @@\n def add(a, b):\n-    return a - b\n+    return a + b\n"


def source(content=SOURCE, path="src/math.py", digest=None):
    return SourceFile(path, content, digest or sha256(content).hexdigest(), "file-1", ("evidence-1",))


def test_applies_only_in_memory_and_records_hashes():
    original = source()
    changed, = validate_patch(DIFF, (original,))
    assert original.content == SOURCE
    assert changed.content == b"def add(a, b):\n    return a + b\n"
    assert changed.before_sha256 == original.sha256
    assert changed.after_sha256 == sha256(changed.content).hexdigest()
    assert changed.evidence_ids == ("evidence-1",)


@pytest.mark.parametrize("path", ["../x.py", "/tmp/x.py", "a/../x.py", ".github/workflows/a.yml",
                                   ".env", "src/credentials.json", "src/id_rsa", "src/a.pem",
                                   "src\\x.py", "a//x.py", "secrets/config.py"])
def test_forbidden_paths(path):
    assert not safe_path(path)


@pytest.mark.parametrize("diff", [
    DIFF.replace("a/src/math.py", "a/../../secret"),
    DIFF.replace("b/src/math.py", "b/src/other.py"),
    DIFF.replace("a/src/math.py", "/dev/null"),
    DIFF.replace("b/src/math.py", "/dev/null"),
    DIFF.replace("return a - b", "return a * b"),
    DIFF.replace("@@ -1,2 +1,2 @@", "@@ -1,3 +1,2 @@"),
    DIFF.replace("@@ -1,2 +1,2 @@", "@@ -1,2 +8,2 @@"),
    DIFF + DIFF,
    "diff --git a/src/math.py b/src/math.py\nrename from src/math.py\nrename to src/new.py\n",
    DIFF + "\\ No newline at end of file\n",
    DIFF.replace("\n", "\r\n"),
])
def test_rejects_unsafe_malformed_or_stale_diff(diff):
    with pytest.raises(PatchError):
        validate_patch(diff, (source(),))


def test_rejects_mismatched_file_identity_and_unauthorized_evidence():
    with pytest.raises(PatchError, match="invalid_source_identity"):
        validate_patch(DIFF, (source(digest="0" * 64),))
    with pytest.raises(PatchError, match="unauthorized_or_duplicate_path"):
        validate_patch(DIFF, ())
    with pytest.raises(PatchError, match="invalid_source_identity"):
        validate_patch(DIFF, (SourceFile("src/math.py", SOURCE, sha256(SOURCE).hexdigest(), "1", ()),))


def test_limits_cannot_be_relaxed_and_are_enforced():
    with pytest.raises(ValueError):
        Limits(files=6)
    with pytest.raises(PatchError):
        validate_patch(DIFF, (source(),), Limits(changed_lines=1))


def test_unicode_is_not_mistaken_for_a_line_boundary():
    content = "# π\u2028notes\nreturn 1\n".encode()
    diff = "--- a/src/math.py\n+++ b/src/math.py\n@@ -1,2 +1,2 @@\n # π\u2028notes\n-return 1\n+return 2\n"
    changed, = validate_patch(diff, (source(content),))
    assert changed.content == "# π\u2028notes\nreturn 2\n".encode()


def test_disposable_workspaces_keep_baseline_and_patch_separate_and_clean_up():
    original = source()
    changed = validate_patch(DIFF, (original,))
    with workspace_pair((original,), changed) as (baseline, patched):
        assert (baseline / original.path).read_bytes() == SOURCE
        assert (patched / original.path).read_bytes() == changed[0].content
        assert (baseline.stat().st_mode & 0o777) == 0o700
        assert ((patched / original.path).stat().st_mode & 0o777) == 0o600
        temporary_root = baseline.parent
    assert not temporary_root.exists()


def test_disposable_workspace_rejects_changed_identity():
    original = source()
    changed, = validate_patch(DIFF, (original,))
    from dataclasses import replace
    with pytest.raises(PatchError, match="invalid_result_identity"):
        with workspace_pair((original,), (replace(changed, after_sha256="0" * 64),)):
            pytest.fail("must not create a workspace")
