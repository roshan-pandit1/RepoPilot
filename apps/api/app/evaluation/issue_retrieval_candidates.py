"""Compare baseline and experimental issue-query strategies."""
from __future__ import annotations

from app.modules.investigation.query_builder import (RetrievalQuery, _STOP, _TOKEN, _VAGUE,
    build_queries, build_queries_v2)
from app.modules.investigation.ranking import protected_symbol_order

STRATEGIES = ('baseline', 'body', 'body-filtered', 'body-first')
def protected_symbol_rerank(title: str, body: str, baseline: list[dict], candidates: list[dict],
                            limit: int = 20) -> list[dict]:
    """Apply the production ordering to recorded metadata without source text."""
    def pairs(rows):
        return [(item['chunk_id'], item.get('symbol')) for item in rows]
    order = protected_symbol_order(title, body, pairs(baseline), pairs(candidates), limit)
    lookup = {item['chunk_id']: item for item in candidates}
    lookup.update({item['chunk_id']: item for item in baseline[:min(4, limit)]})
    return [{**lookup[chunk_id], 'rank': rank} for rank, chunk_id in enumerate(order, 1)]


def candidate_queries(strategy: str, title: str, body: str, labels: list[str], limit: int = 3) -> list[RetrievalQuery]:
    """Try bounded body expansion using the existing untrusted-text filtering rules."""
    if strategy not in STRATEGIES or not 1 <= limit <= 3:
        raise ValueError('invalid_candidate_strategy')
    baseline = build_queries(title, body, labels, limit)
    if strategy == 'baseline' or not baseline:
        return baseline
    if strategy == 'body':
        return build_queries_v2(title, body, labels, limit)
    original = baseline
    if strategy in ('body-filtered', 'body-first'):
        # Product names already classified as stop words should not consume identifier slots.
        original = [q for q in baseline if not (q.id.startswith('identifier_') and q.text.casefold() in _STOP)]
    title_terms = {word.casefold() for word in _TOKEN.findall(title[:1024])
                   if word.casefold() not in _STOP | _VAGUE}
    if len(title_terms) < 2:
        return original[:limit]
    seen = {q.text.casefold() for q in original}
    extra = []
    for query in build_queries(body[:1024], '', [], 3):
        if query.text.casefold() in seen or query.text.casefold() in _STOP:
            continue
        seen.add(query.text.casefold())
        name = 'body_terms' if query.id == 'title_terms' else f'body_{query.id}'
        extra.append(RetrievalQuery(name, query.text))
    if strategy == 'body-first':
        identifiers = [q for q in original if q.id.startswith('identifier_')]
        titles = [q for q in original if not q.id.startswith('identifier_')]
        return (identifiers + extra + titles)[:limit]
    return (original + extra)[:limit]
