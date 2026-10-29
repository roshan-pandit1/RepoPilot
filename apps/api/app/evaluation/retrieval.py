"""Evaluate the existing authorized search API; never persist source or credentials."""
from __future__ import annotations

import argparse
import getpass
import json
import math
import statistics
import time
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx

MODES = ("keyword", "semantic", "hybrid")


def match_label(item: dict, label: dict) -> bool:
    """Require the complete labeled range and symbol, not arbitrary line overlap."""
    return (item.get("path") == label["path"] and item.get("symbol") == label["symbol"]
            and isinstance(item.get("start_line"), int) and isinstance(item.get("end_line"), int)
            and item["start_line"] <= label["start_line"] <= label["end_line"] <= item["end_line"])


def citation_valid(item: dict, repository: str, commit: str) -> bool:
    try:
        start, end, path = item["start_line"], item["end_line"], item["path"]
        if not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int) or isinstance(end, bool):
            return False
        if start < 1 or end < start or item["commit_sha"] != commit or not isinstance(path, str):
            return False
        expected = ("https://github.com/" + "/".join(quote(p, safe="") for p in repository.split("/"))
                    + "/blob/" + commit + "/" + quote(path, safe="/") + f"#L{start}-L{end}")
        return item.get("url") == expected
    except (KeyError, TypeError):
        return False


def measure_query(labels: list[dict], items: list[dict]) -> dict:
    found: set[int] = set()
    gains, ranks = [], []
    for rank, item in enumerate(items[:10], 1):
        matching = next((i for i, label in enumerate(labels) if i not in found and match_label(item, label)), None)
        gains.append(0 if matching is None else 1)
        if matching is not None:
            found.add(matching)
            ranks.append(rank)
    recalls = {str(k): sum(gains[:k]) / len(labels) for k in (1, 3, 5, 10)}
    dcg = sum(gain / math.log2(rank + 1) for rank, gain in enumerate(gains, 1))
    ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(10, len(labels)) + 1))
    return {"recall": recalls, "reciprocal_rank": 1 / ranks[0] if ranks else 0,
            "ndcg_at_10": dcg / ideal, "relevant_ranks": ranks}


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


def evaluate(dataset: dict, responses: dict, metadata: dict) -> dict:
    result = {"dataset_commit": dataset["commit_sha"], "repository": dataset["repository"],
              "configuration": metadata, "modes": {}}
    for mode in MODES:
        rows = []
        for question in dataset["queries"]:
            response, elapsed = responses[(mode, question["id"])]
            if response.get("commit_sha") != dataset["commit_sha"]:
                raise ValueError("Snapshot commit does not match the benchmark")
            items = response["items"][:10]
            scores = measure_query(question["relevance"], items)
            top = items[0] if items and citation_valid(items[0], dataset["repository"], dataset["commit_sha"]) else None
            rows.append({"id": question["id"], "question": question["question"], **scores,
                "returned": len(items), "invalid_citations": sum(not citation_valid(item, dataset["repository"], dataset["commit_sha"]) for item in items),
                "fallback": bool(response.get("fallback_reason")), "effective_mode": response.get("mode"),
                "latency_ms": round(elapsed, 3), "top_result": {"path": top["path"], "symbol": top.get("symbol")} if top else None})
        result["modes"][mode] = {"queries": rows,
            "recall": {str(k): statistics.mean(r["recall"][str(k)] for r in rows) for k in (1, 3, 5, 10)},
            "mrr": statistics.mean(r["reciprocal_rank"] for r in rows),
            "ndcg_at_10": statistics.mean(r["ndcg_at_10"] for r in rows),
            "no_relevant": sum(not r["relevant_ranks"] for r in rows),
            "fallback_count": sum(r["fallback"] for r in rows),
            "total_results": sum(r["returned"] for r in rows),
            "invalid_citations": sum(r["invalid_citations"] for r in rows),
            "latency_p50_ms": percentile([r["latency_ms"] for r in rows], .5),
            "latency_p95_ms": percentile([r["latency_ms"] for r in rows], .95)}
    return result


