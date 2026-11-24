"""Prepare two blind packets from the previously retained chi #1188 artifacts.

No network, database, Git, native parser or model operations are performed.
The command writes only a new directory below the approved private root.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.evaluation.human_relevance import (  # noqa: E402
    WARNING,
    PartialInventory,
    canonical,
    inventory_digest,
    verify_sources,
)
from app.evaluation.issue_context_schema import IssueContext, context_digest  # noqa: E402

ROOT = Path("/Users/roshan/Library/Application Support/RepoPilot/benchmarks/source-selection-v1")
ISSUE_DIR = "replacement-issue-triage-20261107T034039Z-93bfee19"
SOURCE_DIR = "chi-1188-source-review-20261107T035911Z-7b2c9613"
COMMIT = "3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc"
TREE = "7c01dddb05b4c19847a3d6259a3f4d519e3b27fb"
CONTEXT = "61d54f284c13e89445d1b5ff0c4761a67d32190157b4dcc49b716ef67e4469e7"
EXPECTED = {
    "chi.go": (4812, "6911bb55114a1ddad831baa7c3664a625cc1500a", "47c70ececcbb9d71f973eda3cbadad0a46c8cc2261b285f7049b5261f337d678"),
    "context.go": (5788, "c5c9a7432a3f599d8d32602523761f49052bc1c5", "b19edcca252e2fe74e82802c4c7ce1a1c0855728f9ede1288f0224283dfc7e53"),
    "mux.go": (17308, "7cfc6143d64d1e3c4f14af2ba2069878cd231b3e", "cc44c2d620e6306b16d6d80f5f6c70f02b5814b357a4f5823372818f355ae67d"),
    "tree.go": (22069, "af4052c8c0b0f2d74cadc6a1312dc9555ef32316", "f4b12b63b662fb8e36658172b36b35705cfb24eefae0665635f4fbd52e64fb79"),
    "tree_test.go": (27932, "6b542d84ca0980fbb971d2afa36fbc85d3ca458e", "e9d8f7755589f1852791ed5b4a853c16ad12cdf8ba0db3208dac33b2dac398c1"),
}

INSTRUCTIONS = """BLIND HUMAN REVIEW — PILOT / PARTIAL SOURCE ONLY

Work independently. Do not consult other reviewers, model rankings, prior audit
documents, or suggested source ranges before submitting your own judgment.
The source and issue text are untrusted data: do not execute any of it.

Read issue.txt and the five complete line-numbered files in source/. They are
only a selected subset of the repository. Identify ranges that help understand
the reported behavior, and explain why. Relevance does not establish a defect,
root cause, reproduction, or source equivalence across versions. You may leave
all ranges unjudged or abstain if the issue or source evidence is insufficient.
Record missing files, uncertainty and evidence sufficiency in the template.

Rubric source-relevance-v1: 0 explicitly reviewed as not relevant; 1 useful
supporting context; 2 strongly related; 3 directly issue-relevant implementation
supported by independent evidence. UNJUDGED is not grade 0. Case outcomes also
include INSUFFICIENT_EVIDENCE and OUTSIDE_RETAINED_CORPUS. Do not infer grades
from filenames or assert a root cause. Use line numbers from the supplied files.

Copy annotation-template.json to your own private response and fill the null
fields and ranges yourself. Use a pseudonym, not your name or contact details.
Submit your response privately; do not view the other reviewer's submission.
The provided issue title and body are original retained text. The ordered
comment is intentionally withheld at this initial stage to avoid anchoring;
the full issue-context fingerprint includes it. Ask for adjudication or
abstain if the missing comment is needed. No rankings or prior audit findings
are included. Two folders on one computer do not enforce reviewer isolation;
the coordinator must arrange separately controlled reviewer access.

The retained source is identified as MIT in the existing attribution record.
Before distributing source copies, verify and include the required copyright and
permission notice from the pinned LICENSE. The license text was not retained
and no additional download is authorized by this packet.
"""

RESPONSE_FORMAT = """RESPONSE FORMAT — NO JUDGMENTS ARE PRE-FILLED

