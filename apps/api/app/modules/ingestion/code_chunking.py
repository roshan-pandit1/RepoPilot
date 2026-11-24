"""Deterministic, line-addressable Python chunks; never execute repository content."""
import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class SourceChunk:
    start_line: int
    end_line: int
    symbol: str | None
    text: str
    symbol_kind: str | None = None


def chunk_multilingual(source: str, analysis, max_lines: int = 120) -> list[SourceChunk]:
    """Cover every original line once, with outer non-overlapping syntax ranges.

    An unavailable, invalid or bounded-out parser produces line windows without
    symbols. Nested definitions remain in their containing source chunk.
    """
    if max_lines < 1:
        raise ValueError("max_lines must be positive")
    lines = source.splitlines(keepends=True)
    candidates = sorted(analysis.symbols if analysis.fallback_reason is None else (),
                        key=lambda s: (s.start_line, -s.end_line, s.name))
    blocks = []
    last = 0
    for symbol in candidates:
        if (symbol.start_line > last and symbol.end_line >= symbol.start_line
                and symbol.end_line <= len(lines)):
            blocks.append(symbol)
            last = symbol.end_line
    result: list[SourceChunk] = []

    def add(first, end, symbol=None):
        while first <= end:
            final = min(end, first + max_lines - 1)
            matches = symbol is not None and first == symbol.start_line
            result.append(SourceChunk(first, final, symbol.name if matches else None,
                                      "".join(lines[first - 1:final]),
                                      symbol.kind if matches else None))
            first = final + 1

    cursor = 1
    for block in blocks:
        if cursor < block.start_line:
            add(cursor, block.start_line - 1)
        add(block.start_line, block.end_line, block)
        cursor = block.end_line + 1
    if cursor <= len(lines):
        add(cursor, len(lines))
    return result


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
