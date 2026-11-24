"""Offline, bounded syntax inspection for supported source languages.

Tree-sitter grammars are deliberately loaded only from installed packages. This
module never downloads grammars and never executes the source being inspected.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from importlib import import_module, metadata
from pathlib import PurePosixPath
from time import monotonic

from app.modules.ingestion.code_selection import incompatible_line_endings

REGISTRY_VERSION = "languages-v1"


@dataclass(frozen=True)
class Language:
    name: str
    module: str
    entrypoint: str = "language"


# TSX is a distinct grammar; JSX is part of the JavaScript grammar.
LANGUAGES = {
    ".py": Language("python", "ast"),
    ".js": Language("javascript", "tree_sitter_javascript"),
    ".mjs": Language("javascript", "tree_sitter_javascript"),
    ".jsx": Language("jsx", "tree_sitter_javascript"),
    ".ts": Language("typescript", "tree_sitter_typescript", "language_typescript"),
    ".tsx": Language("tsx", "tree_sitter_typescript", "language_tsx"),
    ".java": Language("java", "tree_sitter_java"),
    ".go": Language("go", "tree_sitter_go"),
    ".rs": Language("rust", "tree_sitter_rust"),
    ".c": Language("c", "tree_sitter_c"),
    ".h": Language("c", "tree_sitter_c"),
    ".cc": Language("cpp", "tree_sitter_cpp"),
    ".cpp": Language("cpp", "tree_sitter_cpp"),
    ".hpp": Language("cpp", "tree_sitter_cpp"),
    ".cs": Language("csharp", "tree_sitter_c_sharp"),
}


@dataclass(frozen=True)
class Symbol:
    name: str
    kind: str
    start_line: int
    end_line: int
    parent: str | None = None


@dataclass(frozen=True)
class SyntaxAnalysis:
    language: str
    parser_version: str
    symbols: tuple[Symbol, ...]
    import_lines: tuple[tuple[int, int], ...]
    fallback_reason: str | None = None


_DEFINITIONS = {
    "function_declaration": "function", "function_definition": "function",
    "function_item": "function", "method_definition": "method",
    "method_declaration": "method", "class_declaration": "class",
    "class_definition": "class", "class_specifier": "class",
    "struct_item": "struct", "struct_specifier": "struct",
    "struct_declaration": "struct", "interface_declaration": "interface",
}
_IMPORTS = {"import_statement", "import_declaration", "import_spec", "use_declaration",
            "using_directive", "preproc_include"}


def _python(source: str, max_nodes: int) -> SyntaxAnalysis:
    import sys
    version = REGISTRY_VERSION + ":python-" + ".".join(map(str, sys.version_info[:3]))
    try:
        root = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return SyntaxAnalysis("python", version, (), (), "syntax_error")
    symbols: list[Symbol] = []
    imports: list[tuple[int, int]] = []
    stack = [(root, None, None)]
    visited = 0
    while stack:
        node, parent, parent_kind = stack.pop()
        visited += 1
        if visited > max_nodes:
            return SyntaxAnalysis("python", version, (), (), "node_limit")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            kind = "class" if isinstance(node, ast.ClassDef) else ("method" if parent_kind == "class" else "function")
            name = f"{parent}.{node.name}" if parent else node.name
            first = min([node.lineno, *(d.lineno for d in node.decorator_list)])
            symbols.append(Symbol(name, kind, first, node.end_lineno or node.lineno, parent))
            parent = name
            parent_kind = kind
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append((node.lineno, node.end_lineno or node.lineno))
        stack.extend((child, parent, parent_kind) for child in reversed(list(ast.iter_child_nodes(node))))
    return SyntaxAnalysis("python", version, tuple(symbols), tuple(imports))


def analyze_source(path: str, source: str, *, max_bytes: int = 100_000,
                   max_nodes: int = 50_000, timeout_seconds: float = 0.5) -> SyntaxAnalysis:
    """Analyze a bounded source string, returning an explicit untrusted-parser fallback.

    Callers must apply Git tree and source-selection checks independently.
    """
    language = LANGUAGES.get(PurePosixPath(path).suffix.lower())
    if language is None:
        raise ValueError("unsupported_language")
    if (max_bytes < 1 or max_nodes < 1 or not 0 < timeout_seconds <= 1
            or len(source.encode("utf-8")) > max_bytes or "\x00" in source):
        raise ValueError("source_limit_or_binary")
    if language.name == "python":
        return _python(source, max_nodes)
    # Tree-sitter uses LF-delimited rows; Python's line slicing recognizes these
    # other separators too. Fall back rather than attribute incorrect lines.
    if incompatible_line_endings(source):
        return SyntaxAnalysis(language.name, "unavailable", (), (), "unsupported_line_endings")
    try:
        from tree_sitter import Language as TreeLanguage
        from tree_sitter import Parser
        grammar = import_module(language.module)
        version = f"{REGISTRY_VERSION}:ts-{metadata.version('tree-sitter')}:{metadata.version(language.module.replace('_', '-'))}"
        parser = Parser(TreeLanguage(getattr(grammar, language.entrypoint)()))
    except (ImportError, AttributeError, ValueError, TypeError, metadata.PackageNotFoundError):
        return SyntaxAnalysis(language.name, "unavailable", (), (), "parser_unavailable")
    raw = source.encode("utf-8")
    deadline = monotonic() + timeout_seconds
    try:
        tree = parser.parse(lambda offset, _point: raw[offset:offset + 8192],
                            progress_callback=lambda *_: monotonic() >= deadline)
        if tree is None:
            return SyntaxAnalysis(language.name, version, (), (), "parse_timeout")
        root = tree.root_node
    except (ValueError, RuntimeError, MemoryError):
        return SyntaxAnalysis(language.name, version, (), (),
                              "parse_timeout" if monotonic() >= deadline else "parser_error")
    if root.has_error:
        return SyntaxAnalysis(language.name, version, (), (), "syntax_error")
    symbols: list[Symbol] = []
    imports: list[tuple[int, int]] = []
    stack = [(root, None)]
    visited = 0
    while stack:
        if monotonic() >= deadline:
            return SyntaxAnalysis(language.name, version, (), (), "parse_timeout")
        node, parent = stack.pop()
        visited += 1
        if visited > max_nodes:
            return SyntaxAnalysis(language.name, version, (), (), "node_limit")
        first, last = node.start_point.row + 1, node.end_point.row + 1
        if node.end_point.column == 0 and last > first:
            last -= 1
        if node.type in _IMPORTS:
            imports.append((first, last))
        if node.type in _DEFINITIONS:
            name_node = node.child_by_field_name("name")
            declarator = node.child_by_field_name("declarator")
            while name_node is None and declarator is not None:
                if declarator.type in {"identifier", "field_identifier"}:
                    name_node = declarator
                    break
                declarator = declarator.child_by_field_name("declarator")
            if name_node is not None and name_node.text is not None:
                short_name = name_node.text.decode("utf-8")
                name = f"{parent}.{short_name}" if parent else short_name
                kind = _DEFINITIONS[node.type]
                symbols.append(Symbol(name, kind, first, last, parent))
                parent = name
        stack.extend((child, parent) for child in reversed(node.named_children))
    return SyntaxAnalysis(language.name, version, tuple(symbols), tuple(imports))
