"""Synthetic coverage provenance and provider-serialization tests; no model calls."""
from dataclasses import replace
from hashlib import sha256
import json

import pytest

from app.modules.ingestion.citations import github_citation
from app.modules.patches.generation import build_candidate_request, generate_candidate
from app.modules.patches.source_coverage import describe_coverage
from app.modules.patches.validation import PatchError, PinnedFileIdentity
from test_ollama_patch_provider import chat, metadata, provider, response
from test_patch_provider_contract import EVIDENCE_ID, context


SOURCE = b"def add(a: int, b: int) -> int:\n    return a - b\n"
SOURCE_HASH = "9445c47952abb8a7fc5d4a905d55b5be05771df1d69362ec597f9a50f7ede40d"
ISSUE = ("The add function returns the difference instead of the sum. The expected behavior is addition. "
         "Propose the smallest correction.")
LONG_SOURCE = "".join(f"# line {i:02d}: π\n" for i in range(1, 13)).encode()
LONG_HASH = "0fe18352f9d253bdbe20826126774c18f9764806309f15b7caf2b0b8ed35c867"


@pytest.fixture(autouse=True)
def no_proxy_environment(monkeypatch):
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(key, raising=False)


def synthetic_context(*, content=SOURCE, digest=SOURCE_HASH, expected_size=49, start=1, end=2,
                      include_identity=True, record_complete=True):
    """The expected hash and size come from the independent fixed synthetic manifest."""
    base = context()
    path = "src/arithmetic.py"
    repository, repo_id, tenant_id = "synthetic-lab/arithmetic", 1002, 1003
    identity = PinnedFileIdentity(base.snapshot_id, base.commit_sha, repo_id, tenant_id,
                                  base.files[0].file_id, path, digest, expected_size, record_complete)
    file = replace(base.files[0], path=path, content=content, sha256=digest,
                   pinned_identity=identity if include_identity else None)
    evidence = replace(base.evidence[0], path=path, start_line=start, end_line=end,
                       citation=github_citation(repository, base.commit_sha, path, start, end))
    return replace(base, repository_full_name=repository, repository_id=repo_id, tenant_id=tenant_id, issue_id=1001,
                   title="Synthetic addition issue", body=ISSUE, files=(file,), evidence=(evidence,))


def capture_request(ctx):
    seen = []

    def handler(request):
        if request.url.path != "/api/chat":
            return response(payload=metadata(request.url.path))
        seen.append(request.content)
        value = {"status": "insufficient_evidence", "diff": "", "rationale": "Synthetic abstention.",
                 "uncertainty": "unknown", "evidence_ids": [], "source_files": []}
        return response(payload=chat(value))

    with pytest.raises(PatchError, match="local_model_insufficient_evidence"):
        generate_candidate(provider(handler), ctx)
    assert len(seen) == 1
    return json.loads(seen[0]), seen[0]


def test_complete_file_requires_verified_inventory_identity_and_exact_bytes():
    ctx = synthetic_context()
    payload, raw = capture_request(ctx)
    user = json.loads(payload["messages"][1]["content"])
    snippet = user["snippets"][0]
    coverage = snippet["coverage"]
    assert user["source_coverage_version"] == "source-coverage-v1"
    assert user["issue"]["body"] == ISSUE and snippet["text"].encode() == SOURCE
    assert snippet["path"] == ctx.files[0].path and snippet["evidence_id"] == EVIDENCE_ID
    assert user["files"][0]["sha256"] == SOURCE_HASH
    assert user["evidence"][0]["citation"] == ctx.evidence[0].citation
    assert coverage == {
        "version": "source-coverage-v1", "classification": "COMPLETE_FILE",
        "verification_status": "PINNED_FILE_IDENTITY_VERIFIED", "provided_byte_count": 49,
        "provided_start_line": 1, "provided_end_line": 2, "provided_start_byte": 0,
        "provided_end_byte_exclusive": 49, "full_file_byte_count": 49, "full_file_line_count": 2,
        "full_file_sha256": SOURCE_HASH,
        "notice": "This is the complete content of the supplied file. No additional source lines from this file are omitted.",
    }
    assert "snippets[].text" in payload["messages"][0]["content"]
    assert "A candidate may be proposed" in payload["messages"][0]["content"]
    assert "If the evidence is insufficient" in payload["messages"][0]["content"]
    assert "--- a/path, +++ b/path and @@ hunks" in payload["messages"][0]["content"]
    assert len(raw) < 524288 and payload["format"]["type"] == "object"


def test_verified_middle_excerpt_has_utf8_byte_offsets_and_no_full_file_claim():
    assert len(LONG_SOURCE) == 168 and sha256(LONG_SOURCE).hexdigest() == LONG_HASH
    ctx = synthetic_context(content=LONG_SOURCE, digest=LONG_HASH, expected_size=168, start=6, end=6)
    payload, _ = capture_request(ctx)
    snippet = json.loads(payload["messages"][1]["content"])["snippets"][0]
    coverage = snippet["coverage"]
    assert coverage["classification"] == "BOUNDED_EXCERPT"
    assert coverage["notice"] == "This is an excerpt. Other lines from the file may be omitted."
    assert (coverage["provided_start_line"], coverage["provided_end_line"]) == (3, 9)
    assert (coverage["provided_start_byte"], coverage["provided_end_byte_exclusive"]) == (28, 126)
    assert coverage["provided_byte_count"] == 98 and snippet["text"].encode() == LONG_SOURCE[28:126]
    assert coverage["full_file_byte_count"] == 168 and coverage["full_file_line_count"] == 12
    assert coverage["full_file_sha256"] == LONG_HASH