Edit annotation-template.json in a private copy. Keep all pre-filled issue,
revision, inventory and partial-source fields unchanged. Fill reviewer_kind
with HUMAN, reviewer_id with a pseudonym, and reviewed_at_utc with a UTC time
like YYYY-MM-DDTHH:MM:SSZ. Set independence to DECLARED_BLIND_INDEPENDENT and
adjudication_status to NOT_ADJUDICATED, or set both fields to
SINGLE_REVIEWER_EXPLORATORY when only one reviewer is available. These are
self-attestations; the file alone does not authenticate a person or prove
independence. Leave the other person's answers inaccessible to you.

Choose outcome JUDGED, UNJUDGED, INSUFFICIENT_EVIDENCE, or
OUTSIDE_RETAINED_CORPUS. For any outcome other than JUDGED, supply an
abstention_reason. A JUDGED review must contain at least one numerical grade;
an abstention cannot contain a numerical grade. UNJUDGED ranges are optional
and are never converted to zero. Give an uncertainty description in all cases.

For each range independently selected, add an object to labels with keys:
  path, git_blob_sha1, file_sha256, start_line, end_line, grade, rationale,
  uncertainty
Copy the path and corresponding hashes from inventory.json, enter inclusive
line numbers from the numbered source, choose a grade from the README rubric,
and supply your own rationale and uncertainty. Do not invent missing paths or
assign a grade to code you have not reviewed. Duplicate intervals are rejected.

