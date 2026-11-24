"""Original, deterministic source text; these strings are never executed."""

BASE = {
    "python": (
        "import os\n# café μ\nclass Box:\n    def total(self, n):\n"
        "        def inner(v):\n            return v + 1\n        return inner(n)\n"
        "def helper():\n    return 0\n",
        "def broken(\n", ("Box", "Box.total", "helper"),
    ),
    "javascript": (
        'import x from "x";\n// café μ\nclass Box {\n'
        '  total(n) { function inner(v) { return v + 1; } return inner(n); }\n'
        '}\nfunction helper() { return 0; }\n',
        "function broken( {\n", ("Box", "Box.total", "helper"),
    ),
    "jsx": (
        'import x from "x";\n// café μ\n'
        'function View() { return <div>μ</div>; }\n'
        'function helper() { return 0; }\n',
        "function broken( {\n", ("View", "helper"),
    ),
    "typescript": (
        'import x from "x";\n// café μ\nclass Box {\n'
        '  total(n: number): number { return n + 1; }\n}\n'
        'function helper(): number { return 0; }\n',
        "function broken( {\n", ("Box", "Box.total", "helper"),
    ),
    "tsx": (
        'import x from "x";\n// café μ\n'
        'function View(): JSX.Element { return <div>μ</div>; }\n'
        'function helper(): number { return 0; }\n',
        "function broken( {\n", ("View", "helper"),
    ),
    "java": (
        "import java.util.List;\n// café μ\nclass Box {\n"
        "  int total(int n) { if (n > 0) { return n + 1; } return 0; }\n"
        "}\nclass Other {}\n",
        "class Broken { void m( {\n", ("Box", "Box.total", "Other"),
    ),
    "go": (
        'package demo\nimport "fmt"\n// café μ\ntype Box struct {}\n'
        'func (b Box) total(n int) int { if n > 0 { return n + 1 }; return 0 }\n'
        'func helper() {}\n',
        "package p\nfunc broken( {\n", ("total", "helper"),
    ),
    "rust": (
        "use std::fmt;\n// café μ\nstruct Boxed { n: i32 }\n"
        "fn total(n: i32) -> i32 { if n > 0 { n + 1 } else { 0 } }\n"
        "fn helper() {}\n",
        "fn broken( {\n", ("Boxed", "total", "helper"),
    ),
    "c": (
        "#include <stdio.h>\n// café μ\nstruct Box { int n; };\n"
        "int total(int n) { if (n > 0) { return n + 1; } return 0; }\n"
        "int helper(void) { return 0; }\n",
        "int broken( {\n", ("Box", "total", "helper"),
    ),
    "cpp": (
        "#include <vector>\n// café μ\n"
        "class Box { public: int total(int n) { return n + 1; } };\n"
        "int helper() { return 0; }\n",
        "int broken( {\n", ("Box", "Box.total", "helper"),
    ),
    "csharp": (
        "using System;\n// café μ\n"
        "class Box { public int Total(int n) { return n + 1; } }\n"
        "class Other {}\n",
        "class Broken { void M( {\n", ("Box", "Box.Total", "Other"),
    ),
}

VARIANTS = {
    ".py": "python", ".js": "javascript", ".jsx": "jsx", ".mjs": "javascript",
    ".ts": "typescript", ".tsx": "tsx", ".java": "java", ".go": "go",
    ".rs": "rust", ".c": "c", ".h": "c", ".cpp": "cpp", ".cc": "cpp",
    ".hpp": "cpp", ".cs": "csharp",
}

STRESS_EXTENSIONS = (
    ".py", ".js", ".ts", ".tsx", ".java", ".go", ".rs", ".c", ".cpp", ".cs",
)


def small(extension: str) -> tuple[str, str, tuple[str, ...]]:
    source, broken, symbols = BASE[VARIANTS[extension]]
    return source.replace("\n", "\r\n"), broken, symbols


def stress(extension: str) -> tuple[str, tuple[str, ...]]:
    kind = VARIANTS[extension]
    steps = 130
    repetitions = 150
    if kind == "python":
        src = ("# café μ\ndef long_fn():\n    n = 0\n" + "    n += 1\n" * steps
               + "    return n\n" + "".join(f"def f{i}():\n    return {i}\n" for i in range(repetitions)))
        return src, ("long_fn", "f0", f"f{repetitions - 1}")
    if kind in {"javascript", "typescript", "tsx"}:
        annotation = ": number" if kind == "typescript" else ""
        if kind == "tsx":
            header = "function longFn(): JSX.Element {\n  let n = 0;\n"
            tail = "  return <div>{n}</div>;\n}\n"
            repeated = "".join(f"function f{i}(): JSX.Element {{ return <p>{i}</p>; }}\n"
                               for i in range(repetitions))
        else:
            header = f"function longFn(){annotation} {{\n  let n = 0;\n"
            tail = "  return n;\n}\n"
            repeated = "".join(f"function f{i}(){annotation} {{ return {i}; }}\n"
                               for i in range(repetitions))
        return "// café μ\n" + header + "  n += 1;\n" * steps + tail + repeated, (
            "longFn", "f0", f"f{repetitions - 1}")
    if kind == "java":
        long_part = ("class LongBox { int longFn() {\n  int n = 0;\n" + "  n += 1;\n" * steps
                     + "  return n;\n} }\n")
        repeated = "".join(f"class C{i} {{ int f() {{ return {i}; }} }}\n" for i in range(repetitions))
        return "// café μ\n" + long_part + repeated, ("LongBox", "LongBox.longFn", f"C{repetitions - 1}")
    if kind == "go":
        long_part = ("package p\n// café μ\nfunc longFn() int {\n  n := 0\n" + "  n += 1\n" * steps
                     + "  return n\n}\n")
        repeated = "".join(f"func f{i}() int {{ return {i} }}\n" for i in range(repetitions))
        return long_part + repeated, ("longFn", "f0", f"f{repetitions - 1}")
    if kind == "rust":
        long_part = ("// café μ\nfn long_fn() -> i32 {\n  let mut n = 0;\n" + "  n += 1;\n" * steps
                     + "  n\n}\n")
        repeated = "".join(f"fn f{i}() -> i32 {{ {i} }}\n" for i in range(repetitions))
        return long_part + repeated, ("long_fn", "f0", f"f{repetitions - 1}")
    if kind in {"c", "cpp"}:
        long_part = ("// café μ\nint long_fn(void) {\n  int n = 0;\n" + "  n += 1;\n" * steps
                     + "  return n;\n}\n")
        repeated = "".join(f"int f{i}(void) {{ return {i}; }}\n" for i in range(repetitions))
        return long_part + repeated, ("long_fn", "f0", f"f{repetitions - 1}")
    if kind == "csharp":
        long_part = ("class LongBox { public int LongFn() {\n  int n = 0;\n" + "  n += 1;\n" * steps
                     + "  return n;\n} }\n")
        repeated = "".join(f"class C{i} {{ public int F() {{ return {i}; }} }}\n"
                           for i in range(repetitions))
        return "// café μ\n" + long_part + repeated, ("LongBox", "LongBox.LongFn", f"C{repetitions - 1}")
    raise ValueError("unsupported stress grammar")
