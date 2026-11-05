"""Bounded, non-executing analysis of already verified evidence chunks."""
from __future__ import annotations

import ast
import multiprocessing
import re
import time
from collections import Counter

from app.modules.ingestion.code_selection import eligible_python_path
from app.modules.investigation.query_builder import _STOP, _TOKEN, _UNTRUSTED_INSTRUCTION

MAX_CHUNKS = 20
MAX_CHUNK_BYTES = 8192
MAX_TOTAL_BYTES = 65536
MAX_NODES = 500
MAX_EDGES = 1000
MAX_SIGNALS = 40
TIME_BUDGET = 0.5
PROCESS_TIMEOUT = 2.0
_ID = r'[A-Za-z_][A-Za-z0-9_]{0,63}'
_FRAME = re.compile(r'File ["\']([^"\']{1,300}\.py)["\'], line ([0-9]{1,7}), in (' + _ID + r')')
_PATH = re.compile(r'(?<![\w./\\-])([A-Za-z0-9_./-]{1,240}\.py)(?![\w/])')
_QUOTED = re.compile(r'`(' + _ID + r')`')
_SNAKE_IDENTIFIER = re.compile(r'\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b')
_NAMED = re.compile(r'\b(function|class|method)\s+(' + _ID + r')\b', re.I)
_EXCEPTION = re.compile(r'\b(' + _ID + r'(?:Error|Exception|Warning))\b')
_IMPORT_ERROR = re.compile(r"(?:No module named|cannot import name)\s+['\"]([A-Za-z_][A-Za-z0-9_.]{0,127})['\"]")
_MODULE = re.compile(r'\b(?:from|import)\s+([A-Za-z_][A-Za-z0-9_.]{0,127})\b')


class AnalysisTimeout(Exception):
    """The bounded parser process did not finish within its deadline."""


class AnalysisProcessError(Exception):
    """The parser process exited or failed without a valid result."""


def _analysis_child(pipe, title, body, evidence):
    try:
        try:
            result = analyze(title, body, evidence)
        except Exception:
            # Never return or log exception details that may contain untrusted source.
            result = None
        pipe.send(result)
    except (BrokenPipeError, EOFError, OSError):
        pass
    finally:
        pipe.close()


def run_bounded(title: str, body: str, evidence: list[dict], *, timeout: float = PROCESS_TIMEOUT) -> dict:
    """Run only the application analyzer in a disposable process with a deadline."""
    if not 0 < timeout <= PROCESS_TIMEOUT:
        raise ValueError('invalid_analysis_timeout')
    context = multiprocessing.get_context('spawn')
    reader, writer = context.Pipe(duplex=False)
    process = context.Process(target=_analysis_child, args=(writer, title, body, evidence), daemon=True)
    try:
        process.start()
        writer.close()
        if not reader.poll(timeout):
            raise AnalysisTimeout()
        try:
            result = reader.recv()
        except (EOFError, OSError):
            raise AnalysisProcessError() from None
        if not isinstance(result, dict):
            raise AnalysisProcessError()
        return result
    finally:
        reader.close()
        writer.close()
        if process.pid is not None:
            if process.is_alive():
                process.terminate()
            process.join(timeout=0.25)
            if process.is_alive():
                process.kill()
                process.join(timeout=0.25)
            if not process.is_alive():
                process.close()