def markdown(report: dict) -> str:
    config = report["configuration"]
    out = ["# Retrieval evaluation", "", f"Repository: {report['repository']}", f"Commit: {report['dataset_commit']}",
           f"Provider: {config.get('provider')}; model: {config.get('model')}; dimensions: {config.get('dimensions')}; limit: {config.get('limit')}",
           "", "Fake-vector semantic and hybrid results: **MECHANICAL TEST ONLY**. Real semantic quality has not been measured.",
           "Binary relevance uses incomplete, manually reviewed labels; ranks are not comprehensive judgments.", ""]
    for mode, result in report["modes"].items():
        recall = " / ".join(format(result["recall"][str(k)], ".3f") for k in (1, 3, 5, 10))
        out += [f"## {mode}", "", f"Recall @1/@3/@5/@10: {recall}",
                f"MRR: {result['mrr']:.3f}; nDCG@10: {result['ndcg_at_10']:.3f}; no relevant: {result['no_relevant']}",
                f"Fallbacks: {result['fallback_count']}; returned results: {result['total_results']}; invalid citations: {result['invalid_citations']} (no citation evidence if no results); latency p50/p95: {result['latency_p50_ms']:.1f}/{result['latency_p95_ms']:.1f} ms", "",
                "| Query | Relevant ranks | Effective mode |", "| --- | --- | --- |"]
        out += [f"| {r['id']} | {', '.join(map(str, r['relevant_ranks'])) or 'none'} | {r['effective_mode']} |" for r in result["queries"]]
        misses = [row for row in result["queries"] if not row["relevant_ranks"]]
        if misses:
            out += ["", "Representative misses (unlabeled results are not necessarily irrelevant):"]
            out += [f"- {row['id']}: top result {row['top_result']['path'] if row['top_result'] else 'none or invalid citation'}" for row in misses[:3]]
        out.append("")
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--repository-id", required=True, type=int)
    parser.add_argument("--output", type=Path, required=True, help="Output prefix; writes .json and .md")
    parser.add_argument("--base-url", default="http://localhost:3000")
    parser.add_argument("--capture", type=Path, help="Process a sanitized capture from the signed-in browser")
    args = parser.parse_args()
    url = urlsplit(args.base_url)
    if url.scheme != "http" or url.hostname not in {"localhost", "127.0.0.1", "::1"} or url.path not in {"", "/"} or url.query or url.fragment or url.username or url.password:
        parser.error("Only a local HTTP origin is allowed")
    if args.repository_id <= 0:
        parser.error("Repository id must be positive")
    dataset = json.loads(args.dataset.read_text())
    if args.capture:
        capture = json.loads(args.capture.read_text())
        if (capture.get("repository") != dataset["repository"] or capture.get("commit_sha") != dataset["commit_sha"]
                or capture.get("repository_id") != str(args.repository_id) or capture.get("provider") not in (None, "fake")):
            raise SystemExit("Capture does not match benchmark repository, commit, or fake-provider restriction")
        responses = {(item["mode"], item["id"]): (item["response"], item["latency_ms"])
                     for item in capture["queries"]}
        expected = {(mode, query["id"]) for mode in MODES for query in dataset["queries"]}
        if len(capture["queries"]) != len(expected) or set(responses) != expected:
            raise SystemExit("Capture is incomplete or contains duplicate queries")
        meta = {"provider": capture.get("provider"), "model": capture.get("model"),
                "dimensions": capture.get("dimensions"), "embedding_ready": capture.get("ready"),
                "limit": 10, "quality_label": "MECHANICAL TEST ONLY for fake semantic/hybrid"}
        result = evaluate(dataset, responses, meta)
        args.output.with_suffix(".json").write_text(json.dumps(result, indent=2) + "\n")
        args.output.with_suffix(".md").write_text(markdown(result) + "\n")
        print("Evaluation complete; reports contain no source snippets or credentials.")
        return
    session = getpass.getpass("Local rp_session cookie (hidden; never saved): ")
    csrf = getpass.getpass("Local rp_csrf cookie (hidden; never saved): ")
    if not session or not csrf or any(c in session + csrf for c in "\r\n; "):
        raise SystemExit("Invalid session input")
    origin = args.base_url.rstrip("/")
    headers = {"cookie": f"rp_session={session}; rp_csrf={csrf}", "x-csrf-token": csrf, "origin": origin}
    base = f"{origin}/api/code/{args.repository_id}"
    responses = {}
    with httpx.Client(headers=headers, timeout=30, follow_redirects=False, trust_env=False) as client:
        status = client.get(base + "/embedding-status")
        status.raise_for_status()
        state = status.json()
        if state.get("snapshot_commit") != dataset["commit_sha"]:
            raise SystemExit("Published snapshot does not match the benchmark commit")
        if state.get("provider") not in (None, "fake"):
            raise SystemExit("Only the free fake provider or keyword fallback is supported")
        for mode in MODES:
            for query in dataset["queries"]:
                started = time.perf_counter()
                response = client.post(base + "/search", json={"query": query["question"], "limit": 10, "mode": mode})
                elapsed = (time.perf_counter() - started) * 1000
                response.raise_for_status()
                responses[(mode, query["id"])] = (response.json(), elapsed)
    meta = {"provider": state.get("provider"), "model": state.get("model"), "dimensions": state.get("dimensions"),
            "embedding_ready": state.get("ready"), "limit": 10, "quality_label": "MECHANICAL TEST ONLY for fake semantic/hybrid"}
    result = evaluate(dataset, responses, meta)
    args.output.with_suffix(".json").write_text(json.dumps(result, indent=2) + "\n")
    args.output.with_suffix(".md").write_text(markdown(result) + "\n")
    print("Evaluation complete; reports contain no source snippets or credentials.")


if __name__ == "__main__":
    main()
