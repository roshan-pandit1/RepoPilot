import pytest

from app.modules.ingestion.code_chunking import chunk_python
from app.modules.ingestion.code_selection import decode_source, eligible_python_path


def test_decorated_symbols_and_lines_are_preserved():
    source = 'import os\n\n@decorator\ndef hello():\n    return "hi"\n\nclass Item:\n    pass\n'
    chunks = chunk_python(source)
    assert [(c.start_line, c.end_line, c.symbol) for c in chunks] == [
        (1, 2, None), (3, 5, "hello"), (6, 6, None), (7, 8, "Item")]
    assert "".join(c.text for c in chunks) == source
    assert all(c.text == "".join(source.splitlines(keepends=True)[c.start_line-1:c.end_line])
               for c in chunks)


def test_invalid_and_large_files_are_deterministic_and_bounded():
    source = "def broken(:\n" + "x = 1\n" * 5
    chunks = chunk_python(source, max_lines=2)
    assert [(c.start_line, c.end_line) for c in chunks] == [(1, 2), (3, 4), (5, 6)]
    assert "".join(c.text for c in chunks) == source
    assert chunks == chunk_python(source, max_lines=2)
    assert chunk_python("") == []
    with pytest.raises(ValueError):
        chunk_python(source, max_lines=0)


@pytest.mark.parametrize("path", ["../a.py", "/a.py", "a//b.py", "a/./b.py", "a\\b.py",
                                  "node_modules/a.py", ".venv/a.py", "credentials.py",
                                  ".secrets.py", "file.txt"])
def test_unsafe_or_unwanted_paths_are_skipped(path):
    assert not eligible_python_path(path)


def test_source_selection_enforces_byte_limit_and_text():
    assert eligible_python_path("src/app.py")
    assert decode_source(b"x = 1\r\n", 10) == "x = 1\r\n"
    assert decode_source(b"too big", 3) is None
    assert decode_source(b"abc\x00", 100) is None
    assert decode_source(b"\xff", 100) is None