def issue_signals(title: str, body: str) -> list[dict]:
    """Extract explicit signals with line provenance; skip instruction-bearing lines."""
    result, seen = [], set()

    def add(kind, value, origin, line, **extra):
        key = (kind, value, origin, line, tuple(sorted(extra.items())))
        if key not in seen and len(result) < MAX_SIGNALS:
            seen.add(key)
            result.append({'kind': kind, 'value': value, 'origin': origin, 'line': line, **extra})

    for origin, text in (('title', title[:1024]), ('body', body[:4000])):
        for line_number, line in enumerate(text.splitlines()[:200], 1):
            if _UNTRUSTED_INSTRUCTION.search(line):
                continue
            frames = list(_FRAME.finditer(line))
            for match in frames:
                path, number, symbol = match.groups()
                if eligible_python_path(path) and 0 < int(number) <= 1000000:
                    add('traceback', path, origin, line_number, source_line=int(number), symbol=symbol)
            for match in _PATH.finditer(line):
                if not any(frame.start() <= match.start() < frame.end() for frame in frames) and eligible_python_path(match.group(1)):
                    add('path', match.group(1), origin, line_number)
            for match in _QUOTED.finditer(line):
                add('identifier', match.group(1), origin, line_number)
            for match in _SNAKE_IDENTIFIER.finditer(line):
                value = match.group(0)
                if len(value) <= 64 and not value.startswith(('github_pat_', 'ghp_', 'gho_', 'ghs_', 'ghu_', 'ghr_')):
                    add('identifier', value, origin, line_number)
            for match in _NAMED.finditer(line):
                add(match.group(1).lower(), match.group(2), origin, line_number)
            for match in _EXCEPTION.finditer(line):
                add('exception', match.group(1), origin, line_number)
            for match in _IMPORT_ERROR.finditer(line):
                add('import_error', match.group(1), origin, line_number)
            for match in _MODULE.finditer(line):
                add('module', match.group(1), origin, line_number)
            if origin == 'title':
                for token in _TOKEN.findall(line)[:8]:
                    if token.casefold() not in _STOP and '_' not in token:
                        add('title_term', token.casefold(), origin, line_number)
    return result


