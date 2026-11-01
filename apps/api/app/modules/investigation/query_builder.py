"""Small deterministic, bounded heuristics; issue text is data, never instructions."""
from dataclasses import dataclass
import re

_TOKEN = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z][A-Za-z0-9_]{2,63}(?![A-Za-z0-9_])")
_UNTRUSTED_INSTRUCTION = re.compile(r"(?i)\b(ignore|reveal|secret|password|credential|private.key|system prompt|developer instruction|bearer|access.token)\b")
_STOP = frozenset("a an and are as at be by can code does error for from github how i in is it its issue of on or repo repository request source that the this to was when where with would".split())
_VAGUE = frozenset({'application', 'failed', 'fails', 'failure', 'broken', 'problem', 'working'})


@dataclass(frozen=True)
class RetrievalQuery:
    id: str
    text: str


def build_queries(title: str, body: str, labels: list[str], limit: int = 3) -> list[RetrievalQuery]:
    """Select a few identifiers, followed by bounded title terms, without executing content."""
    if not 1 <= limit <= 3:
        raise ValueError("invalid_query_limit")
    # Exclude instruction/credential-bearing lines; filter is defensive, not an injection boundary.
    title_lines = [line for line in title[:1024].splitlines() if not _UNTRUSTED_INSTRUCTION.search(line)]
    body_lines = [line for line in body[:4000].splitlines() if not _UNTRUSTED_INSTRUCTION.search(line)]
    label_lines = [label[:100] for label in labels[:20] if not _UNTRUSTED_INSTRUCTION.search(label[:100])]
    result: list[RetrievalQuery] = []
    seen = set()
    for token in _TOKEN.findall("\n".join(title_lines + body_lines + label_lines)):
        if not ("_" in token or (re.search(r"[a-z][A-Z]", token) and re.search(r"[A-Z]", token))):
            continue
        folded = token.lower()
        if folded in seen or folded.startswith(("github_pat", "ghp_", "gho_", "ghs_", "ghu_", "ghr_")):
            continue
        seen.add(folded)
        result.append(RetrievalQuery(f"identifier_{len(result) + 1}", token))
        if len(result) >= min(2, limit):
            break
    words = []
    for token in _TOKEN.findall(" ".join(title_lines + label_lines)):
        lower = token.lower()
        if lower in _STOP or lower in {x.lower() for x in words} or "_" in token or len(token) > 30:
            continue
        words.append(token)
        if len(words) == 8:
            break
    text = " ".join(words)[:120].strip()
    if text and len(result) < limit and text.lower() not in seen:
        result.append(RetrievalQuery("title_terms", text))
    return result[:limit]


def build_queries_v2(title: str, body: str, labels: list[str], limit: int = 3) -> list[RetrievalQuery]:
    """Keep v1 queries and append distinct bounded body terms for informative titles."""
    baseline = build_queries(title, body, labels, limit)
    if not baseline:
        return baseline
    usable_lines = '\n'.join(line for line in title[:1024].splitlines() if not _UNTRUSTED_INSTRUCTION.search(line))
    title_terms = {word.casefold() for word in _TOKEN.findall(usable_lines)
                   if word.casefold() not in _STOP | _VAGUE}
    if len(title_terms) < 2:
        return baseline
    seen = {q.text.casefold() for q in baseline}
    extra = []
    for query in build_queries(body[:1024], '', [], 3):
        if query.text.casefold() in seen or query.text.casefold() in _STOP:
            continue
        seen.add(query.text.casefold())
        name = 'body_terms' if query.id == 'title_terms' else f'body_{query.id}'
        extra.append(RetrievalQuery(name, query.text))
    return (baseline + extra)[:limit]


def build_queries_for_version(version: str, title: str, body: str, labels: list[str],
                              limit: int = 3) -> list[RetrievalQuery]:
    if version == 'terms-v1':
        return build_queries(title, body, labels, limit)
    if version == 'terms-v2':
        return build_queries_v2(title, body, labels, limit)
    raise ValueError('query_version_unavailable')
