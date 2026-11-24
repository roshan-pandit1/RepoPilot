import pytest
import importlib.util

from app.modules.ingestion.language_analysis import LANGUAGES, analyze_source
from pathlib import PurePosixPath


@pytest.mark.parametrize(("path", "source", "symbol"), [
    ("x.py", "import os\nclass A:\n    def f(self):\n        pass\n", "A.f"),
    ("x.js", "import x from 'x';\nclass A { f() {} }\n", "A.f"),
    ("x.jsx", "import x from 'x';\nfunction F() { return <div/>; }\n", "F"),
    ("x.ts", "import x from 'x';\nclass A { f(): void {} }\n", "A.f"),
    ("x.tsx", "import x from 'x';\nfunction F() { return <div/>; }\n", "F"),
    ("x.java", "import a.B;\nclass A { void f() {} }\n", "A.f"),
    ("x.go", 'package x\nimport "fmt"\nfunc f() {}\n', "f"),
    ("x.rs", "use x::y;\nstruct A {}\nfn f() {}\n", "f"),
    ("x.c", "#include <stdio.h>\nint f() {return 0;}\n", "f"),
    ("x.cpp", "#include <stdio.h>\nclass A { void f() {} };\n", "A.f"),
    ("x.cs", "using System;\nclass A { void F() {} }\n", "A.F"),
])
def test_languages_extract_symbols_and_import_ranges(path, source, symbol):
    module = LANGUAGES[PurePosixPath(path).suffix].module
    if module != "ast" and importlib.util.find_spec(module) is None:
        pytest.skip(f"optional parser {module} is not installed")
    result = analyze_source(path, source)
    assert result.fallback_reason is None
    assert result.parser_version
    assert symbol in {item.name for item in result.symbols}
    assert result.import_lines
    assert all(1 <= item.start_line <= item.end_line <= len(source.splitlines())
               for item in result.symbols)


def test_unicode_crlf_and_decorated_nested_python_ranges():
    source = "import os\r\n@décor\r\ndef outer():\r\n    def inner():\r\n        pass\r\n"
    result = analyze_source("x.py", source)
    assert [(x.name, x.start_line, x.end_line) for x in result.symbols] == [
        ("outer", 2, 5), ("outer.inner", 4, 5)]
    assert [x.kind for x in result.symbols] == ["function", "function"]
    assert result.import_lines == ((1, 1),)


def test_syntax_errors_limits_and_unsupported_fail_closed():
    result = analyze_source("x.py", "def broken(")
    assert result.fallback_reason == "syntax_error" and not result.symbols
    assert analyze_source("x.py", "x = 1", max_nodes=1).fallback_reason == "node_limit"
    if importlib.util.find_spec("tree_sitter_javascript") is not None:
        assert analyze_source("x.js", "let a = 1", max_nodes=1).fallback_reason == "node_limit"
    with pytest.raises(ValueError, match="source_limit_or_binary"):
        analyze_source("x.py", "\x00")
    with pytest.raises(ValueError, match="source_limit_or_binary"):
        analyze_source("x.py", "abc", max_bytes=2)
    with pytest.raises(ValueError, match="unsupported_language"):
        analyze_source("x.bin", "abc")


def test_unavailable_grammar_does_not_fabricate_symbols(monkeypatch):
    def unavailable(_name):
        raise ImportError("missing grammar")

    monkeypatch.setattr("app.modules.ingestion.language_analysis.import_module", unavailable)
    result = analyze_source("x.js", "function f() {}")
    assert result.fallback_reason == "parser_unavailable"
    assert not result.symbols and not result.import_lines
