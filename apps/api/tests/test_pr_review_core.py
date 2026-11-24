"""Verify pinned PR evidence without executing repository data."""

from hashlib import sha1

import pytest

from app.modules.github.client import GitHubFailure
from app.modules.pr_review import core


def test_complete_diff_checks_both_hunks_and_unchanged_gaps():
    before = "one\ntwo\nthree\nfour\n"
    after = "one\nTWO\nthree\nFOUR\n"
    patch = "@@ -1,4 +1,4 @@\n one\n-two\n+TWO\n three\n-four\n+FOUR"
    assert core.added_lines(patch, before, after) == ({2, 4}, 2)
    with pytest.raises(ValueError, match="patch_incomplete"):
        core.added_lines("@@ -1,2 +1,2 @@\n one\n-two\n+TWO", before, after)
    with pytest.raises(ValueError, match="patch_context_mismatch"):
        core.added_lines(patch.replace("+TWO", "+fake"), before, after)


def test_mismatched_gap_rejected():
    with pytest.raises(ValueError, match="patch_incomplete"):
        core.added_lines("@@ -3,1 +3,1 @@\n-c\n+C", "a\nb\nc\n", "a\nx\nC\n")


BASE = "1" * 40
HEAD = "2" * 40
OLD = "import subprocess\ndef run(x):\n    return x\n"
NEW = "import subprocess\ndef run(x):\n    return subprocess.run(f'{x}', shell=True)\n"
PATCH = "@@ -1,3 +1,3 @@\n import subprocess\n def run(x):\n-    return x\n+    return subprocess.run(f'{x}', shell=True)"


class Source:
    def commit(self, token, repo, sha):
        return {"sha": sha}

    def tree_file(self, token, repo, sha, path):
        raw = (OLD if sha == BASE else NEW).encode()
        blob = sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        return {"path": path, "sha": blob, "size": len(raw)}

    def blob(self, token, repo, blob, expected_size):
        for raw in (OLD.encode(), NEW.encode()):
            if sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == blob:
                return raw
        raise AssertionError("unrecognized blob")


class Pull:
    def __init__(self):
        self.calls = 0
        self.changed = False
        self.patch = PATCH

    def pull(self, token, repo, number):
        self.calls += 1
        head = "3" * 40 if self.changed and self.calls == 2 else HEAD
        return {
            "id": 42,
            "number": number,
            "title": "A review",
            "html_url": f"https://github.com/{repo}/pull/{number}",
            "user": {"login": "author"},
            "changed_files": 1,
            "base": {"sha": BASE, "repo": {"id": 10, "full_name": repo}},
            "head": {"sha": head, "repo": {"id": 10, "full_name": repo}},
        }

    def pull_files(self, token, repo, number):
        return [
            {
                "filename": "src/example.py",
                "status": "modified",
                "additions": 1,
                "deletions": 1,
                "patch": self.patch,
            }
        ]


def test_pinned_evidence_and_changed_line():
    meta, files, findings, limitations = core.analyze_pull(
        Source(), Pull(), "token", 10, "owner/repo", 3
    )
    assert meta["head_sha"] == HEAD and not limitations
    assert files[0]["coverage"] == "complete"
    assert len(findings) == 1 and findings[0]["evidence"]["commit_sha"] == HEAD
    assert findings[0]["start_line"] == 3


def test_changed_head_is_not_accepted():
    pull = Pull()
    pull.changed = True
    with pytest.raises(GitHubFailure, match="pull_request_changed"):
        core.analyze_pull(Source(), pull, "token", 10, "owner/repo", 3)


def test_bad_diff_cannot_be_published_as_complete():
    pull = Pull()
    pull.patch = PATCH.replace("return x", "not the old line")
    _, files, findings, limitations = core.analyze_pull(
        Source(), pull, "token", 10, "owner/repo", 3
    )
    assert files[0]["coverage"] == "partial" and files[0]["patch"] is None
    assert not findings and "source_or_patch_unverified" in limitations


def test_bad_finding_cannot_publish_previously_verified_diff(monkeypatch):
    monkeypatch.setattr(
        core, "scan_changed_file", lambda *a: [{"path": "other.py", "start_line": 3, "end_line": 3}]
    )
    _, files, findings, limitations = core.analyze_pull(
        Source(), Pull(), "token", 10, "owner/repo", 3
    )
    assert files[0]["coverage"] == "partial" and files[0]["patch"] is None
    assert not findings and "source_or_patch_unverified" in limitations


