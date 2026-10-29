"""Test-only, bounded reader of a single local Git commit; never executes source."""
import re
import subprocess
from pathlib import Path


class GitSource:
    def __init__(self, repo: Path, commit: str, full_name: str):
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("Expected a full SHA-1 commit")
        self.repo, self.sha, self.full_name = repo.resolve(), commit, full_name
        if self._git("rev-parse", "--verify", f"{commit}^{{commit}}").strip().decode() != commit:
            raise ValueError("Commit does not resolve exactly")
        self.entries = []
        self.blobs = {}
        tree = self._git("ls-tree", "-rz", "-l", "--full-tree", commit)
        if len(tree) > 4_000_000:
            raise ValueError("Git tree too large")
        for record in tree.split(b"\0"):
            if not record:
                continue
            meta, path = record.split(b"\t", 1)
            mode, kind, sha, size = meta.split()
            if kind != b"blob" or mode not in (b"100644", b"100755"):
                continue
            path = path.decode("utf-8")
            blob = sha.decode("ascii")
            entry = {"path": path, "type": "blob", "mode": mode.decode(),
                     "sha": blob, "size": int(size)}
            self.entries.append(entry)
            self.blobs[blob] = entry["size"]
        if len(self.entries) > 10000:
            raise ValueError("Git tree exceeds entry limit")

    def _git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30).stdout

    def _name(self, full_name):
        if full_name != self.full_name:
            raise ValueError("Unexpected repository")

    def repository(self, token, full_name):
        self._name(full_name)
        return {"private": False, "full_name": full_name, "default_branch": "pinned"}

    def commit(self, token, full_name, branch):
        self._name(full_name)
        if branch != "pinned":
            raise ValueError("Unexpected branch")
        return {"sha": self.sha}

    def tree(self, token, full_name, sha):
        self._name(full_name)
        if sha != self.sha:
            raise ValueError("Unexpected commit")
        return {"truncated": False, "tree": list(self.entries)}

    def blob(self, token, full_name, sha, expected_size):
        self._name(full_name)
        if self.blobs.get(sha) != expected_size or expected_size > 100_000:
            raise ValueError("Unknown or oversized blob")
        data = self._git("cat-file", "blob", sha)
        if len(data) != expected_size:
            raise ValueError("Blob size mismatch")
        return data