@pytest.mark.parametrize("case", ["missing_identity", "incomplete_file_record", "final_visible_line"])
def test_unverified_or_incomplete_inventory_never_claims_full_coverage(case):
    if case == "incomplete_file_record":
        ctx = synthetic_context(record_complete=False)
    elif case == "final_visible_line":
        ctx = synthetic_context(content=LONG_SOURCE, digest=LONG_HASH, expected_size=168,
                                start=10, end=12, include_identity=False)
    else:
        ctx = synthetic_context(include_identity=False)
    payload, _ = capture_request(ctx)
    snippet = json.loads(payload["messages"][1]["content"])["snippets"][0]
    coverage = snippet["coverage"]
    assert coverage["classification"] == "UNKNOWN_COVERAGE"
    assert coverage["verification_status"] == "FULL_FILE_IDENTITY_UNAVAILABLE"
    assert "may or may not be omitted" in coverage["notice"]
    for name in ("provided_start_byte", "provided_end_byte_exclusive", "full_file_byte_count",
                 "full_file_line_count", "full_file_sha256"):
        assert coverage[name] is None
    if case == "final_visible_line":
        assert snippet["end_line"] == 12


@pytest.mark.parametrize("field,value", [
    ("sha256", "0" * 64), ("byte_length", 48), ("snapshot_id", "00000000-0000-4000-8000-000000000000"),
    ("commit_sha", "c" * 40), ("repository_id", 1), ("tenant_id", 1),
    ("file_id", "00000000-0000-4000-8000-000000000000"), ("path", "src/other.py"),
    ("file_record_complete", "true"),
])
def test_mismatched_pinned_identity_fails_before_provider_transport(field, value):
    ctx = synthetic_context()
    file = ctx.files[0]
    forged = replace(file.pinned_identity, **{field: value})
    ctx = replace(ctx, files=(replace(file, pinned_identity=forged),))
    called = []
    with pytest.raises(PatchError, match="invalid_provider_request"):
        generate_candidate(provider(lambda request: called.append(request)), ctx)
    assert called == []


def test_incomplete_visible_bytes_do_not_match_complete_file_record():
    ctx = synthetic_context()
    file = ctx.files[0]
    truncated = SOURCE.splitlines(keepends=True)[0]
    # Even if the visible bytes are self-hashed, the independently pinned record
    # still has the original size and digest and must reject the invented file.
    file = replace(file, content=truncated, sha256=sha256(truncated).hexdigest())
    evidence = replace(ctx.evidence[0], end_line=1,
                       citation=github_citation(ctx.repository_full_name, ctx.commit_sha, file.path, 1, 1))
    ctx = replace(ctx, files=(file,), evidence=(evidence,))
    called = []
    with pytest.raises(PatchError, match="invalid_provider_request"):
        generate_candidate(provider(lambda request: called.append(request)), ctx)
    assert called == []


def test_provider_rechecks_pinned_identity_after_request_construction():
    ctx = synthetic_context()
    request = build_candidate_request(ctx)
    file = request.untrusted_data.files[0]
    tampered = replace(file, pinned_identity=replace(file.pinned_identity, byte_length=48))
    request = replace(request, untrusted_data=replace(request.untrusted_data, files=(tampered,)))
    seen = []

    def handler(raw):
        seen.append(raw.url.path)
        return response(payload=metadata(raw.url.path))

    with pytest.raises(PatchError, match="invalid_provider_request"):
        provider(handler).generate(request, timeout_seconds=3)
    assert "/api/chat" not in seen


def _coverage_arguments():
    ctx = synthetic_context()
    file = ctx.files[0]
    return dict(identity=file.pinned_identity, snapshot_id=ctx.snapshot_id, commit_sha=ctx.commit_sha,
                repository_id=ctx.repository_id, tenant_id=ctx.tenant_id, file_id=file.file_id,
                path=file.path, digest=file.sha256, source=file.content, start_line=1, end_line=2,
                start_byte=0, end_byte=49, snippet=file.content)


@pytest.mark.parametrize("change", [
    {"start_line": 0}, {"end_line": 3}, {"start_line": 2, "end_line": 1},
    {"start_byte": 1}, {"end_byte": 48}, {"start_byte": True}, {"snippet": b"not the source"},
    {"digest": "0" * 64},
])
def test_invalid_line_byte_and_content_ranges_are_rejected(change):
    args = _coverage_arguments()
    args.update(change)
    with pytest.raises(PatchError, match="invalid_provider_request"):
        describe_coverage(**args)


def test_verified_complete_synthetic_candidate_still_uses_existing_diff_validation():
    ctx = synthetic_context()
    diff = ("--- a/src/arithmetic.py\n+++ b/src/arithmetic.py\n@@ -1,2 +1,2 @@\n"
            " def add(a: int, b: int) -> int:\n-    return a - b\n+    return a + b\n")
    def handler(request):
        if request.url.path != "/api/chat":
            return response(payload=metadata(request.url.path))
        value = {"status": "candidate", "diff": diff, "rationale": "Synthetic candidate.",
                 "uncertainty": "Not executed.", "evidence_ids": [EVIDENCE_ID],
                 "source_files": [{"path": ctx.files[0].path, "file_id": ctx.files[0].file_id,
                                   "sha256": ctx.files[0].sha256}]}
        return response(payload=chat(value))
    result = generate_candidate(provider(handler), ctx)
    assert result.changed_files[0].content == SOURCE.replace(b"a - b", b"a + b")
    assert result.evidence_ids == (EVIDENCE_ID,)
