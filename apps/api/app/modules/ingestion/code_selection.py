"""Conservative selection of candidate Python source from untrusted GitHub trees.

This is not a secret scanner: selecting a path never proves its contents are safe.
"""
from pathlib import PurePosixPath
import re

_EXCLUDED = frozenset({
    ".git", ".venv", "venv", "env", "node_modules", "vendor", "dist", "build",
    "__pycache__", ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".next", "site-packages", "generated", "migrations",
})


def eligible_python_path(path: str) -> bool:
    """Accept only normalized, relative Python paths outside excluded directories."""
    if not path or "\\" in path or "\x00" in path or path.startswith("/"):
        return False
    parts = path.split("/")
    if any(part in {"", ".", ".."} or part.lower() in _EXCLUDED for part in parts):
        return False
    name = parts[-1].lower()
    if name.startswith(".") or any(marker in name for marker in ("secret", "credential", "private_key")):
        return False
    return PurePosixPath(path).suffix == ".py"


def eligible_source_path(path: str, *, multilingual: bool = True, exclude_generated: bool = False) -> bool:
    """Use the existing path exclusions for each explicitly registered extension."""
    if not multilingual:
        return eligible_python_path(path)
    from app.modules.ingestion.language_analysis import LANGUAGES

    if not path or PurePosixPath(path).suffix.lower() not in LANGUAGES:
        return False
    name = PurePosixPath(path).name.lower()
    if exclude_generated and (".generated." in name or name.endswith((".min.js", ".min.mjs", ".g.cs",
                                                                       ".designer.cs", ".pb.go", ".pb.gw.go", ".gen.go"))):
        return False
    # Reuse every existing path and credential-name restriction unchanged.
    return eligible_python_path(path + ".py")


def decode_source(data: bytes, max_bytes: int) -> str | None:
    """Accept bounded, valid UTF-8 text; leave source line endings unchanged."""
    if max_bytes <= 0 or len(data) > max_bytes or b"\x00" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def incompatible_line_endings(source: str) -> bool:
    """Reject separators that differ between Python line slicing and GitHub LF lines."""
    return (any(c in source for c in ("\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"))
            or "\r" in source.replace("\r\n", ""))


_SENSITIVE = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)


def contains_sensitive_source(source: str) -> bool:
    """Reject entire files with recognizable credentials; not comprehensive scanning."""
    return any(pattern.search(source) for pattern in _SENSITIVE)
