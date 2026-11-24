"""Offline paired retrieval evaluation over independently supplied judgments.

No model, repository, labels, sessions or captures are created by this module.
Unjudged results are reported explicitly rather than treated as negative labels.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import statistics
from pathlib import Path

from pydantic import ValidationError

from app.evaluation.git_source import GitSource
from app.evaluation.issue_context_schema import IssueContext, context_digest
from app.evaluation.retrieval import citation_valid, percentile
from app.modules.ingestion.code_selection import eligible_source_path, incompatible_line_endings
from app.modules.investigation.query_builder import build_queries_for_version

MODES = ("keyword", "semantic", "hybrid")


def _context_config(dataset: dict) -> dict:
    config = dataset.get("retrieval_config")
    keys = {"version", "query_version", "query_limit", "query_body_limit", "per_query_limit",
            "evidence_limit", "semantic_candidate_pool", "top_k", "fusion_k", "chunking_policy",
            "semantic_representation", "semantic_query_policy", "missing_vectors", "missing_results"}
    if (not isinstance(config, dict) or set(config) != keys or config["version"] != "capture-config-v1"
            or config["query_version"] != "terms-v2" or config["missing_vectors"] != "reject"
            or config["missing_results"] != "empty"):
        raise ValueError("invalid_retrieval_config")
    bounds = {"query_limit": (1, 3), "query_body_limit": (1, 4000), "per_query_limit": (1, 20),
              "evidence_limit": (1, 30), "semantic_candidate_pool": (1, 50), "top_k": (10, 10),
              "fusion_k": (1, 1000)}
    if (any(isinstance(config[key], bool) or not isinstance(config[key], int)
            or not low <= config[key] <= high for key, (low, high) in bounds.items())
            or config["evidence_limit"] < config["top_k"]
            or config["semantic_candidate_pool"] < config["top_k"]
            or any(not isinstance(config[key], str) or not 1 <= len(config[key]) <= 100
                   for key in ("chunking_policy", "semantic_representation", "semantic_query_policy"))):
        raise ValueError("invalid_retrieval_config")
    return config


def _issue_context(query: dict) -> IssueContext:
    try:
        return IssueContext.model_validate(query.get("issue_context"))
    except (ValidationError, ValueError, TypeError):
        raise ValueError("invalid_issue_context") from None


def _expected_query_provenance(issue: IssueContext, config: dict) -> list[dict]:
    queries = build_queries_for_version(config["query_version"], issue.title,
        (issue.body or "")[:config["query_body_limit"]], issue.labels, config["query_limit"])
    return [{"id": item.id, "text_sha256": hashlib.sha256(item.text.encode()).hexdigest()} for item in queries]


def validate_dataset(dataset: dict, roots: dict[str, Path]) -> dict:
    """Verify every labeled source range against explicit, pinned local Git objects."""
    if (not isinstance(dataset, dict) or dataset.get("version") not in {"heldout-v1", "heldout-v2"}
            or dataset.get("split") != "held_out"):
        raise ValueError("invalid_dataset_split")
    if dataset["version"] == "heldout-v2":
        _context_config(dataset)
        annotation = dataset.get("annotation")
        if (not isinstance(annotation, dict)
                or any(not isinstance(annotation.get(key), str) or not 1 <= len(annotation[key]) <= 2000
                       for key in ("instructions", "adjudication_protocol"))
                or not isinstance(annotation.get("exclusion_criteria"), list)
                or not 1 <= len(annotation["exclusion_criteria"]) <= 30
                or any(not isinstance(item, str) or not 1 <= len(item) <= 250
                       for item in annotation["exclusion_criteria"])):
            raise ValueError("invalid_annotation_protocol")
    queries = dataset.get("queries")
    if not isinstance(queries, list) or not queries:
        raise ValueError("invalid_queries")
    seen, sources = set(), {}
    for query in queries:
        if not isinstance(query, dict) or any(not isinstance(query.get(k), str) or not query[k].strip()
                for k in ("id", "repository", "commit", "query", "language", "category", "label_provenance")):
            raise ValueError("invalid_query")
        repo, commit = query["repository"], query["commit"]
        if query["id"] in seen or repo not in roots or not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("invalid_query_identity")
        seen.add(query["id"])
        key = (repo, commit)
        if key not in sources:
            source = GitSource(roots[repo], commit, repo)
            sources[key] = (source, {item["path"]: item for item in source.entries})
        source, entries = sources[key]
        labels = query.get("relevance")
        if not isinstance(labels, list):
            raise ValueError("invalid_labels")
        if dataset["version"] == "heldout-v2":
            _issue_context(query)
            status = query.get("adjudication_status")
            if (status not in {"adjudicated", "insufficient-evidence"}
                    or any(len(query[key]) > limit for key, limit in (("id", 80), ("repository", 250),
                           ("query", 20000), ("language", 80), ("category", 80)))
                    or len(query["label_provenance"]) > 1000
                    or (status == "insufficient-evidence" and labels)
                    or (status == "adjudicated" and not any(
                        isinstance(label, dict) and isinstance(label.get("grade"), int)
                        and not isinstance(label["grade"], bool) and label["grade"] > 0 for label in labels))):
                raise ValueError("invalid_adjudication")
        label_keys = set()
        for label in labels:
            if not isinstance(label, dict):
                raise ValueError("invalid_label")
            path, start, end, grade = (label.get(k) for k in ("path", "start_line", "end_line", "grade"))
            if (not isinstance(path, str) or not eligible_source_path(path) or path not in entries
                    or any(isinstance(n, bool) or not isinstance(n, int) for n in (start, end, grade))
                    or start < 1 or end < start or not 0 <= grade <= 3):
                raise ValueError("invalid_label")
            entry = entries[path]
            raw = source.blob("", repo, entry["sha"], entry["size"])
            try:
                source_text = raw.decode("utf-8")
                if incompatible_line_endings(source_text):
                    raise ValueError("invalid_label_source")
                lines = source_text.splitlines()
            except UnicodeError:
                raise ValueError("invalid_label_source") from None
            identity = (path, start, end)
            if end > len(lines) or identity in label_keys or b"\x00" in raw:
                raise ValueError("invalid_label_range")
            label_keys.add(identity)
    return sources


def _git_citation_valid(item: dict, repository: str, commit: str, source, entries: dict,
                        line_cache: dict) -> bool:
    """Check both the URL and its claimed range against the pinned local Git blob."""
    if not citation_valid(item, repository, commit):
        return False
    path = item["path"]
    if not eligible_source_path(path) or path not in entries:
        return False
    if path not in line_cache:
        entry = entries[path]
        try:
            raw = source.blob("", repository, entry["sha"], entry["size"])
            source_text = raw.decode("utf-8")
            if b"\x00" in raw or incompatible_line_endings(source_text):
                raise ValueError("invalid_source")
            line_cache[path] = source_text.splitlines(keepends=True)
        except (UnicodeError, ValueError):
            line_cache[path] = None
    lines = line_cache[path]
    if lines is None or item["end_line"] > len(lines):
        return False
    # Captures may intentionally omit source text. When present it must be exact.
    snippet = item.get("snippet")
    return snippet is None or (isinstance(snippet, str)
                               and snippet == "".join(lines[item["start_line"] - 1:item["end_line"]]))


def _matches(item: dict, label: dict) -> bool:
    return (item.get("path") == label["path"] and isinstance(item.get("start_line"), int)
            and not isinstance(item["start_line"], bool) and isinstance(item.get("end_line"), int)
            and not isinstance(item["end_line"], bool)
            and item["start_line"] <= label["start_line"] <= label["end_line"] <= item["end_line"])


def score_query(labels: list[dict], items: list[dict]) -> dict:
    """Measure labeled recall and precision over judged results, reporting gaps."""
    relevant = {i for i, label in enumerate(labels) if label["grade"] > 0}
    matched: set[int] = set()
    seen_items: set[tuple] = set()
    grades, judged, ranks, matched_counts = [], [], [], []
    for rank, item in enumerate(items[:10], 1):
        hits = [i for i, label in enumerate(labels) if _matches(item, label)]
        identity = (item.get("path"), item.get("start_line"), item.get("end_line"))
        if identity in seen_items:
            grades.append(0)
            judged.append(bool(hits))
            matched_counts.append(0)
            continue
        seen_items.add(identity)
        positive = [i for i in hits if i in relevant and i not in matched]
        if positive:
            matched.update(positive)
            grades.append(max(labels[i]["grade"] for i in positive))
            matched_counts.append(len(positive))
            ranks.append(rank)
            judged.append(True)
        else:
            grades.append(0)
            judged.append(bool(hits))
            matched_counts.append(0)
    recall = {str(k): (sum(matched_counts[:k]) / len(relevant) if relevant else None)
              for k in (1, 5, 10)}
    precision = {str(k): (sum(grade > 0 for grade in grades[:k]) / sum(judged[:k])
                          if sum(judged[:k]) else None) for k in (1, 5, 10)}
    precision_bounds = {str(k): {"lower": sum(grade > 0 for grade in grades[:k]) / k,
                                 "upper": (sum(grade > 0 for grade in grades[:k])
                                           + sum(not value for value in judged[:k])) / k}
                        for k in (1, 5, 10)}
    ideal_grades = sorted((labels[i]["grade"] for i in relevant), reverse=True)[:10]
    dcg = sum((2**grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(grades, 1))
    ideal = sum((2**grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(ideal_grades, 1))
    return {"recall": recall, "judged_precision": precision, "precision_at_k_bounds": precision_bounds,
            "mrr": 1 / ranks[0] if ranks else (0 if relevant else None),
            "ndcg_at_10": dcg / ideal if ideal else None, "judged": sum(judged),
            "unjudged": len(judged) - sum(judged), "returned": len(judged)}


def ann_recall(exact: list[str], approximate: list[str], k: int) -> float | None:
    if not 1 <= k <= 50 or len(set(exact)) != len(exact) or len(set(approximate)) != len(approximate):
        raise ValueError("invalid_neighbor_ranking")
    reference = set(exact[:k])
    return len(reference.intersection(approximate[:k])) / len(reference) if reference else None


def evaluate(dataset: dict, captures: dict[tuple[str, str], tuple[dict, float]], *, roots: dict[str, Path]) -> dict:
    """Validate pinned Git labels, then score supplied paired captures."""
    sources = validate_dataset(dataset, roots)
    output = {"version": dataset["version"], "split": dataset["split"], "modes": {},
              "context_validation": ("issue-context-v1" if dataset["version"] == "heldout-v2"
                                     else "legacy-query-only-unverified")}
    config = _context_config(dataset) if dataset["version"] == "heldout-v2" else None
    vector_spaces: set[tuple] = set()
    line_caches: dict[tuple[str, str], dict] = {}
    queries = dataset["queries"]
    for mode in MODES:
        rows = []
        for query in queries:
            response, elapsed = captures[(mode, query["id"])]
            if (response.get("commit_sha") != query["commit"] or not isinstance(response.get("snapshot_id"), str)
                    or not response["snapshot_id"] or response.get("mode") not in MODES
                    or (response["mode"] != mode and not response.get("fallback_reason"))
                    or (mode in {"keyword", "hybrid"} and response.get("lexical_strategy") != "terms-v2")
                    or not isinstance(elapsed, (float, int)) or isinstance(elapsed, bool)
                    or not math.isfinite(elapsed) or elapsed < 0):
                raise ValueError("invalid_capture")
            if config is not None:
                issue = _issue_context(query)
                if (response.get("issue_context_version") != issue.version
                        or response.get("context_sha256") != context_digest(issue)
                        or response.get("query_version") != config["query_version"]
                        or response.get("queries") != _expected_query_provenance(issue, config)
                        or response.get("semantic_query_sha256") != hashlib.sha256(query["query"].encode()).hexdigest()
                        or response.get("retrieval_config") != config
                        or not isinstance(response.get("universe_digest"), str)
                        or not re.fullmatch(r"[0-9a-f]{64}", response["universe_digest"])
                        or response.get("fallback_reason") is not None
                        or response.get("missing_embeddings") is not False):
                    raise ValueError("issue_context_capture_mismatch")
            if mode in {"semantic", "hybrid"} and not response.get("fallback_reason"):
                identity = response.get("semantic_identity")
                if (not isinstance(identity, dict) or identity.get("provider") not in {"fake", "local-onnx"}
                        or any(not isinstance(identity.get(key), str) or not identity[key]
                               for key in ("model", "revision", "representation_contract", "normalization"))
                        or isinstance(identity.get("dimensions"), bool)
                        or not isinstance(identity.get("dimensions"), int) or identity["dimensions"] < 1
                        or not re.fullmatch(r"[0-9a-f]{64}", identity["representation_contract"])):
                    raise ValueError("invalid_semantic_identity")
                vector_spaces.add(tuple(identity[key] for key in
                    ("provider", "model", "revision", "representation_contract", "normalization", "dimensions")))
            items = response["items"][:10]
            source_key = (query["repository"], query["commit"])
            source, entries = sources[source_key]
            line_cache = line_caches.setdefault(source_key, {})
            valid = [_git_citation_valid(item, *source_key, source, entries, line_cache) for item in items]
            scores = score_query(query["relevance"], [item if ok else {} for item, ok in zip(items, valid, strict=True)])
            rows.append({"id": query["id"], "repository": query["repository"], "language": query["language"],
                         "snapshot_id": response["snapshot_id"], **scores, "latency_ms": elapsed,
                         "invalid_citations": sum(not ok for ok in valid),
                         "fallback": bool(response.get("fallback_reason")),
                         "missing_embeddings": bool(response.get("missing_embeddings")),
                         "effective_mode": response.get("mode")})
        def mean(values):
            present = [value for value in values if value is not None]
            return statistics.mean(present) if present else None
        eligible = [row for row in rows if not row["fallback"] and row["effective_mode"] == mode]
        output["modes"][mode] = {"queries": rows,
            "eligible_queries": len(eligible),
            "recall": {str(k): mean([row["recall"][str(k)] for row in eligible]) for k in (1, 5, 10)},
            "judged_precision": {str(k): mean([row["judged_precision"][str(k)] for row in eligible]) for k in (1, 5, 10)},
            "precision_at_k_bounds": {str(k): {edge: mean([row["precision_at_k_bounds"][str(k)][edge] for row in eligible])
                                             for edge in ("lower", "upper")} for k in (1, 5, 10)},
            "mrr": mean([row["mrr"] for row in eligible]), "ndcg_at_10": mean([row["ndcg_at_10"] for row in eligible]),
            "fallback_count": sum(row["fallback"] for row in rows),
            "missing_embeddings": sum(row["missing_embeddings"] for row in rows),
            "invalid_citations": sum(row["invalid_citations"] for row in rows),
            "unjudged_results": sum(row["unjudged"] for row in rows),
            "latency_p50_ms": percentile([row["latency_ms"] for row in rows], .5),
            "latency_p95_ms": percentile([row["latency_ms"] for row in rows], .95),
            "per_language_recall_at_10": {name: mean([r["recall"]["10"] for r in eligible if r["language"] == name])
                                          for name in sorted({r["language"] for r in rows})},
            "per_repository_recall_at_10": {name: mean([r["recall"]["10"] for r in eligible if r["repository"] == name])
                                            for name in sorted({r["repository"] for r in rows})}}
    universe_by_snapshot = {}
    for query in queries:
        snapshots = {captures[(mode, query["id"])][0]["snapshot_id"] for mode in MODES}
        if len(snapshots) != 1:
            raise ValueError("snapshot_mismatch")
        if config is not None:
            digests = {captures[(mode, query["id"])][0]["universe_digest"] for mode in MODES}
            if len(digests) != 1:
                raise ValueError("candidate_universe_mismatch")
            key = (query["repository"], query["commit"], next(iter(snapshots)))
            previous = universe_by_snapshot.setdefault(key, next(iter(digests)))
            if previous != next(iter(digests)):
                raise ValueError("candidate_universe_mismatch")
    if len(vector_spaces) > 1:
        raise ValueError("embedding_space_mismatch")
    output["semantic_quality_status"] = ("MECHANICAL_TEST_ONLY" if vector_spaces and next(iter(vector_spaces))[0] == "fake"
        else "CAPTURE_PROVENANCE_UNVERIFIED" if vector_spaces else "NO_SEMANTIC_RESULTS")
    baseline = {row["id"]: row for row in output["modes"]["keyword"]["queries"]
                if not row["fallback"] and row["effective_mode"] == "keyword"}
    for mode in ("semantic", "hybrid"):
        pairs = [(baseline[row["id"]]["recall"]["10"], row["recall"]["10"])
                 for row in output["modes"][mode]["queries"] if row["id"] in baseline
                 and not row["fallback"] and row["effective_mode"] == mode
                 and baseline[row["id"]]["recall"]["10"] is not None and row["recall"]["10"] is not None]
        output["modes"][mode]["paired_vs_keyword_recall10"] = {
            "queries": len(pairs), "bootstrap_95": paired_interval([a for a, _ in pairs], [b for _, b in pairs])}
    output["limitations"] = "Unjudged results are unknown; judged precision is not full precision. Labels may be incomplete."
    return output


def paired_interval(before: list[float], after: list[float], *, seed: int = 0, samples: int = 2000):
    """Seeded percentile bootstrap over paired query differences; not valid for tiny samples."""
    if len(before) != len(after) or len(before) < 5 or not 100 <= samples <= 10000:
        return None
    differences = [b - a for a, b in zip(before, after, strict=True)]
    if any(not math.isfinite(value) for value in differences):
        raise ValueError("invalid_scores")
    rng = random.Random(seed)
    means = sorted(statistics.mean(rng.choice(differences) for _ in differences) for _ in range(samples))
    return {"mean_difference": statistics.mean(differences), "low": means[int(samples * .025)],
            "high": means[min(samples - 1, int(samples * .975))], "samples": samples, "seed": seed}


def main(argv: list[str] | None = None) -> None:
    """Score existing JSON captures offline; never fetch or create an evaluation run."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--captures", required=True, type=Path)
    parser.add_argument("--repository", action="append", required=True, metavar="OWNER/REPO=PATH")
    parser.add_argument("--output", required=True, type=Path, help="New JSON report; existing files are not overwritten")
    args = parser.parse_args(argv)
    roots = {}
    for binding in args.repository:
        name, separator, path = binding.partition("=")
        if not separator or not name or not path or name in roots or not Path(path).is_dir():
            raise ValueError("invalid_repository_binding")
        roots[name] = Path(path)
    for path in (args.dataset, args.captures):
        if path.stat().st_size > 8_000_000:
            raise ValueError("evaluation_input_too_large")
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    records = json.loads(args.captures.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("invalid_captures")
    captures = {}
    for record in records:
        if (not isinstance(record, dict) or record.get("mode") not in MODES
                or not isinstance(record.get("query_id"), str) or not isinstance(record.get("response"), dict)):
            raise ValueError("invalid_capture")
        key = (record["mode"], record["query_id"])
        if key in captures:
            raise ValueError("duplicate_capture")
        captures[key] = (record["response"], record.get("latency_ms"))
    result = evaluate(dataset, captures, roots=roots)
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=True, indent=2, sort_keys=True)
        stream.write("\n")


if __name__ == "__main__":
    main()
