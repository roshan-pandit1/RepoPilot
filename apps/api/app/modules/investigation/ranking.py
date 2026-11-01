"""Bounded deterministic ordering of already authorized retrieval candidates."""
from __future__ import annotations

import re

from app.modules.investigation.query_builder import _UNTRUSTED_INSTRUCTION

_RANK_STOP = frozenset('and are code for from github has issue not repository should source the that use with wrong test def'.split())


def _rank_tokens(value: str) -> set[str]:
    """Split identifier terms and apply a small deterministic suffix rule."""
    clean = '\n'.join(line for line in value.splitlines() if not _UNTRUSTED_INSTRUCTION.search(line))
    clean = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', clean).lower().replace('_', ' ')
    words = {word for word in re.findall(r'[a-z][a-z0-9]{2,}', clean) if word not in _RANK_STOP}

    def stem(word: str) -> str:
        for suffix in ('ing', 'ed', 's'):
            if len(word) > len(suffix) + 3 and word.endswith(suffix):
                return word[:-len(suffix)]
        return word

    return {stem(word) for word in words}


def protected_symbol_order(title: str, body: str, baseline: list[tuple[str, str | None]],
                           candidates: list[tuple[str, str | None]], limit: int) -> list[str]:
    """Keep four existing leaders, then order by rank and issue/symbol token overlap."""
    if not 1 <= limit <= 30:
        raise ValueError('invalid_evidence_budget')
    title_tokens, body_tokens = _rank_tokens(title[:1024]), _rank_tokens(body[:4000])
    head = baseline[:min(4, limit)]
    seen = {chunk_id for chunk_id, _ in head}

    def priority(item):
        rank, (_, symbol) = item
        symbol_tokens = _rank_tokens((symbol or '')[:256])
        # Twice the rank, less four per title match and one per body match.
        return (2 * rank - 4 * len(symbol_tokens & title_tokens) - len(symbol_tokens & body_tokens), rank)

    tail = [item for _, item in sorted(enumerate(candidates, 1), key=priority) if item[0] not in seen]
    result, ids = [], set()
    for chunk_id, _ in [*head, *tail]:
        if chunk_id not in ids:
            result.append(chunk_id)
            ids.add(chunk_id)
        if len(result) == limit:
            break
    return result
