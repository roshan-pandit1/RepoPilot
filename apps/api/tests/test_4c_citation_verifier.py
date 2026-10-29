import hashlib
import io
import json
import sys
from pathlib import Path

import pytest

from app.evaluation.git_source import GitSource
from app.modules.ingestion.code_chunking import chunk_python
from evaluation.verify_4c_citations import main


COMMIT = '956a4f92983b222ce179891bbde39cb49a2022b2'


def test_local_git_citation_verifier_detects_changed_chunk(monkeypatch, capsys):
    root = Path(__file__).resolve().parents[3]
    source = GitSource(root, COMMIT, 'alice/public')
    entry = next(row for row in source.entries if row['path'] == 'apps/api/app/modules/github/security.py')
    raw = source.blob('', 'alice/public', entry['sha'], entry['size'])
    chunk = next(row for row in chunk_python(raw.decode()) if row.symbol == 'valid_signature')
    item = {'path': entry['path'], 'symbol': chunk.symbol, 'start_line': chunk.start_line,
            'end_line': chunk.end_line, 'file_hash': hashlib.sha256(raw).hexdigest(),
            'chunk_hash': hashlib.sha256(chunk.text.encode()).hexdigest()}
    data = {'repository': 'alice/public', 'commit_sha': COMMIT, 'items': [item]}
    monkeypatch.setattr(sys, 'argv', ['verify_4c_citations.py', str(root)])
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(data)))
    main()
    assert '1 evidence chunk(s) match' in capsys.readouterr().out
    data['items'][0]['chunk_hash'] = '0' * 64
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(data)))
    with pytest.raises(ValueError, match='Git source chunk'):
        main()
