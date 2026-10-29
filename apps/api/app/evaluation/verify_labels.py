"""Verify benchmark labels against a local immutable Git object; never execute source."""
import argparse
import ast
import json
import subprocess
from pathlib import Path

from app.modules.ingestion.code_chunking import chunk_python
from app.modules.ingestion.code_selection import contains_sensitive_source, decode_source, eligible_python_path


def valid_label(source, label):
    """Require the entire labeled interval inside its symbol and one eligible chunk."""
    start, end = label['start_line'], label['end_line']
    if (not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int)
            or isinstance(end, bool) or start < 1 or end < start):
        return False
    nodes = ast.parse(source).body
    valid_node = any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and n.name == label['symbol']
        and min([n.lineno, *(decorator.lineno for decorator in n.decorator_list)]) <= start <= end <= n.end_lineno
        for n in nodes)
    valid_chunk = any(c.symbol == label['symbol'] and c.text.strip()
        and c.start_line <= start <= end <= c.end_line for c in chunk_python(source))
    return valid_node and valid_chunk


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path)
    args = parser.parse_args()
    dataset = json.loads(args.dataset.read_text())
    sha = dataset['commit_sha']
    if len(sha) != 40 or any(char not in '0123456789abcdef' for char in sha):
        raise SystemExit('Invalid commit SHA')
    checked = 0
    for query in dataset['queries']:
        for label in query['relevance']:
            path = label['path']
            if not eligible_python_path(path):
                raise SystemExit(f"Ineligible label: {query['id']}")
            raw = subprocess.check_output(['git', 'show', f'{sha}:{path}'])
            source = decode_source(raw, 100_000)
            if source is None or contains_sensitive_source(source):
                raise SystemExit(f"Rejected source: {query['id']}")
            if not valid_label(source, label):
                raise SystemExit(f"Unmatched label: {query['id']}")
            checked += 1
    print(f'{checked} labels match pinned Git symbols and eligible source chunks')


if __name__ == '__main__':
    main()