def analyze(title: str, body: str, evidence: list[dict]) -> dict:
    """Analyze bounded source snippets supplied by the authorized evidence boundary.

    Output references only supplied chunks; callers must validate ownership and fingerprints.
    """
    started = time.monotonic()
    signals = issue_signals(title, body)
    nodes, edges, parsed, exception_names = [], [], [], {}
    limits = ['evidence_budget'] if len(evidence) > MAX_CHUNKS else []
    used = 0
    for item in evidence[:MAX_CHUNKS]:
        if time.monotonic() - started > TIME_BUDGET:
            limits.append('time_budget')
            break
        if len(item['path']) > 512 or not eligible_python_path(item['path']):
            limits.append('invalid_source_path')
            continue
        source = item['source']
        size = len(source.encode('utf-8'))
        if size > MAX_CHUNK_BYTES or used + size > MAX_TOTAL_BYTES:
            limits.append('source_budget')
            continue
        used += size
        try:
            tree = ast.parse(source)
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            limits.append('unparseable_chunk')
            continue
        offset = item['start_line'] - 1
        file_node = {'id': f"{item['chunk_id']}:file", 'chunk_id': item['chunk_id'],
                     'path': item['path'], 'name': item['path'], 'kind': 'file',
                     'start_line': item['start_line'], 'end_line': item['end_line'], 'parent': None,
                     'is_async': False}
        module_node = {**file_node, 'id': f"{item['chunk_id']}:module", 'kind': 'module',
                       'name': item['path'][:-3].replace('/', '.')}
        if len(nodes) + 2 > MAX_NODES:
            limits.append('node_budget')
            break
        nodes.extend([file_node, module_node])
        if len(edges) < MAX_EDGES:
            edges.append({'type': 'DEFINES', 'source': file_node['id'], 'target': module_node['id'],
                          'chunk_id': item['chunk_id']})
        definitions = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                definitions.append((node, None))
                if isinstance(node, ast.ClassDef):
                    definitions.extend((child, node.name) for child in node.body
                                       if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)))
        ids, class_owner = {}, {}
        for node, parent in definitions:
            if not re.fullmatch(_ID, node.name) or (parent is not None and not re.fullmatch(_ID, parent)):
                limits.append('unsupported_identifier')
                continue
            if len(nodes) >= MAX_NODES:
                limits.append('node_budget')
                break
            start, end = node.lineno + offset, (node.end_lineno or node.lineno) + offset
            if not item['start_line'] <= start <= end <= item['end_line']:
                continue
            kind = 'class' if isinstance(node, ast.ClassDef) else 'method' if parent else 'function'
            node_id = f"{item['chunk_id']}:{kind}:{start}"
            entry = {'id': node_id, 'chunk_id': item['chunk_id'], 'path': item['path'], 'name': node.name,
                     'kind': kind, 'start_line': start, 'end_line': end, 'parent': parent,
                     'is_async': isinstance(node, ast.AsyncFunctionDef)}
            nodes.append(entry)
            ids[(parent, node.name, start)] = node_id
            if kind == 'class':
                class_owner[node.name] = node_id
            if len(edges) < MAX_EDGES:
                owner = class_owner.get(parent) if parent else module_node['id']
                if owner:
                    edges.append({'type': 'MEMBER_OF' if parent else 'DEFINES',
                                  'source': node_id if parent else owner,
                                  'target': owner if parent else node_id, 'chunk_id': item['chunk_id']})
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    limits.append('relative_import_unresolved')
                elif node.module:
                    imports.append(node.module)
            elif isinstance(node, ast.Call) and (isinstance(node.func, ast.Name) and node.func.id == '__import__'
                    or isinstance(node.func, ast.Attribute) and node.func.attr == 'import_module'):
                limits.append('dynamic_import_unresolved')
            if isinstance(node, ast.Raise) and node.exc:
                value = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
                if isinstance(value, ast.Name):
                    exception_names.setdefault(item['chunk_id'], set()).add(value.id)
            elif isinstance(node, ast.ExceptHandler) and isinstance(node.type, ast.Name):
                exception_names.setdefault(item['chunk_id'], set()).add(node.type.id)
        for module in sorted(set(imports))[:40]:
            if len(module) <= 128 and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]*', module) and len(edges) < MAX_EDGES:
                edges.append({'type': 'IMPORTS_UNRESOLVED', 'source': module_node['id'], 'target': module,
                              'chunk_id': item['chunk_id']})
        parsed.append((item, tree, definitions, imports, ids))

    # Lexical resolution is restricted to this chunk and is never a runtime guarantee.
    for item, tree, definitions, _imports, ids in parsed:
        names = Counter(node.name for node, parent in definitions if parent is None)
        assigned = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)}
        imported = {alias.asname or alias.name.split('.')[0] for node in ast.walk(tree)
                    if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names}
        for caller, parent in definitions:
            if isinstance(caller, ast.ClassDef):
                continue
            class Calls(ast.NodeVisitor):
                def __init__(self):
                    self.calls = []
                def visit_Call(self, node):
                    self.calls.append(node)
                    self.generic_visit(node)
                def visit_FunctionDef(self, node):
                    return None
                visit_AsyncFunctionDef = visit_FunctionDef
                visit_ClassDef = visit_FunctionDef
                visit_Lambda = visit_FunctionDef
            visitor = Calls()
            try:
                for statement in caller.body:
                    visitor.visit(statement)
            except RecursionError:
                limits.append('visitor_depth')
                continue
            for call in visitor.calls:
                if len(edges) >= MAX_EDGES:
                    limits.append('edge_budget')
                    break
                caller_id = ids.get((parent, caller.name, caller.lineno + item['start_line'] - 1))
                if not caller_id:
                    continue
                target = call.func.id if isinstance(call.func, ast.Name) and re.fullmatch(_ID, call.func.id) else None
                args = {arg.arg for arg in (*caller.args.posonlyargs, *caller.args.args, *caller.args.kwonlyargs)}
                args.update(arg.arg for arg in (caller.args.vararg, caller.args.kwarg) if arg)
                target_id = next((value for (scope, name, _), value in ids.items()
                                  if scope is None and name == target), None)
                if target and names[target] == 1 and target not in assigned | imported | args and target_id:
                    kind, destination = 'CALLS_STATIC', target_id
                elif target and names[target]:
                    kind, destination = 'CALLS_AMBIGUOUS', target
                else:
                    kind, destination = 'CALLS_UNKNOWN', target or '<dynamic>'
                edges.append({'type': kind, 'source': caller_id, 'target': destination,
                              'chunk_id': item['chunk_id']})

    # Only exact module-path matches with one source file are connected; imports are still
    # potential because Python import paths and runtime hooks are not resolved here.
    modules = {}
    for node in nodes:
        if node['kind'] == 'module':
            modules.setdefault(node['name'], {}).setdefault(node['path'], node['id'])
    for edge in list(edges):
        if edge['type'] == 'IMPORTS_UNRESOLVED':
            matches = modules.get(edge['target'], {})
            if len(matches) == 1 and len(edges) < MAX_EDGES:
                target = next(iter(matches.values()))
                if target != edge['source']:
                    edges.append({'type': 'IMPORTS_POTENTIAL', 'source': edge['source'], 'target': target,
                                  'chunk_id': edge['chunk_id']})

    imports_by_chunk = {item['chunk_id']: set(imports) for item, _tree, _defs, imports, _ids in parsed}
    findings, ranking = [], []
    for item in evidence[:MAX_CHUNKS]:
        observed = []
        for signal in signals:
            if signal['kind'] == 'traceback' and signal['value'] == item['path'] and item['start_line'] <= signal['source_line'] <= item['end_line']:
                observed.append(signal)
            elif signal['kind'] == 'path' and signal['value'] == item['path']:
                observed.append(signal)
            elif signal['kind'] in {'identifier', 'function', 'method', 'class'} and any(
                    node['chunk_id'] == item['chunk_id'] and node['name'] == signal['value'] for node in nodes):
                observed.append(signal)
            elif signal['kind'] == 'exception' and signal['value'] in exception_names.get(item['chunk_id'], set()):
                observed.append(signal)
            elif signal['kind'] in {'module', 'import_error'} and signal['value'] in imports_by_chunk.get(item['chunk_id'], set()):
                observed.append(signal)
        points = sum(4 if s['kind'] == 'traceback' else 2 for s in observed[:4])
        ranking.append({'chunk_id': item['chunk_id'], 'baseline_rank': item['rank'], 'signal_points': points,
                        'relationship_points': 0})
        if observed:
            rule = ('traceback_location' if any(s['kind'] == 'traceback' for s in observed) else
                    'exception_alignment' if any(s['kind'] == 'exception' for s in observed) else
                    'import_alignment' if any(s['kind'] in {'module', 'import_error'} for s in observed) else 'explicit_source_match')
            priority_kind = ('traceback' if rule == 'traceback_location' else 'exception' if rule == 'exception_alignment' else
                             next((s['kind'] for s in observed if s['kind'] in {'module', 'import_error'}), None) if rule == 'import_alignment' else None)
            ordered_signals = sorted(observed, key=lambda signal: signal['kind'] != priority_kind) if priority_kind else observed
            explanation = ('An explicitly reported exception is named in a raise or exception handler in this source.'
                           if rule == 'exception_alignment' else 'This source imports a module named in the issue; its runtime availability is unknown.'
                           if rule == 'import_alignment' else
                           'An explicit issue reference matches this indexed source location.')
            findings.append({'rule_id': rule,
                'chunk_id': item['chunk_id'], 'signals': ordered_signals[:4],
                'explanation': explanation,
                'next_steps': ['Inspect the cited code and reproduce the behavior in a safe test environment.'],
                'limitations': ['A matching location does not establish a cause.'], 'uncertainty': 'high'})
    anchors = {row['chunk_id'] for row in ranking if row['signal_points'] > 0}
    node_chunks = {node['id']: node['chunk_id'] for node in nodes}
    neighbors = set()
    for edge in edges:
        if edge['type'] in {'IMPORTS_POTENTIAL', 'CALLS_STATIC'}:
            source, target = node_chunks.get(edge['source']), node_chunks.get(edge['target'])
            if source in anchors and target and target != source:
                neighbors.add(target)
            if target in anchors and source and source != target:
                neighbors.add(source)
    for row in ranking:
        row['relationship_points'] = int(row['chunk_id'] in neighbors)
    # Keep the strongest existing leaders; this is a candidate order, not persisted retrieval.
    head, tail = ranking[:4], ranking[4:]
    tail.sort(key=lambda row: (row['baseline_rank'] - row['signal_points'] - row['relationship_points'],
                               row['baseline_rank'], row['chunk_id']))
    ranked = head + tail
    return {'version': 'cie-v1', 'label': 'RULE-BASED ANALYSIS — POSSIBLE CAUSES, NOT VERIFIED',
            'signals': signals, 'nodes': nodes, 'edges': edges, 'candidate_ranking': ranked,
            'findings': findings[:10], 'abstained': not findings,
            'limitations': ['Only existing evidence chunks are analyzed; partial Python chunks may not parse.',
                            'Static and potential relationships do not prove runtime behavior.',
                            'Analysis is bounded and does not reproduce the issue.', *sorted(set(limits))],
            'bytes_parsed': used}
