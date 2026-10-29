from pathlib import Path

import pytest

from app.evaluation.git_source import GitSource
from app.modules.ingestion.code_collect import collect_source
from app.modules.ingestion.code_snapshot import plan_snapshot


COMMIT = "956a4f92983b222ce179891bbde39cb49a2022b2"


def test_git_source_reads_pinned_commit_and_rejects_unknown_objects():
    root = Path(__file__).resolve().parents[3]
    source = GitSource(root, COMMIT, "test/public")
    plan = plan_snapshot(source, "", "test/public")
    assert plan.commit_sha == COMMIT
    collection = collect_source(source, "", "test/public", plan)
    assert any(file.path == "apps/api/app/modules/ingestion/code_chunking.py"
               and any(chunk.symbol == "chunk_python" for chunk in file.chunks)
               for file in collection.files)
    with pytest.raises(ValueError):
        source.tree("", "test/public", "0" * 40)
    with pytest.raises(ValueError):
        source.blob("", "test/public", "0" * 40, 1)
    with pytest.raises(ValueError):
        GitSource(root, "HEAD", "test/public")
