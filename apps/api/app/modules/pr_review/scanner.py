"""Small deterministic review rules over verified source, never executing it.

PY-SHELL-001 recognizes a direct function parameter interpolated into a subprocess
shell command. This is a review lead, not a claim of reachability or exploitability.
"""
import ast

from app.modules.patches.validation import safe_path

RULE_VERSION = "pr-rules-v1"
_ALLOWED = {"run", "call", "check_call", "check_output", "Popen"}


def _bound_names(node):
    """Names rebound anywhere in a scope; ignore imports which we validate separately."""
    bound = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)):
            bound.add(child.id)
        elif isinstance(child, ast.arg):
            bound.add(child.arg)
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(child.name)
        elif isinstance(child, ast.ExceptHandler) and child.name:
            bound.add(child.name)
        elif isinstance(child, (ast.Import, ast.ImportFrom)):
            for alias in child.names:
                bound.add(alias.asname or alias.name.split('.')[0])
    return bound


def scan_changed_file(path: str, source: str, added_lines: set[int]) -> list[dict]:
    """Return narrow AST-based findings only on verified added Python lines.

    Syntax failures, unsupported types and oversized files do not produce findings;
    callers must separately report analysis coverage, never call these a clean scan.
    """
    if (not isinstance(path, str) or not safe_path(path) or not path.endswith('.py')
            or not isinstance(source, str) or len(source.encode('utf-8', errors='replace')) > 100_000
            or not isinstance(added_lines, set) or any(type(n) is not int or n < 1 for n in added_lines)):
        return []
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return []
    # Allow exactly one unshadowed top-level subprocess import spelling.
    bindings = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            bindings.extend((alias.asname or alias.name.split('.')[0], None) for alias in node.names if alias.name == 'subprocess')
        elif isinstance(node, ast.ImportFrom) and node.module == 'subprocess' and node.level == 0:
            bindings.extend((alias.asname or alias.name, alias.name) for alias in node.names if alias.name in _ALLOWED)
    if not bindings:
        return []
    # Do not infer a binding if it is rebound, shadowed, or imported more than once.
    # This is deliberately conservative; dynamic monkey-patching remains unknown.
    all_nodes = tuple(ast.walk(tree))
    unsafe_names = {node.id for node in all_nodes
                    if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))}
    unsafe_names.update(node.arg for node in all_nodes if isinstance(node, ast.arg))
    unsafe_names.update(node.name for node in all_nodes
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))
    imports = [alias.asname or alias.name.split('.')[0]
               for node in all_nodes if isinstance(node, (ast.Import, ast.ImportFrom))
               for alias in node.names]
    bindings = [(name, method) for name, method in bindings
                if name not in unsafe_names and imports.count(name) == 1]
    if not bindings:
        return []
    found = []
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        params = {p.arg for p in (*func.args.posonlyargs, *func.args.args, *func.args.kwonlyargs)}
        if func.args.vararg:
            params.add(func.args.vararg.arg)
        if func.args.kwarg:
            params.add(func.args.kwarg.arg)
        modified = {n.id for node in func.body for n in ast.walk(node)
                    if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del))}
        params -= modified
        for node in ast.walk(func):
            if not isinstance(node, ast.Call) or node.lineno not in added_lines or not node.args:
                continue
            target = None
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                target = (node.func.value.id, None) if node.func.attr in _ALLOWED else None
            elif isinstance(node.func, ast.Name):
                target = next(((name, method) for name, method in bindings if name == node.func.id and method), None)
            if not target or target not in bindings:
                continue
            # A local binding shadows an imported subprocess name; refuse to reason about it.
            if target[0] in _bound_names(func):
                continue
            shell = [k.value for k in node.keywords if k.arg == 'shell']
            if len(shell) != 1 or not isinstance(shell[0], ast.Constant) or shell[0].value is not True:
                continue
            command = node.args[0]
            if not isinstance(command, ast.JoinedStr):
                continue
            interpolated = {v.value.id for v in command.values
                            if isinstance(v, ast.FormattedValue) and isinstance(v.value, ast.Name)}
            if not params.intersection(interpolated):
                continue
            found.append({"rule_id": "PY-SHELL-001", "category": "SECURITY", "severity": "MEDIUM",
                "confidence": "MEDIUM", "path": path, "start_line": node.lineno, "end_line": node.lineno,
                "explanation": "A function parameter is interpolated into a command run with shell=True. If callers can control that value, shell metacharacters may change the command.",
                "recommendation": "Where possible, pass a fixed executable and argument list with shell=False; validate any externally controlled values."})
    # Nested scopes can expose a call through more than one AST walk; retain one exact location.
    return list({(f['rule_id'], f['path'], f['start_line']): f for f in found}.values())
