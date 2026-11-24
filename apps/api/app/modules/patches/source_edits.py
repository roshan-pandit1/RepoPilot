"""Convert evidence-visible whole-line replacements into a validated in-memory diff."""
from dataclasses import dataclass
from difflib import unified_diff

from app.modules.patches.context import PatchContext
from app.modules.patches.generation import CandidateRequest, build_candidate_request
from app.modules.patches.validation import Limits, PatchError, SourceFile, safe_path, validate_patch


@dataclass(frozen=True)
class SourceEdit:
    """An exact line-sequence replacement; no path is ever opened on disk."""
    path: str
    before: str
    after: str
    start_line: int | None = None


def _lines(value: str) -> list[str]:
    if (not isinstance(value, str) or not value
            or any(ord(char) < 32 and char not in "\n\t" for char in value)):
        raise PatchError("invalid_source_edit")
    try:
        if len(value.encode("utf-8")) > 16384:
            raise PatchError("invalid_source_edit")
    except UnicodeEncodeError:
        raise PatchError("invalid_source_edit") from None
    parts = value.split("\n")
    if parts[-1] == "":
        parts.pop()
    if not parts:
        raise PatchError("invalid_source_edit")
    return parts


def edits_to_diff(request: CandidateRequest, edits: tuple[SourceEdit, ...],
                  evidence_ids: tuple[str, ...], snippets: list[dict],
                  limits: Limits = Limits()) -> str:
    """Revalidate context, bind edits to cited snippets, and invoke the existing validator.

    ``before`` and ``after`` are LF-separated whole lines; the optional final LF is
    a separator, not a request to alter file newline policy. Paths are inert labels.
    """
    if not isinstance(request, CandidateRequest) or not isinstance(edits, tuple) or not 1 <= len(edits) <= 30:
        raise PatchError("invalid_source_edit")
    if (not isinstance(evidence_ids, tuple) or not evidence_ids or len(evidence_ids) > 30
            or not all(isinstance(e, str) for e in evidence_ids) or len(set(evidence_ids)) != len(evidence_ids)):
        raise PatchError("invalid_evidence_reference")
    data = request.untrusted_data
    try:
        sources = tuple(SourceFile(f.path, f.source.encode("utf-8"), f.sha256, f.file_id,
                                   f.evidence_ids, f.pinned_identity) for f in data.files)
        context = PatchContext(data.investigation_id, data.snapshot_id, data.commit_sha, data.issue_id,
                               data.title, data.body, sources, data.evidence, data.repository_id,
                               data.repository_full_name, data.tenant_id)
        if build_candidate_request(context) != request:
            raise PatchError("invalid_provider_request")
    except (AttributeError, TypeError, UnicodeEncodeError):
        raise PatchError("invalid_provider_request") from None
    refs = {e.id: e for e in data.evidence}
    if not set(evidence_ids) <= refs.keys():
        raise PatchError("invalid_evidence_reference")
    files = {f.path: f for f in data.files}
    visible: dict[str, list[tuple[int, int, str]]] = {}
    if not isinstance(snippets, list):
        raise PatchError("invalid_provider_request")
    for snippet in snippets:
        if not isinstance(snippet, dict):
            raise PatchError("invalid_provider_request")
        path, eid = snippet.get("path"), snippet.get("evidence_id")
        start, end = snippet.get("start_line"), snippet.get("end_line")
        file, evidence = files.get(path), refs.get(eid)
        if (file is None or evidence is None or evidence.path != path or type(start) is not int
                or type(end) is not int or not 1 <= start <= evidence.start_line <= evidence.end_line <= end):
            raise PatchError("invalid_provider_request")
        original = file.source.split("\n")[:-1]
        if end > len(original) or snippet.get("text") != "".join(line + "\n" for line in original[start - 1:end]):
            raise PatchError("invalid_provider_request")
        visible.setdefault(path, []).append((start - 1, end, eid))
    ranges: dict[str, list[tuple[int, int, list[str]]]] = {}
    for edit in edits:
        if not isinstance(edit, SourceEdit) or not safe_path(edit.path) or edit.path not in files:
            raise PatchError("unauthorized_or_duplicate_path")
        if edit.start_line is not None and (type(edit.start_line) is not int or edit.start_line < 1):
            raise PatchError("invalid_source_edit_range")
        before, after = _lines(edit.before), _lines(edit.after)
        if before == after:
            raise PatchError("unchanged_source_edit")
        original = files[edit.path].source.split("\n")[:-1]
        if edit.start_line is None:
            matches = []
            for index in range(len(original) - len(before) + 1):
                if original[index] == before[0] and original[index:index + len(before)] == before:
                    matches.append(index)
                    if len(matches) > 1:
                        break
            if len(matches) != 1:
                raise PatchError("ambiguous_or_missing_source_edit")
            start = matches[0]
        else:
            start = edit.start_line - 1
            if original[start:start + len(before)] != before:
                raise PatchError("invalid_source_edit_range")
        end = start + len(before)
        if not any(lo <= start and end <= hi and eid in evidence_ids
                   for lo, hi, eid in visible.get(edit.path, [])):
            raise PatchError("uncited_source_edit")
        ranges.setdefault(edit.path, []).append((start, end, after))
    if len(ranges) > limits.files:
        raise PatchError("too_many_files")
    result = []
    for path in sorted(ranges):
        original = files[path].source.split("\n")[:-1]
        updated, position = [], 0
        for start, end, after in sorted(ranges[path], key=lambda item: item[0]):
            if start < position:
                raise PatchError("overlapping_source_edits")
            updated.extend(original[position:start])
            updated.extend(after)
            position = end
        updated.extend(original[position:])
        result.extend(unified_diff([line + "\n" for line in original], [line + "\n" for line in updated],
                                   fromfile="a/" + path, tofile="b/" + path, lineterm="\n"))
    diff = "".join(result)
    validate_patch(diff, sources, limits)
    return diff
