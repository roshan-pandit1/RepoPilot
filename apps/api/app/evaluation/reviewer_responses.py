"""Reconcile blinded review submissions without claiming reviewer independence."""
import argparse
from collections import defaultdict
from hashlib import sha256
import json


def reconcile(manifest_bytes, bundles, adjudications=None):
    if len(manifest_bytes) > 1_000_000:
        raise ValueError("manifest too large")
    manifest = json.loads(manifest_bytes)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("cases"), list):
        raise ValueError("invalid manifest")
    ids = [case.get("id") for case in manifest["cases"] if isinstance(case, dict)]
    if len(ids) != len(manifest["cases"]) or len(set(ids)) != len(ids):
        raise ValueError("invalid case identities")
    digest = sha256(manifest_bytes).hexdigest()
    reviews = defaultdict(dict)
    if not isinstance(bundles, list) or len(bundles) > 100:
        raise ValueError("invalid review bundles")
    for bundle in bundles:
        if (not isinstance(bundle, dict) or set(bundle) != {"version", "manifest_sha256", "reviewer_reference", "responses"}
                or bundle["version"] != "reviewer-responses-v1" or bundle["manifest_sha256"] != digest
                or not isinstance(bundle["reviewer_reference"], str)
                or not 1 <= len(bundle["reviewer_reference"].strip()) <= 80
                or not isinstance(bundle["responses"], list) or len(bundle["responses"]) > len(ids)):
            raise ValueError("invalid review bundle")
        reviewer = bundle["reviewer_reference"].strip()
        for response in bundle["responses"]:
            keys = {"case_id", "decision", "severity", "confidence", "actionability", "start_line", "end_line", "minutes", "reason", "false_positive_reason"}
            if (not isinstance(response, dict) or set(response) not in (keys, keys | {"file", "category"}) or response["case_id"] not in ids
                    or ("file" in response and (not isinstance(response["file"], str) or len(response["file"]) > 512))
                    or ("category" in response and response["category"] not in {"unsure", "BUG", "SECURITY", "PERFORMANCE", "RELIABILITY", "MAINTAINABILITY", "TEST_COVERAGE"})
                    or response["decision"] not in {"pending", "present", "absent", "uncertain"}
                    or response["severity"] not in {"unsure", "critical", "high", "medium", "low", "informational"}
                    or response["confidence"] not in {"unsure", "low", "medium", "high"}
                    or response["actionability"] not in {"unsure", "yes", "no"}
                    or any(not isinstance(response[k], str) or len(response[k]) > 2000 for k in ("reason", "false_positive_reason"))
                    or any(response[k] is not None and (type(response[k]) is not int or not 0 <= response[k] <= 1000000) for k in ("start_line", "end_line", "minutes"))
                    or reviewer in reviews[response["case_id"]]):
                raise ValueError("invalid or duplicate response")
            reviews[response["case_id"]][reviewer] = response["decision"]
    decisions = {}
    adjudications = [] if adjudications is None else adjudications
    if not isinstance(adjudications, list) or len(adjudications) > len(ids):
        raise ValueError("invalid adjudications")
    for item in adjudications:
        if (not isinstance(item, dict) or set(item) not in ({"case_id", "decision", "adjudicator_reference", "reason"},
                                                           {"case_id", "decision", "adjudicator_reference", "reason", "labels"})
                or item["case_id"] not in ids or item["case_id"] in decisions
                or item["decision"] not in {"present", "absent", "uncertain"}
                or not isinstance(item["adjudicator_reference"], str) or not 1 <= len(item["adjudicator_reference"].strip()) <= 80
                or not isinstance(item["reason"], str) or not 1 <= len(item["reason"]) <= 2000
                or item["adjudicator_reference"].strip() in reviews[item["case_id"]]):
            raise ValueError("invalid adjudication")
        decisions[item["case_id"]] = item["decision"]
    states = {}
    for case_id in ids:
        submitted = {x for x in reviews[case_id].values() if x in {"present", "absent"}}
        if case_id in decisions:
            states[case_id] = "adjudicated" if decisions[case_id] != "uncertain" else "pending"
        elif len(submitted) > 1:
            states[case_id] = "disagreement"
        elif submitted:
            states[case_id] = "awaiting_adjudication"
        else:
            states[case_id] = "pending"
    return {"manifest_sha256": digest, "cases": states,
            "counts": {state: list(states.values()).count(state) for state in ("pending", "disagreement", "awaiting_adjudication", "adjudicated")},
            "reviewer_independence": "not independently verified",
            "accuracy_metrics": None}


