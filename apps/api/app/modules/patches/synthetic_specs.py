"""Immutable execution allowlist. These are original inert fixture bytes."""
from dataclasses import dataclass
from hashlib import sha256

from app.modules.patches.validation import PatchError, SourceFile, validate_patch

REPOSITORY = "repopilot-fixtures/patch-p4"
COMMIT = "d" * 40  # Explicit synthetic identity; not a Git provenance claim.
SNAPSHOT = "44444444-4444-4444-8444-444444444444"
SOURCE_PATH = "src/calc.py"
TEST_PATH = "test_add.py"
TEST_SOURCE = (b'import sys\nsys.path.insert(0, "/fixture/src")\nfrom calc import add\ntry:\n'
               b'    assert add(1, 2) == 3\n    assert add(-4, 7) == 3\nexcept AssertionError:\n'
               b'    print("FAIL")\n    raise SystemExit(1)\nprint("PASS")\n')
TEST_SHA256 = "fddc8d811a1a9ff714cd8fff650da62a9e9d5f0a5daf7e2d9eee062c4a5855fe"
BAD_SOURCE = b"def add(a, b):\n    return a - b\n"
GOOD_SOURCE = b"def add(a, b):\n    return a + b\n"
FIX_BAD = ("--- a/src/calc.py\n+++ b/src/calc.py\n@@ -1,2 +1,2 @@\n"
           " def add(a, b):\n-    return a - b\n+    return a + b\n")
FIX_GOOD = ("--- a/src/calc.py\n+++ b/src/calc.py\n@@ -1,2 +1,2 @@\n"
            " def add(a, b):\n-    return a + b\n+    return (a + b)\n")
IMAGE = "sha256:839d58f92f8cd1fbf52e766934434133ed5c35f2d7adbdffa665ac393597ca9b"


@dataclass(frozen=True)
class FixtureSpec:
    id: str
    source: bytes
    source_sha256: str
    patch: str
    patch_sha256: str
    patched_sha256: str
    version: str = "p4-test-spec-v1"
    fixture_repository: str = REPOSITORY
    fixture_commit: str = COMMIT
    fixture_snapshot: str = SNAPSHOT
    test_sha256: str = TEST_SHA256
    image: str = IMAGE
    executable: str = "/usr/local/bin/python"
    arguments: tuple[str, ...] = ("-I", "-B", "/fixture/test_add.py")
    cwd: str = "/fixture"
    timeout_seconds: int = 10
    memory_bytes: int = 128 * 1024 * 1024
    pids: int = 8
    cpu_nanos: int = 1_000_000_000
    environment: tuple[str, ...] = ("PATH=/usr/bin:/bin", "HOME=/nonexistent", "LANG=C.UTF-8")
    output_bytes: int = 4096
    format: str = "PASS-or-FAIL-v1"
    cleanup: str = "remove-owned-container-and-private-workspace"


SPECS = (
    FixtureSpec("synthetic-add-reproducer-v1", BAD_SOURCE,
        "e1a894022d1a082987b87adecb623438c9e386d86b2b621cff4a5fe7fdf7edc8", FIX_BAD,
        "7833b06cfe4eb2dbf373cef7aa6c0c4bf40447a42cb28b5ebbfbec4e294d41d8",
        "ba1a531f581d2e6094e978ed6f7aca7a8d92eeb62c6e7ad73ee692f7f18bc772"),
    FixtureSpec("synthetic-add-already-passes-v1", GOOD_SOURCE,
        "ba1a531f581d2e6094e978ed6f7aca7a8d92eeb62c6e7ad73ee692f7f18bc772", FIX_GOOD,
        "34a4f382315e6e2043afc17d1088f15426ee505e7fb116ac0b28f937cf0bf082",
        "7b3468a0529aec1a0e194719c214b86a2d7f561ee05ab61b73bef7bac7e0c788"),
)


def select_spec(repository: str, context, diff: str):
    """No caller can supply a command, a new fixture, or external source bytes."""
    if (repository != REPOSITORY or context.commit_sha != COMMIT or context.snapshot_id != SNAPSHOT
            or len(context.files) != 1 or context.files[0].path != SOURCE_PATH):
        raise PatchError("synthetic_fixture_not_allowed")
    file = context.files[0]
    if sha256(TEST_SOURCE).hexdigest() != TEST_SHA256:
        raise PatchError("synthetic_fixture_integrity")
    for spec in SPECS:
        if (file.content == spec.source and file.sha256 == spec.source_sha256
                and sha256(file.content).hexdigest() == spec.source_sha256 and diff == spec.patch
                and sha256(diff.encode()).hexdigest() == spec.patch_sha256):
            changed = validate_patch(diff, context.files)
            if len(changed) != 1 or changed[0].after_sha256 != spec.patched_sha256:
                raise PatchError("synthetic_fixture_integrity")
            test_file = SourceFile(TEST_PATH, TEST_SOURCE, TEST_SHA256, "trusted-test", ("trusted-test",))
            return spec, (*context.files, test_file), changed
    raise PatchError("synthetic_fixture_not_allowed")
