"""Check sanitized evidence fingerprints against local Git objects; no source is printed."""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from app.modules.ingestion.code_chunking import chunk_python
from app.modules.ingestion.citations import github_citation


def main():
    repo = Path(sys.argv[1]).resolve()
    data = json.load(sys.stdin)
    commit = data['commit_sha']
    if not isinstance(commit, str) or not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise SystemExit('Invalid snapshot commit.')
    subprocess.run(['git', '-C', str(repo), 'cat-file', '-e', f'{commit}^{{commit}}'],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    cache = {}
    for item in data['items']:
        path = item['path']
        github_citation(data['repository'], commit, path, item['start_line'], item['end_line'])
        if path not in cache:
            raw = subprocess.run(['git', '-C', str(repo), 'cat-file', 'blob', f'{commit}:{path}'],
                                 check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30).stdout
            if len(raw) > 100_000:
                raise ValueError('Git file exceeds indexing limit')
            cache[path] = (raw, chunk_python(raw.decode('utf-8')))
        raw, chunks = cache[path]
        if hashlib.sha256(raw).hexdigest() != item['file_hash']:
            raise ValueError('Git file does not match the indexed file')
        if not any(chunk.start_line == item['start_line'] and chunk.end_line == item['end_line']
                   and chunk.symbol == item['symbol']
                   and hashlib.sha256(chunk.text.encode()).hexdigest() == item['chunk_hash'] for chunk in chunks):
            raise ValueError('Git source chunk does not match the persisted evidence')
    print(f"Local Git verification: {len(data['items'])} evidence chunk(s) match commit {commit}.")
    if not data['items']:
        print('No evidence items: there are no citations to verify in this run.')
    print('Remote GitHub link resolution is not checked by this command.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, UnicodeError, subprocess.SubprocessError):
        raise SystemExit('Local Git evidence verification failed or commit is unavailable.') from None
