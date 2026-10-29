"""Construct commit-pinned links without trusting repository or path input as a URL."""
import re
from urllib.parse import quote

from app.modules.ingestion.code_selection import eligible_python_path


def github_citation(full_name: str, commit: str, path: str, start: int, end: int) -> str:
    parts = full_name.split("/")
    if (len(parts) != 2 or any(not part or part in {".", ".."} or "\\" in part for part in parts)
            or not re.fullmatch(r"[0-9a-f]{40}", commit) or not eligible_python_path(path)
            or not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int)
            or isinstance(end, bool) or start < 1 or end < start):
        raise ValueError("invalid_citation")
    base = "https://github.com/" + "/".join(quote(part, safe="") for part in parts)
    return f"{base}/blob/{commit}/{quote(path, safe='/')}#L{start}-L{end}"