def test_fork_head_is_rejected():
    pull = Pull()
    info = pull.pull("token", "owner/repo", 3)
    info["head"]["repo"]["id"] = 11
    with pytest.raises(GitHubFailure, match="pull_request_identity_invalid"):
        core.pull_identity(info, 10, "owner/repo", 3)


def test_github_rate_limit_during_blob_fetch_fails_review():
    class LimitedSource(Source):
        def blob(self, token, repo, blob, expected_size):
            raise GitHubFailure("github_rate_limited")
    with pytest.raises(GitHubFailure, match="github_rate_limited"):
        core.analyze_pull(LimitedSource(), Pull(), "token", 10, "owner/repo", 3)


def test_source_blob_mismatch_is_not_published_as_partial():
    class MismatchedSource(Source):
        def blob(self, token, repo, blob, expected_size):
            return b"x" * expected_size
    with pytest.raises(GitHubFailure, match="source_identity_mismatch"):
        core.analyze_pull(MismatchedSource(), Pull(), "token", 10, "owner/repo", 3)


def test_revocation_before_blob_prevents_further_source_reads():
    calls = []

    class TrackingSource(Source):
        def blob(self, *args):
            calls.append("blob")
            return super().blob(*args)

    checks = 0

    def authorize():
        nonlocal checks
        checks += 1
        if checks == 6:
            raise GitHubFailure("authorization_revoked")

    with pytest.raises(GitHubFailure, match="authorization_revoked"):
        core.analyze_pull(TrackingSource(), Pull(), "token", 10, "owner/repo", 3,
                          authorize_access=authorize)
    assert checks == 6
    assert calls == []


class ForkPull(Pull):
    def pull(self, token, repo, number):
        result = super().pull(token, repo, number)
        result["head"]["repo"] = {"id": 11, "full_name": "contributor/fork", "private": False}
        return result


class ForkSource(Source):
    def repository(self, token, repo):
        assert repo == "contributor/fork"
        return {"id": 11, "full_name": repo, "private": False}

    def commit(self, token, repo, sha):
        # Fork objects are read through the authorized base only; never via a fork URL.
        assert repo == "owner/repo"
        return super().commit(token, repo, sha)

    def tree_file(self, token, repo, sha, path):
        assert repo == "owner/repo"
        return super().tree_file(token, repo, sha, path)

    def blob(self, token, repo, blob, expected_size):
        assert repo == "owner/repo"
        return super().blob(token, repo, blob, expected_size)


def test_public_fork_uses_pinned_head_and_authorized_base_objects():
    meta, files, findings, _ = core.analyze_pull(ForkSource(), ForkPull(), "token", 10, "owner/repo", 3)
    assert meta["head_repository_id"] == 11 and meta["head_repository_name"] == "contributor/fork"
    assert files[0]["coverage"] == "complete" and len(findings) == 1
    assert findings[0]["evidence"]["head_repository_id"] == "11"
    assert findings[0]["evidence"]["commit_sha"] == HEAD


@pytest.mark.parametrize("repo_metadata", [
    {"id": 12, "full_name": "contributor/fork", "private": False},
    {"id": 11, "full_name": "attacker/fork", "private": False},
    {"id": 11, "full_name": "contributor/fork", "private": True},
    {"id": 11, "full_name": "contributor/fork"},
])
def test_public_fork_metadata_must_match_and_remain_public(repo_metadata):
    class Changed(ForkSource):
        def repository(self, *args):
            return repo_metadata
        def commit(self, *args):
            pytest.fail("unverified fork must not retrieve source")
    with pytest.raises(GitHubFailure, match="pull_request_identity_invalid"):
        core.analyze_pull(Changed(), ForkPull(), "token", 10, "owner/repo", 3)


def test_changed_fork_identity_is_rejected_before_source():
    class Changed(ForkPull):
        def pull(self, *args):
            result = super().pull(*args)
            result["head"]["repo"] = {"id": 12, "full_name": "other/fork", "private": False}
            return result
    with pytest.raises(GitHubFailure, match="pull_request_changed"):
        core.analyze_pull(ForkSource(), Changed(), "token", 10, "owner/repo", 3,
                          expected=(42, BASE, HEAD, 11, "contributor/fork"))