def score_adjudicated(manifest_bytes, bundles, adjudications, predictions):
    """Score explicit adjudications only; identity/independence remain unverified."""
    from app.evaluation.review_quality import _location, evaluate

    summary = reconcile(manifest_bytes, bundles, adjudications)
    manifest = json.loads(manifest_bytes)
    if (not isinstance(predictions, dict) or set(predictions) != {"version", "manifest_sha256", "analyzer", "cases"}
            or predictions["version"] != "review-predictions-v1"
            or predictions["manifest_sha256"] != summary["manifest_sha256"]
            or not isinstance(predictions["analyzer"], str) or not 1 <= len(predictions["analyzer"]) <= 128
            or not isinstance(predictions["cases"], list)):
        raise ValueError("invalid predictions")
    by_id = {case["id"]: case for case in manifest["cases"]}
    predicted = {}
    for case in predictions["cases"]:
        if (not isinstance(case, dict) or set(case) != {"case_id", "supported", "findings"}
                or case["case_id"] not in by_id or case["case_id"] in predicted
                or type(case["supported"]) is not bool or not isinstance(case["findings"], list)
                or len(case["findings"]) > 1000):
            raise ValueError("invalid prediction case")
        predicted[case["case_id"]] = case
    output = []
    for decision in adjudications:
        case_id = decision["case_id"]
        if summary["cases"][case_id] != "adjudicated":
            continue
        reviewers = {bundle["reviewer_reference"].strip() for bundle in bundles
                     if any(item["case_id"] == case_id and item["decision"] in {"present", "absent"}
                            for item in bundle["responses"])}
        if len(reviewers) < 2:
            raise ValueError("two reviewer submissions required for scoring")
        labels = decision.get("labels")
        if (not isinstance(labels, list) or len(labels) > 1000
                or (decision["decision"] == "present" and not labels)
                or (decision["decision"] == "absent" and labels)):
            raise ValueError("adjudicated locations required")
        case = by_id[case_id]
        path = case.get("path", case.get("source_file"))
        ranges = case.get("line_ranges", [case.get("line_range")])
        for label in labels:
            _location(label)
            if (label["path"] != path or not any(isinstance(span, list) and len(span) == 2
                    and span[0] <= label["start"] <= label["end"] <= span[1] for span in ranges)):
                raise ValueError("adjudicated location outside review scope")
        prediction = predicted.get(case_id, {"supported": False, "findings": []})
        output.append({"id": case_id, "repository": case.get("repository", "synthetic/alpha-review-candidates-v1"),
            "commit": case.get("head_sha"), "source_sha256": case["source_sha256"],
            "language": case["language"], "scope": case["review_scope"],
            "label_provenance": "adjudicated; reviewer independence not independently verified",
            "supported": prediction["supported"], "labels": labels, "findings": prediction["findings"]})
    if not output:
        raise ValueError("no adjudicated cases available for scoring")
    return evaluate({"version": "review-quality-v1", "split": "regression",
                     "analyzer": predictions["analyzer"], "cases": output})


def freeze_ground_truth(manifest_bytes, bundles, adjudications):
    """Canonicalize validated adjudications; this does not verify human independence."""
    digest = sha256(manifest_bytes).hexdigest()
    score_adjudicated(manifest_bytes, bundles, adjudications,
        {"version": "review-predictions-v1", "manifest_sha256": digest,
         "analyzer": "unscored-freeze-validation", "cases": []})
    selected = sorted((item for item in adjudications if item["decision"] in {"present", "absent"}),
                      key=lambda item: item["case_id"])
    payload = {"version": "review-ground-truth-v1", "manifest_sha256": digest,
               "reviewer_independence": "not independently verified", "adjudications": selected}
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def main():
    parser = argparse.ArgumentParser(description="Reconcile reviewer response files; no code execution or automatic accuracy claims.")
    parser.add_argument("manifest")
    parser.add_argument("responses", nargs="*")
    parser.add_argument("--adjudications")
    parser.add_argument("--predictions")
    parser.add_argument("--ground-truth", help="Previously frozen ground-truth file required for scoring")
    parser.add_argument("--freeze", help="Create a new immutable-by-convention ground-truth file; never overwrite")
    args = parser.parse_args()
    def read(path):
        with open(path, "rb") as handle:
            raw = handle.read(1_000_001)
        if len(raw) > 1_000_000:
            raise ValueError("input too large")
        return raw
    manifest = read(args.manifest)
    bundles = [json.loads(read(path)) for path in args.responses]
    adjudications = json.loads(read(args.adjudications)) if args.adjudications else None
    result = reconcile(manifest, bundles, adjudications)
    if args.freeze and args.predictions:
        raise ValueError("freeze ground truth before loading predictions")
    if args.predictions:
        if adjudications is None or not args.ground_truth:
            raise ValueError("predictions require previously frozen ground truth")
        expected = freeze_ground_truth(manifest, bundles, adjudications)
        if read(args.ground_truth) != expected:
            raise ValueError("frozen ground truth mismatch")
        result["score"] = score_adjudicated(manifest, bundles, adjudications, json.loads(read(args.predictions)))
    if args.freeze:
        if adjudications is None:
            raise ValueError("freezing requires adjudications")
        frozen = freeze_ground_truth(manifest, bundles, adjudications)
        with open(args.freeze, "xb") as handle:
            handle.write(frozen)
        result["ground_truth_sha256"] = sha256(frozen).hexdigest()
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