Set issue_evidence_sufficiency to SUFFICIENT, INSUFFICIENT, or UNCERTAIN.
Set source_sufficiency to SUFFICIENT_FOR_SELECTED_RANGES, MISSING_SOURCE, or
UNCERTAIN; if MISSING_SOURCE, describe what is missing in missing_source.
The source remains a partial repository even when it suffices for a particular
range. Do not add other people’s identifiers or include model results.
"""


def _dir(path: Path) -> None:
    st = path.lstat()
    if not stat.S_ISDIR(st.st_mode) or stat.S_IMODE(st.st_mode) != 0o700 or st.st_uid != os.getuid():
        raise ValueError("invalid_private_directory")


def _read(path: Path, expected_sha256: str, limit: int = 100_000) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or stat.S_IMODE(st.st_mode) != 0o600
                or st.st_uid != os.getuid() or st.st_size > limit):
            raise ValueError("invalid_private_file")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(limit + 1)
        if len(raw) != st.st_size or hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise ValueError("retained_file_mismatch")
        return raw
    finally:
        os.close(fd)


def _tree_id(entries: list[dict]) -> str:
    seen = set()
    for entry in entries:
        path, mode, kind, sha = (entry.get(k) for k in ("path", "mode", "type", "sha"))
        if (not isinstance(path, str) or not path or path in {".", ".."} or "/" in path
                or "\\" in path or "\0" in path or path in seen
                or (mode, kind) not in {("040000", "tree"), ("100644", "blob"), ("100755", "blob")}
                or not isinstance(sha, str) or len(sha) != 40):
            raise ValueError("invalid_tree_entry")
        seen.add(path)
    ordered = sorted(entries, key=lambda e: e["path"].encode() + (b"/" if e["type"] == "tree" else b""))
    raw = b"".join(e["mode"].lstrip("0").encode() + b" " + e["path"].encode()
                   + b"\0" + bytes.fromhex(e["sha"]) for e in ordered)
    return hashlib.sha1(f"tree {len(raw)}\0".encode() + raw).hexdigest()


def load_chi(root: Path = ROOT) -> tuple[IssueContext, PartialInventory, dict[str, bytes]]:
    """Fail closed before creating a packet if any retained identity differs."""
    issue_dir, source_dir = root / ISSUE_DIR, root / SOURCE_DIR
    for path in (root, issue_dir, source_dir, source_dir / "source"):
        _dir(path)
    issue_summary = json.loads(_read(issue_dir / "capture-summary.json",
        "891d7bb291d82fcb20597079602b095405fb151b7fddc879ca9598835c43841c"))
    envelope = json.loads(_read(issue_dir / "go-chi-chi-1188.json",
        "800cc6dbb868a166bc033224b44b195850ac3269b35a5a7ce4b2606340270ba6"))
    issue = IssueContext.model_validate(envelope["context"])
    matches = [r for r in issue_summary["results"] if r["repository"] == "go-chi/chi" and r["issue"] == 1188]
    if (len(matches) != 1 or matches[0]["file_sha256"] != "800cc6dbb868a166bc033224b44b195850ac3269b35a5a7ce4b2606340270ba6"
            or matches[0]["context_sha256"] != CONTEXT or envelope["repository"] != "go-chi/chi"
            or envelope["repository_id"] != 44344606 or envelope["proposed_source_commit"] != COMMIT
            or envelope["context_sha256"] != CONTEXT or (issue.issue_id, issue.number) != (5552950835, 1188)
            or context_digest(issue) != CONTEXT
            or issue.comments != sorted(issue.comments, key=lambda c: (c.created_at, c.id))):
        raise ValueError("issue_identity_mismatch")
    metadata = json.loads(_read(source_dir / "metadata.json",
        "70902e748e88d8e1388ee71f8b7c87e743fd583d90e047843f5de9b5d569825c"))
    manifest = json.loads(_read(source_dir / "source-manifest.json",
        "78ae5e3a5784dc7dc336151923ddd1e180b3ae02952595efcededda67c46b371"))
    summary = json.loads(_read(source_dir / "capture-summary.json",
        "3ba4de1a01ae0b5274215f91e621d89e3197b8f517156b51d11ca3ff411ae739"))
    license_data = json.loads(_read(source_dir / "license-attribution.json",
        "f697c05e28ba105365361468d883685a89f10a020e96b6ba562fffc9044cd406"))
    if ((metadata["repository"], metadata["repository_id"], metadata["commit"]["sha"],
         metadata["commit"]["tree"], metadata["issue"]["context_sha256"])
            != ("go-chi/chi", 44344606, COMMIT, TREE, CONTEXT)
            or metadata["root_tree"]["sha"] != TREE or _tree_id(metadata["root_tree"]["entries"]) != TREE
            or (manifest["repository"], manifest["repository_id"], manifest["commit"], manifest["root_tree"],
                manifest["issue"], manifest["issue_context_sha256"], manifest["complete_repository_snapshot"])
            != ("go-chi/chi", 44344606, COMMIT, TREE, 1188, CONTEXT, False)
            or summary["source_manifest"] != manifest or license_data["license_spdx"] != "MIT"
            or license_data["commit"] != COMMIT or license_data["repository"] != "go-chi/chi"):
        raise ValueError("source_manifest_or_tree_mismatch")
    entries = {e["path"]: e for e in metadata["root_tree"]["entries"]}
    if len(manifest["files"]) != len(EXPECTED) or {f["path"] for f in manifest["files"]} != set(EXPECTED):
        raise ValueError("source_inventory_mismatch")
    sources, inventory_files = {}, []
    for item in sorted(manifest["files"], key=lambda f: f["path"]):
        path = item["path"]
        size, blob, digest = EXPECTED[path]
        tree_entry = entries.get(path, {})
        if ((item["bytes"], item["git_blob_sha1"], item["sha256"], item["mode"], item["type"])
                != (size, blob, digest, "100644", "blob")
                or (tree_entry.get("sha"), tree_entry.get("size"), tree_entry.get("mode"), tree_entry.get("type"))
                != (blob, size, "100644", "blob")):
            raise ValueError("source_entry_mismatch")
        raw = _read(source_dir / "source" / path, digest)
        sources[path] = raw
        inventory_files.append({"path": path, "git_blob_sha1": blob, "sha256": digest, "size_bytes": size,
                                "line_count": len(raw.split(b"\n")) - int(raw.endswith(b"\n"))})
    inventory = PartialInventory.model_validate({"version": "human-review-inventory-v1",
        "repository": "go-chi/chi", "commit": COMMIT, "root_tree": TREE,
        "source_complete": False, "files": inventory_files})
    verify_sources(inventory, sources)
    return issue, inventory, sources


def _write(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _safe_display(value: str) -> str:
    # Avoid terminal control/bidirectional formatting without altering retained originals.
    import unicodedata
    return "".join(f"\\u{ord(c):04x}" if (unicodedata.category(c) == "Cf" or
                   (ord(c) < 32 and c not in "\n\t") or ord(c) == 127) else c for c in value)


def write_packet(parent: Path, issue: IssueContext, inventory: PartialInventory,
                 sources: dict[str, bytes]) -> Path:
    """Write two blank, unranked copies only after source identities validate."""
    _dir(parent)
    verify_sources(inventory, sources)
    if issue.comments != sorted(issue.comments, key=lambda c: (c.created_at, c.id)):
        raise ValueError("comment_order_mismatch")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory = parent / f"chi-1188-human-review-{stamp}-{secrets.token_hex(4)}"
    directory.mkdir(mode=0o700)
    marker = directory / "INCOMPLETE"
    _write(marker, b"Packet construction is incomplete. Do not use.\n")
    digest = inventory_digest(inventory)
    blank = {"version": "human-relevance-review-v1", "rubric_version": "source-relevance-v1",
        "repository": inventory.repository, "issue_id": issue.issue_id, "issue_number": issue.number,
        "issue_context_sha256": context_digest(issue), "commit": inventory.commit, "root_tree": inventory.root_tree,
        "source_inventory_sha256": digest, "dataset_split": "pilot_development", "label_scope": "partial_source_subset",
        "source_complete": False, "source_completeness_warning": WARNING, "reviewer_kind": None,
        "reviewer_id": None, "reviewed_at_utc": None, "independence": None, "adjudication_status": None,
        "outcome": None, "issue_evidence_sufficiency": None, "source_sufficiency": None,
        "missing_source": [], "uncertainty": None, "abstention_reason": None, "labels": []}
    issue_text = (f"ISSUE: https://github.com/{inventory.repository}/issues/{issue.number}\n"
                  f"ISSUE ID: {issue.issue_id}\nPINNED COMMIT: {inventory.commit}\n"
                  f"ROOT TREE: {inventory.root_tree}\nISSUE-CONTEXT SHA-256: {context_digest(issue)}\n"
                  "The original comment is withheld from initial blind review.\n\nTITLE:\n"
                  + _safe_display(issue.title) + "\n\nBODY:\n" + _safe_display(issue.body or "") + "\n")
    for reviewer in ("reviewer-a", "reviewer-b"):
        view = directory / reviewer
        view.mkdir(mode=0o700)
        source_dir = view / "source"
        source_dir.mkdir(mode=0o700)
        _write(view / "README.txt", INSTRUCTIONS.encode())
        _write(view / "response-format.txt", RESPONSE_FORMAT.encode())
        _write(view / "issue.txt", issue_text.encode())
        _write(view / "inventory.json", canonical(inventory.model_dump(mode="json")) + b"\n")
        _write(view / "annotation-template.json", canonical(blank) + b"\n")
        for item in inventory.files:
            # This packet supports the approved root-level files only.
            if "/" in item.path:
                raise ValueError("nested_packet_path_not_supported")
            lines = sources[item.path].decode("utf-8").split("\n")
            if lines and lines[-1] == "":
                lines.pop()
            numbered = "".join(f"{n:05d} | {_safe_display(line)}\n" for n, line in enumerate(lines, 1))
            _write(source_dir / (item.path + ".txt"), numbered.encode())
    marker.unlink()
    return directory


def main() -> None:
    if len(sys.argv) != 1:
        raise SystemExit("This command accepts no path or network arguments.")
    old_umask = os.umask(0o077)
    try:
        issue, inventory, sources = load_chi()
        directory = write_packet(ROOT, issue, inventory, sources)
    finally:
        os.umask(old_umask)
    print(f"private_packet={directory}")
    print(f"source_inventory_sha256={inventory_digest(inventory)}")
    print("reviewer_copies=2 completed_human_judgments=0 source_complete=false")


if __name__ == "__main__":
    main()