def test_private_and_deleted_fork_cannot_be_pinned():
    data = ForkPull().pull("token", "owner/repo", 3)
    data["head"]["repo"]["private"] = True
    with pytest.raises(GitHubFailure):
        core.pull_identity(data, 10, "owner/repo", 3)
    data["head"]["repo"] = None
    with pytest.raises(GitHubFailure):
        core.pull_identity(data, 10, "owner/repo", 3)


def test_fork_turning_private_stops_before_blob():
    class BecomesPrivate(ForkSource):
        private = False
        def repository(self, token, repo):
            return {"id": 11, "full_name": repo, "private": self.private}
        def tree_file(self, *args):
            item = super().tree_file(*args)
            self.private = True
            return item
        def blob(self, *args):
            pytest.fail("private fork must not fetch a new blob")
    with pytest.raises(GitHubFailure, match="pull_request_identity_invalid"):
        core.analyze_pull(BecomesPrivate(), ForkPull(), "token", 10, "owner/repo", 3)


def test_fork_missing_pinned_head_commit_fails_before_content():
    class MissingHead(ForkSource):
        def commit(self, token, repo, sha):
            if sha == HEAD:
                raise GitHubFailure("github_not_found")
            return super().commit(token, repo, sha)
        def tree_file(self, *args):
            pytest.fail("missing head must not read source")
    with pytest.raises(GitHubFailure, match="github_not_found"):
        core.analyze_pull(MissingHead(), ForkPull(), "token", 10, "owner/repo", 3)


def test_fork_swapped_base_and_head_is_not_the_pinned_review():
    class Swapped(ForkPull):
        def pull(self, *args):
            result = super().pull(*args)
            result["base"]["sha"], result["head"]["sha"] = HEAD, BASE
            return result
    with pytest.raises(GitHubFailure, match="pull_request_changed"):
        core.analyze_pull(ForkSource(), Swapped(), "token", 10, "owner/repo", 3,
                          expected=(42, BASE, HEAD, 11, "contributor/fork"))


def test_fork_replaced_during_scan_fails_before_publication():
    class Replaced(ForkPull):
        def pull(self, *args):
            result = super().pull(*args)
            if self.calls == 2:
                result["head"]["repo"] = {"id": 12, "full_name": "other/fork", "private": False}
            return result
    with pytest.raises(GitHubFailure, match="pull_request_changed"):
        core.analyze_pull(ForkSource(), Replaced(), "token", 10, "owner/repo", 3)


def test_pull_identity_rejects_boolean_numeric_ids():
    item = ForkPull().pull("token", "owner/repo", 3)
    item["base"]["repo"]["id"] = True
    with pytest.raises(GitHubFailure):
        core.pull_identity(item, 1, "owner/repo", 3)
    item = ForkPull().pull("token", "owner/repo", 3)
    item["number"] = True
    item["html_url"] = "https://github.com/owner/repo/pull/1"
    with pytest.raises(GitHubFailure):
        core.pull_identity(item, 10, "owner/repo", 1)


def test_typescript_parser_failure_never_marks_file_clean(monkeypatch):
    from app.core.config import get_settings
    from app.modules.pr_review.typescript_review import TypeScriptAnalysisUnavailable
    monkeypatch.setattr(get_settings(), "pr_typescript_review_enabled", True)
    monkeypatch.setattr(core, "scan_typescript", lambda *args: (_ for _ in ()).throw(TypeScriptAnalysisUnavailable("crash")))
    class TSPull(Pull):
        def pull_files(self, *args):
            return [{"filename": "src/demo.ts", "status": "modified", "additions": 1,
                     "deletions": 1, "patch": PATCH}]
    _, files, findings, limitations = core.analyze_pull(Source(), TSPull(), "token", 10, "owner/repo", 3)
    assert files[0]["coverage"] == "partial" and files[0]["reason"] == "typescript_analysis_unavailable"
    assert not findings and "typescript_analysis_unavailable" in limitations


def test_typescript_policy_fences_runtime_configuration(monkeypatch):
    from app.core.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "pr_typescript_review_enabled", False)
    base = core.active_policy_hash()
    monkeypatch.setattr(settings, "pr_typescript_review_enabled", True)
    monkeypatch.setattr(settings, "pr_typescript_node_sha256", "a" * 64)
    first = core.active_policy_hash()
    monkeypatch.setattr(settings, "pr_typescript_node_sha256", "b" * 64)
    assert first != base and core.active_policy_hash() != first
    second = core.active_policy_hash()
    monkeypatch.setattr(core, "runner_digest", lambda: "changed-runner")
    assert core.active_policy_hash() != second
