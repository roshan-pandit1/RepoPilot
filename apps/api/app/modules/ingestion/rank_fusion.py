"""Reciprocal rank fusion over independently ordered, stable item identifiers."""
from collections import defaultdict


def reciprocal_rank_fusion(rankings: list[list[str]], *, k: int = 60) -> list[tuple[str, float]]:
    if k < 1:
        raise ValueError("k must be positive")
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        seen = set()
        for position, item in enumerate(ranking, 1):
            if item in seen:
                continue
            seen.add(item)
            scores[item] += 1.0 / (k + position)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))
