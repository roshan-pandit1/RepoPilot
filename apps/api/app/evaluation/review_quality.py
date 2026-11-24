"""Score externally labeled review findings without running repository code.

Labels are declarations, not proof of independent human review. The input must not
contain source text or secrets. See commercial-beta-foundation.md for the contract.
"""

import argparse
from hashlib import sha256
import json
import math
import re

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"}


def _wilson(successes, total):
    """95% Wilson interval; statistical assumptions do not establish independence."""
    if total == 0:
        return None
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [max(0.0, center - margin), min(1.0, center + margin)]


def _location(item):
    if (
        not isinstance(item, dict)
        or set(item) != {"rule", "path", "start", "end", "severity"}
        or not isinstance(item["rule"], str)
        or not 0 < len(item["rule"]) <= 80
        or not isinstance(item["path"], str)
        or not 0 < len(item["path"]) <= 512
        or item["path"].startswith("/")
        or "\\" in item["path"]
        or any(part in {"", ".", ".."} for part in item["path"].split("/"))
        or type(item["start"]) is not int
        or type(item["end"]) is not int
        or not 1 <= item["start"] <= item["end"] <= 1_000_000
        or item["severity"] not in _SEVERITIES
    ):
        raise ValueError("invalid finding location")
    return item


def evaluate(dataset):
    """One-to-one exact rule/path and overlapping-line matching, in recorded order."""
    if (
        not isinstance(dataset, dict)
        or set(dataset) != {"version", "split", "analyzer", "cases"}
        or dataset["version"] != "review-quality-v1"
        or dataset["split"] not in {"development", "regression", "independent_holdout"}
        or not isinstance(dataset["analyzer"], str)
        or not 0 < len(dataset["analyzer"]) <= 128
        or not isinstance(dataset["cases"], list)
        or not 1 <= len(dataset["cases"]) <= 10000
    ):
        raise ValueError("invalid dataset")
    canonical = json.dumps(
        dataset, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    seen = set()
    tp = fp = fn = duplicates = severity_correct = supported = 0
    negative_cases = negative_cases_with_findings = 0
    by_rule = {}
    finding_count = 0
    for case in dataset["cases"]:
        required = {
            "id",
            "repository",
            "commit",
            "source_sha256",
            "language",
            "scope",
            "label_provenance",
            "supported",
            "labels",
            "findings",
        }
        if (
            not isinstance(case, dict)
            or set(case) != required
            or not isinstance(case["id"], str)
            or not 0 < len(case["id"]) <= 128
            or case["id"] in seen
            or not isinstance(case["repository"], str)
            or not 0 < len(case["repository"]) <= 250
            or not ((case["commit"] is None and case["repository"].startswith("synthetic/"))
                    or (isinstance(case["commit"], str) and _COMMIT.fullmatch(case["commit"])))
            or not isinstance(case["source_sha256"], str)
            or not _SHA.fullmatch(case["source_sha256"])
            or case["language"] not in {"python", "typescript", "tsx"}
            or not isinstance(case["scope"], str)
            or not 0 < len(case["scope"]) <= 512
            or not isinstance(case["label_provenance"], str)
            or not 0 < len(case["label_provenance"]) <= 250
            or type(case["supported"]) is not bool
            or not isinstance(case["labels"], list)
            or not isinstance(case["findings"], list)
            or len(case["labels"]) > 1000
            or len(case["findings"]) > 1000
        ):
            raise ValueError("invalid case")
        seen.add(case["id"])
        labels = [_location(item) for item in case["labels"]]
        findings = [_location(item) for item in case["findings"]]
        if not case["supported"]:
            if findings:
                raise ValueError("unsupported case has findings")
            continue
        supported += 1
        finding_count += len(findings)
        for rule in {entry["rule"] for entry in labels + findings}:
            by_rule.setdefault(rule, {"tp": 0, "fp": 0, "fn": 0})
        if not labels:
            negative_cases += 1
            negative_cases_with_findings += int(bool(findings))
        unmatched = set(range(len(labels)))
        fingerprints = set()
        for finding in findings:
            fingerprint = tuple(finding[key] for key in ("rule", "path", "start", "end"))
            if fingerprint in fingerprints:
                duplicates += 1
            fingerprints.add(fingerprint)
            match = next(
                (
                    i
                    for i in sorted(unmatched)
                    if labels[i]["rule"] == finding["rule"]
                    and labels[i]["path"] == finding["path"]
                    and labels[i]["start"] <= finding["end"]
                    and finding["start"] <= labels[i]["end"]
                ),
                None,
            )
            if match is None:
                fp += 1
                by_rule[finding["rule"]]["fp"] += 1
            else:
                unmatched.remove(match)
                tp += 1
                by_rule[finding["rule"]]["tp"] += 1
                severity_correct += int(labels[match]["severity"] == finding["severity"])
        fn += len(unmatched)
        for index in unmatched:
            by_rule[labels[index]["rule"]]["fn"] += 1
    for counts in by_rule.values():
        counts["precision"] = counts["tp"] / (counts["tp"] + counts["fp"]) if counts["tp"] + counts["fp"] else None
        counts["recall"] = counts["tp"] / (counts["tp"] + counts["fn"]) if counts["tp"] + counts["fn"] else None
    return {
        "dataset_sha256": sha256(canonical).hexdigest(),
        "analyzer": dataset["analyzer"],
        "split": dataset["split"],
        "case_count": len(seen),
        "supported_cases": supported,
        "unsupported_cases": len(seen) - supported,
        "negative_cases": negative_cases,
        "negative_cases_with_findings": negative_cases_with_findings,
        "false_positive_case_rate": negative_cases_with_findings / negative_cases
        if negative_cases
        else None,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "precision_wilson_95": _wilson(tp, tp + fp),
        "recall_on_supported_cases": tp / (tp + fn) if tp + fn else None,
        "recall_wilson_95": _wilson(tp, tp + fn),
        "false_positive_case_rate_wilson_95": _wilson(negative_cases_with_findings, negative_cases),
        "location_accuracy": tp / (tp + fp) if tp + fp else None,
        "severity_agreement": severity_correct / tp if tp else None,
        "duplicate_findings": duplicates,
        "finding_count": finding_count,
        "duplicate_rate": duplicates / finding_count if finding_count else None,
        "supported_case_fraction": supported / len(seen),
        "per_rule": dict(sorted(by_rule.items())),
        "independence": "not independently verified",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Score labeled PR review records; never execute source."
    )
    parser.add_argument("dataset")
    args = parser.parse_args()
    with open(args.dataset, "rb") as handle:
        raw = handle.read(5_000_001)
    if len(raw) > 5_000_000:
        raise SystemExit("dataset exceeds size limit")
    print(json.dumps(evaluate(json.loads(raw)), sort_keys=True))


if __name__ == "__main__":
    main()
