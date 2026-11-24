"""Prepare private baseline and patched files; never execute their contents.

This is not an untrusted-code sandbox. It is not called by the unavailable
execution adapter and grants no authority to run repository tests.
"""
from contextlib import contextmanager
from hashlib import sha256
import os
from pathlib import Path
import tempfile

from app.modules.patches.validation import ChangedFile, PatchError, SourceFile, safe_path


def _write(root_fd: int, relative: str, content: bytes):
    parts = relative.split("/")
    directory = os.dup(root_fd)
    try:
        for component in parts[:-1]:
            try:
                os.mkdir(component, 0o700, dir_fd=directory)
            except FileExistsError:
                pass
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
    finally:
        os.close(directory)


@contextmanager
def workspace_pair(files: tuple[SourceFile, ...], changed: tuple[ChangedFile, ...]):
    """Stage validated, bounded file bytes under newly owned private directories."""
    originals = {f.path: f for f in files}
    modifications = {f.path: f for f in changed}
    if (not files or not changed or len(files) > 5 or len(originals) != len(files)
            or len(modifications) != len(changed) or not modifications.keys() <= originals.keys()):
        raise PatchError("invalid_workspace_inventory")
    total = 0
    for file in files:
        total += len(file.content)
        if (not safe_path(file.path) or len(file.content) > 1024 * 1024
                or sha256(file.content).hexdigest() != file.sha256):
            raise PatchError("invalid_source_identity")
    for path, file in modifications.items():
        original = originals[path]
        if (file.file_id != original.file_id or file.before_sha256 != original.sha256
                or len(file.content) > 1024 * 1024 or sha256(file.content).hexdigest() != file.after_sha256):
            raise PatchError("invalid_result_identity")
    if total > 5 * 1024 * 1024:
        raise PatchError("workspace_size_limit")
    with tempfile.TemporaryDirectory(prefix="repopilot-patch-") as temp:
        root = Path(temp)
        os.chmod(root, 0o700)
        for name in ("baseline", "patched"):
            directory = root / name
            directory.mkdir(mode=0o700)
            root_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                for file in files:
                    content = modifications[file.path].content if name == "patched" and file.path in modifications else file.content
                    _write(root_fd, file.path, content)
            finally:
                os.close(root_fd)
        yield root / "baseline", root / "patched"
