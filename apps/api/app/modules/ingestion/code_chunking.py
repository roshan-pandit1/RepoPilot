"""Deterministic, line-addressable Python chunks; never execute repository content."""
import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class SourceChunk:
    start_line: int
    end_line: int
    symbol: str | None
    text: str


def chunk_python(source: str, max_lines: int = 120) -> list[SourceChunk]:
    """Partition the whole source; preserve small top-level functions and classes.

    Long blocks and invalid Python fall back to deterministic line windows. Decorators
    are included in their definition. Line numbers are one-based and inclusive.
    """
    if max_lines < 1:
        raise ValueError("max_lines must be positive")
    lines = source.splitlines(keepends=True)
    if not lines:
        return []

    blocks: list[tuple[int, int, str | None]] = []
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        tree = None
    if tree:
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                first = min([node.lineno, *(d.lineno for d in node.decorator_list)])
                blocks.append((first, node.end_lineno or node.lineno, node.name))

    result: list[SourceChunk] = []

    def add(first: int, last: int, symbol: str | None = None) -> None:
        while first <= last:
            end = min(last, first + max_lines - 1)
            result.append(SourceChunk(first, end, symbol, "".join(lines[first - 1:end])))
            first = end + 1

    cursor = 1
    for first, last, symbol in blocks:
        if cursor < first:
            add(cursor, first - 1)
        add(first, last, symbol)
        cursor = last + 1
    if cursor <= len(lines):
        add(cursor, len(lines))
    return result
