"""Bounded evidence-first PR analysis; source is data and never executed."""

import ast
from hashlib import sha256
import re

from app.core.config import get_settings
from app.modules.github.client import GitHubFailure
from app.modules.github.issue_context_client import IssueContextClient
from app.modules.github.source_client import GitHubSourceClient
from app.modules.ingestion.code_selection import contains_sensitive_source
from app.modules.patches.validation import safe_path
from app.modules.pr_review.scanner import RULE_VERSION, scan_changed_file
from app.modules.pr_review.typescript_review import TypeScriptAnalysisUnavailable, runner_digest, scan_typescript

_SHA = re.compile(r"[0-9a-f]{40}\Z")
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?$")
POLICY = {
    "version": "pr-review-v1",
    "max_files": 30,
    "max_file_bytes": 100000,
    "rules": [RULE_VERSION],
    "mode": "deterministic_only",
    "languages": ["python"],
}
POLICY_HASH = sha256(
    __import__("json").dumps(POLICY, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()


def active_policy_hash():
    settings = get_settings()
    if not settings.pr_typescript_review_enabled:
        return POLICY_HASH
    policy = {**POLICY, "languages": ["python", "typescript", "tsx"],
              "rules": [RULE_VERSION, "TS-EVAL-001"],
              "typescript_node_sha256": settings.pr_typescript_node_sha256,
              "typescript_compiler_sha256": settings.pr_typescript_compiler_sha256,
              "typescript_runner_sha256": runner_digest()}
    return sha256(__import__("json").dumps(policy, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class PullClient(IssueContextClient):
    def pull(self, token, name, number):
        return self._get(GitHubSourceClient._repo(name) + f"/pulls/{number}", token)

    def pull_files(self, token, name, number):
        data = self._read(
            GitHubSourceClient._repo(name) + f"/pulls/{number}/files",
            token,
            {"per_page": 100, "page": 1},
        )
        if (
            not isinstance(data, list)
            or len(data) > 100
            or not all(isinstance(item, dict) for item in data)
        ):
            raise GitHubFailure("github_response_invalid")
        return data


def pull_identity(data, repo_id, repo_name, number):
    """Bind GitHub PR identity; only same-repository and explicitly public heads are supported."""
    try:
        base, head = data["base"], data["head"]
        base_repo, head_repo = base["repo"], head["repo"]
        head_id, head_name = head_repo["id"], head_repo["full_name"]
        if (type(data["number"]) is not int or data["number"] != number or data["html_url"] != f"https://github.com/{repo_name}/pull/{number}"
                or type(base_repo["id"]) is not int or base_repo["id"] != repo_id or base_repo["full_name"] != repo_name
                or type(head_id) is not int or not 0 < head_id < 2**63
                or not isinstance(head_name, str)
                or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,149}", head_name)
                or any(part in {".", ".."} for part in head_name.split("/"))
                or (head_id == repo_id) != (head_name == repo_name)
                or (head_id != repo_id and head_repo.get("private") is not False)
                or any(type(sha) is not str or not _SHA.fullmatch(sha) for sha in (base["sha"], head["sha"]))
                or type(data.get("id")) is not int or data["id"] <= 0
                or type(data.get("changed_files")) is not int or not 0 <= data["changed_files"] <= 100000
                or not isinstance(data.get("title"), str) or len(data["title"]) > 1024):
            raise ValueError
        author = data.get("user") or {}
        name = author.get("login") if isinstance(author, dict) else None
        if name is not None and (not isinstance(name, str) or len(name) > 100):
            raise ValueError
        return {"id": data["id"], "number": number, "title": data["title"], "author": name,
                "base_sha": base["sha"], "head_sha": head["sha"],
                "head_repository_id": head_id, "head_repository_name": head_name,
                "changed_files": data["changed_files"]}
    except (KeyError, TypeError, ValueError):
        raise GitHubFailure("pull_request_identity_invalid") from None


def identity_tuple(data):
    return (data["id"], data["base_sha"], data["head_sha"],
            data["head_repository_id"], data["head_repository_name"])


def review_identity(item, repo_name):
    # Prior versions accepted only same-repository heads. Never infer a fork for legacy rows.
    if item.head_repository_id is None and item.head_repository_name is None:
        return (item.github_pr_id, item.base_sha, item.head_sha, item.repository_id, repo_name)
    return (item.github_pr_id, item.base_sha, item.head_sha,
            item.head_repository_id, item.head_repository_name)


def _verified_text(client, token, repo, sha, path, authorize_access):
    authorize_access()
    item = client.tree_file(token, repo, sha, path)
    if (
        not isinstance(item, dict)
        or item.get("path") != path
        or not isinstance(item.get("sha"), str)
        or not _SHA.fullmatch(item["sha"])
        or type(item.get("size")) is not int
        or not 0 <= item["size"] <= POLICY["max_file_bytes"]
    ):
        raise GitHubFailure("source_identity_mismatch")
    authorize_access()
    raw = client.blob(token, repo, item["sha"], item["size"])
    if not isinstance(raw, bytes) or len(raw) != item["size"]:
        raise GitHubFailure("source_identity_mismatch")
    from hashlib import sha1

    if sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest() != item["sha"]:
        raise GitHubFailure("source_identity_mismatch")
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("file_encoding_unsupported") from None
    if "\0" in source or "\r" in source or contains_sensitive_source(source):
        raise ValueError("file_content_unavailable")
    return source, sha256(raw).hexdigest(), item["sha"]


def added_lines(patch, before, after):
    """Verify every supplied hunk against both independently pinned file versions."""
    if not isinstance(patch, str) or not patch or len(patch.encode()) > 200000 or "\r" in patch:
        raise ValueError("patch_unavailable")
    old, new = before.splitlines(), after.splitlines()
    lines = patch.splitlines()
    i = 0
    additions = set()
    deletions = 0
    prior_old = prior_new = 0
    while i < len(lines):
        m = _HUNK.fullmatch(lines[i])
        if not m:
            raise ValueError("patch_invalid")
        start_old, count_old, start_new, count_new = (
            int(m[1]),
            int(m[2] or 1),
            int(m[3]),
            int(m[4] or 1),
        )
        oi, ni = (
            (start_old if count_old == 0 else start_old - 1),
            (start_new if count_new == 0 else start_new - 1),
        )
        if oi < prior_old or ni < prior_new or oi < 0 or ni < 0:
            raise ValueError("patch_invalid")
        if old[prior_old:oi] != new[prior_new:ni]:
            raise ValueError("patch_incomplete")
        old_seen = new_seen = 0
        i += 1
        while i < len(lines) and not lines[i].startswith("@@ "):
            row = lines[i]
            if row == "\\ No newline at end of file":
                i += 1
                continue
            if not row or row[0] not in " +-":
                raise ValueError("patch_invalid")
            if row[0] in " -":
                if oi >= len(old) or old[oi] != row[1:]:
                    raise ValueError("patch_context_mismatch")
                oi += 1
                old_seen += 1
                if row[0] == "-":
                    deletions += 1
            if row[0] in " +":
                if ni >= len(new) or new[ni] != row[1:]:
                    raise ValueError("patch_context_mismatch")
                ni += 1
                new_seen += 1
                if row[0] == "+":
                    additions.add(ni)
            i += 1
        if old_seen != count_old or new_seen != count_new:
            raise ValueError("patch_incomplete")
        prior_old, prior_new = oi, ni
    if old[prior_old:] != new[prior_new:]:
        raise ValueError("patch_incomplete")
    if not additions:
        raise ValueError("no_added_lines")
    return additions, deletions


def analyze_pull(source_client, pull_client, token, repo_id, repo_name, number, *, expected=None, authorize_access=None):
    # The worker supplies a fresh authorization check before each logical GitHub read.
    authorize_access = authorize_access or (lambda: None)
    authorize_access()
    initial = pull_identity(pull_client.pull(token, repo_name, number), repo_id, repo_name, number)
    if expected is not None and identity_tuple(initial) != expected:
        raise GitHubFailure("pull_request_changed")
    if initial["head_repository_id"] != repo_id:
        # A public fork can later become private or be renamed. Reconcile it before
        # every logical read in addition to the base repository's authorization.
        authorize_base = authorize_access

        def authorize_fork():
            authorize_base()
            head_repo = source_client.repository(token, initial["head_repository_name"])
            if (type(head_repo.get("id")) is not int or head_repo["id"] != initial["head_repository_id"]
                    or head_repo.get("full_name") != initial["head_repository_name"]
                    or head_repo.get("private") is not False):
                raise GitHubFailure("pull_request_identity_invalid")

        authorize_access = authorize_fork
    authorize_access()
    records = pull_client.pull_files(token, repo_name, number)
    limitations, files, findings = [], [], []
    if len(records) != initial["changed_files"] or initial["changed_files"] > POLICY["max_files"]:
        limitations.append("changed_file_inventory_incomplete")
    for sha in (initial["base_sha"], initial["head_sha"]):
        authorize_access()
        if source_client.commit(token, repo_name, sha).get("sha") != sha:
            raise GitHubFailure("pull_commit_invalid")
    seen = set()
    for record in records[: POLICY["max_files"]]:
        path, status = record.get("filename"), record.get("status")
        if not isinstance(path, str) or not safe_path(path) or path in seen:
            limitations.append("unsafe_or_duplicate_path")
            continue
        seen.add(path)
        row = {
            "path": path,
            "status": status
            if status
            in {"added", "modified", "removed", "renamed", "copied", "changed", "unchanged"}
            else "unsupported",
            "previous_path": None,
            "additions": record.get("additions") if type(record.get("additions")) is int else None,
            "deletions": record.get("deletions") if type(record.get("deletions")) is int else None,
            "patch": None,
            "coverage": "partial",
            "reason": None,
        }
        files.append(row)
        is_python = path.endswith(".py")
        is_typescript = path.endswith((".ts", ".tsx")) and get_settings().pr_typescript_review_enabled
        if status not in {"added", "modified"} or not (is_python or is_typescript):
            row["reason"] = "unsupported_file_or_operation"
            limitations.append("unsupported_file_or_operation")
            continue
        try:
            source, raw_hash, blob = _verified_text(
                source_client, token, repo_name, initial["head_sha"], path, authorize_access
            )
            before = (
                ""
                if status == "added"
                else _verified_text(source_client, token, repo_name, initial["base_sha"], path, authorize_access)[0]
            )
            patch = record.get("patch")
            selected, removed = added_lines(patch, before, source)
            if row["additions"] != len(selected) or row["deletions"] != removed:
                raise ValueError("patch_incomplete")
            if is_python:
                ast.parse(source)
            if contains_sensitive_source(patch):
                raise ValueError("sensitive_diff")
            row.update(
                patch=patch, coverage="complete", reason=None, source_sha256=raw_hash, blob_sha=blob
            )
            local_findings = []
            candidates = (scan_changed_file(path, source, selected) if is_python
                          else scan_typescript(path, source, selected, get_settings()))
            for candidate in candidates:
                start, end = candidate.get("start_line"), candidate.get("end_line")
                if (
                    candidate.get("path") != path
                    or type(start) is not int
                    or type(end) is not int
                    or start not in selected
                    or end != start
                    or end > len(source.splitlines())
                ):
                    raise ValueError("finding_identity_invalid")
                candidate["evidence"] = {
                    "commit_sha": initial["head_sha"],
                    "file_sha256": raw_hash,
                    "git_blob_sha1": blob,
                    "head_repository_id": str(initial["head_repository_id"]),
                    "head_repository_name": initial["head_repository_name"],
                    "line": start,
                    "changed_line": True,
                }
                local_findings.append(candidate)
            findings.extend(local_findings)
        except TypeScriptAnalysisUnavailable:
            row.update(patch=None, coverage="partial", reason="typescript_analysis_unavailable")
            row.pop("source_sha256", None)
            row.pop("blob_sha", None)
            limitations.append("typescript_analysis_unavailable")
        except (ValueError, SyntaxError, RecursionError, UnicodeError):
            row.update(patch=None, coverage="partial", reason="source_or_patch_unverified")
            row.pop("source_sha256", None)
            row.pop("blob_sha", None)
            limitations.append("source_or_patch_unverified")
    authorize_access()
    final = pull_identity(pull_client.pull(token, repo_name, number), repo_id, repo_name, number)
    if identity_tuple(initial) != identity_tuple(final):
        raise GitHubFailure("pull_request_changed")
    return initial, files, findings, sorted(set(limitations))
