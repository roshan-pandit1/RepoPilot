"""Synthetic source fixtures; no real GitHub or application database access."""
from hashlib import sha256

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.domain.models import CodeChunk, CodeSnapshot, IndexJob, IndexedFile
from app.modules.ingestion.citations import github_citation
from app.modules.ingestion.code_collect import collect_source
from app.modules.ingestion.code_selection import eligible_source_path
from app.modules.ingestion.code_snapshot import plan_snapshot
from app.modules.investigation.code_intelligence import analyze
from app.workers.tasks import process_index
from test_auth_enrollment import csrf, github_auth as github_auth  # noqa: F401
from test_code_workflow import FakeSource, connect


class MixedSource(FakeSource):
    files = {
        "src/python.py": b"def python_total():\r\n    return 1\r\n",
        "src/view.tsx": "import React from 'react';\r\nfunction RenderWidget() { return <p>é</p>; }\r\n".encode(),
        "src/Calc.java": b"import java.util.List;\nclass Calc { int javaValue() { return 1; } }\n",
        "src/main.go": b"package main\nimport \"fmt\"\nfunc GoValue() { fmt.Println(1) }\n",
        "src/legacy.rb": b"def ruby; end\n",
        "src/bad.js": b"const bad = \x00;\n",
        "src/config.ts": b"key = '" + b"ghp_" + b"a" * 36 + b"'\n",
        "node_modules/no.js": b"function excluded() {}\n",
    }

    def repository(self, token, full_name):
        return {"private": False, "full_name": full_name, "default_branch": "main"}

    def tree(self, token, full_name, sha):
        entries = [{"path": path, "type": "blob", "mode": "100644", "sha": f"{n:040x}",
                    "size": len(content)} for n, (path, content) in enumerate(self.files.items(), 1)]
        entries.append({"path": "src/link.ts", "type": "blob", "mode": "120000", "sha": "f" * 40, "size": 5})
        return {"truncated": False, "tree": entries}

    def blob(self, token, full_name, sha, expected_size):
        return list(self.files.values())[int(sha, 16) - 1]


def test_default_plan_is_python_only_and_opt_in_tracks_unsupported_and_skipped():
    source = MixedSource()
    default = plan_snapshot(source, "token", "alice/public")
    assert [item.path for item in default.files] == ["src/python.py"]
    plan = plan_snapshot(source, "token", "alice/public", multilingual=True)
    assert [item.path for item in plan.files] == sorted(
        path for path in source.files if path.endswith((".py", ".tsx", ".java", ".go", ".js", ".ts"))
        and not path.startswith("node_modules/"))
    assert (plan.skipped_files, plan.unsupported_files) == (1, 1)
    collection = collect_source(source, "token", "alice/public", plan)
    assert collection.skipped_files == 3  # unsupported, binary, recognizable credential
    assert {item.language for item in collection.files} == {"python", "tsx", "java", "go"}
    for file in collection.files:
        original = source.files[file.path]
        assert file.content_hash == sha256(original).hexdigest()
        assert file.parser_status == "parsed" and file.parser_version
        assert "".join(chunk.text for chunk in file.chunks).encode() == original
        lines = original.decode().splitlines(keepends=True)
        assert all(chunk.text == "".join(lines[chunk.start_line - 1:chunk.end_line]) for chunk in file.chunks)
        assert file.import_ranges is not None
    assert collect_source(source, "token", "alice/public", plan) == collection


@pytest.mark.parametrize("path", ["../x.ts", "/x.ts", "a//b.go", "a/./x.java", "x\\y.ts",
                                  "node_modules/x.ts", ".git/x.ts", "src/credential.ts", "x.png",
                                  "src/bundle.min.js", "src/types.generated.ts", "src/thing.pb.go",
                                  "src/model.g.cs"])
def test_multilingual_path_selection_preserves_exclusions(path):
    assert not eligible_source_path(path, exclude_generated=True)


def test_parser_fallback_keeps_lines_and_never_invents_symbols(monkeypatch):
    source = MixedSource()
    source.files = {"bad.ts": b"function ( {\nlet x = 1;\n"}
    plan = plan_snapshot(source, "token", "alice/public", multilingual=True)
    item = collect_source(source, "token", "alice/public", plan).files[0]
    assert item.parser_status == "syntax_error"
    assert not any(chunk.symbol for chunk in item.chunks)
    assert "".join(chunk.text for chunk in item.chunks).encode() == source.files["bad.ts"]
    def missing(_module):
        raise ImportError("fixture")
    monkeypatch.setattr("app.modules.ingestion.language_analysis.import_module", missing)
    item = collect_source(source, "token", "alice/public", plan).files[0]
    assert item.parser_status == "parser_unavailable" and not any(c.symbol for c in item.chunks)


@pytest.mark.parametrize(("path", "text", "expected"), [
    ("sample.js", "import x from 'x';\nfunction jsFn() {}\n", "jsFn"),
    ("sample.mjs", "import x from 'x';\nfunction jsFn() {}\n", "jsFn"),
    ("sample.jsx", "import x from 'x';\nfunction jsFn() {return <p/>;}\n", "jsFn"),
    ("sample.ts", "import x from 'x';\nfunction tsFn(): void {}\n", "tsFn"),
    ("sample.tsx", "import x from 'x';\nfunction tsFn() {return <p/>;}\n", "tsFn"),
    ("sample.java", "import a.B;\nclass Klass {}\n", "Klass"),
    ("sample.go", 'package p\nimport "fmt"\nfunc goFn() {}\n', "goFn"),
    ("sample.rs", "use a::b;\nfn rust_fn() {}\n", "rust_fn"),
    ("sample.c", "#include <x.h>\nint c_fn() {return 0;}\n", "c_fn"),
    ("sample.h", "#include <x.h>\nint c_fn() {return 0;}\n", "c_fn"),
    ("sample.cpp", "#include <x.h>\nclass Klass {};\n", "Klass"),
    ("sample.cc", "#include <x.h>\nclass Klass {};\n", "Klass"),
    ("sample.hpp", "#include <x.h>\nclass Klass {};\n", "Klass"),
    ("sample.cs", "using System;\nclass Klass {}\n", "Klass"),
])
def test_language_fixtures_collect_parse_and_chunk(path, text, expected):
    source = MixedSource()
    source.files = {path: text.encode()}
    plan = plan_snapshot(source, "token", "alice/public", multilingual=True)
    file = collect_source(source, "token", "alice/public", plan).files[0]
    assert file.parser_status == "parsed" and file.import_ranges
    chunk = next(chunk for chunk in file.chunks if chunk.symbol == expected)
    assert chunk.symbol_kind and chunk.start_line == len(text.splitlines())
    assert "".join(chunk.text for chunk in file.chunks) == text


@pytest.mark.parametrize("separator", ["\u2028", "\u2029", "\x85", "\r", "\v", "\f"])
def test_nonstandard_line_separators_are_skipped_not_misquoted(separator):
    source = MixedSource()
    source.files = {"x.js": f"function first() {{}}{separator}function second() {{}}".encode()}
    plan = plan_snapshot(source, "token", "alice/public", multilingual=True)
    collection = collect_source(source, "token", "alice/public", plan)
    assert not collection.files and collection.skipped_files == 1


def test_oversized_and_unsupported_files_mark_plan_partial():
    source = MixedSource()
    source.files = {"x.js": b"x" * 101, "x.rb": b"ignored"}
    plan = plan_snapshot(source, "token", "alice/public", multilingual=True, max_file_bytes=100)
    assert not plan.files and plan.skipped_files == 2 and plan.unsupported_files == 1


def test_generated_sources_are_excluded_and_reported_as_skipped():
    source = MixedSource()
    source.files = {"src/x.generated.ts": b"export const x = 1;", "src/x.pb.go": b"package p"}
    plan = plan_snapshot(source, "token", "alice/public", multilingual=True)
    assert not plan.files and plan.skipped_files == 2 and plan.unsupported_files == 0


def test_citation_restricts_multilingual_paths_and_preserves_exact_commit_and_lines():
    assert github_citation("alice/public", "a" * 40, "src/my file.tsx", 2, 5) == (
        "https://github.com/alice/public/blob/" + "a" * 40 + "/src/my%20file.tsx#L2-L5")
    for path in ("../x.ts", "node_modules/x.js", "src/x.rb"):
        with pytest.raises(ValueError):
            github_citation("alice/public", "a" * 40, path, 1, 1)
    # A Python-only legacy snapshot may already contain a generated-named file.
    assert github_citation("alice/public", "a" * 40, "src/x.generated.py", 1, 1).endswith("/src/x.generated.py#L1-L1")


def test_cie_explicitly_skips_non_python_evidence():
    result = analyze("Find f", "", [{"path": "src/x.ts", "source": "function f() {}",
        "start_line": 1, "end_line": 1, "chunk_id": "fixture", "rank": 1}])
    assert result["abstained"] and not result["nodes"]
    assert "unsupported_non_python_evidence" in result["limitations"]
    assert any("Only Python evidence" in value for value in result["limitations"])


def test_opt_in_job_publication_is_partial_pinned_and_idempotent(client, factory, github_auth, monkeypatch):
    with monkeypatch.context() as env:
        env.setattr(get_settings(), "index_multilingual_enabled", True)
        connect(client)
        job_id = client.post("/v1/repositories/902/index", headers=csrf(client)).json()["job_id"]
        # The job's chosen mode persists even if the process configuration later changes.
        env.setattr(get_settings(), "index_multilingual_enabled", False)
        process_index(job_id, factory, github_auth, MixedSource())
        process_index(job_id, factory, github_auth, MixedSource())
        with factory() as db:
            job = db.get(IndexJob, job_id)
            snapshot = db.scalar(select(CodeSnapshot).where(CodeSnapshot.repository_id == 902))
            files = db.scalars(select(IndexedFile).where(IndexedFile.snapshot_id == snapshot.id)).all()
            assert job.indexing_mode == snapshot.indexing_mode == "multilingual"
            assert job.status == "partial" and snapshot.unsupported_count == 1
            assert snapshot.skipped_count == 3 and len(files) == 4
            assert {file.language for file in files} == {"python", "tsx", "java", "go"}
            assert len(db.scalars(select(CodeSnapshot).where(CodeSnapshot.repository_id == 902)).all()) == 1
            assert db.scalar(select(CodeChunk).where(CodeChunk.symbol == "RenderWidget")) is not None


def test_postgres_multilingual_search_and_citations(client, factory, github_auth, monkeypatch):
    if factory.kw["bind"].dialect.name != "postgresql":
        pytest.skip("PostgreSQL full-text search is required")
    with monkeypatch.context() as env:
        env.setattr(get_settings(), "index_multilingual_enabled", True)
        connect(client)
        job_id = client.post("/v1/repositories/902/index", headers=csrf(client)).json()["job_id"]
        process_index(job_id, factory, github_auth, MixedSource())
        for query, path in [("RenderWidget", "src/view.tsx"), ("javaValue", "src/Calc.java"),
                            ("GoValue", "src/main.go")]:
            response = client.post("/v1/repositories/902/search", headers=csrf(client), json={"query": query})
            assert response.status_code == 200 and response.json()["partial"]
            item = next(item for item in response.json()["items"] if item["path"] == path)
            assert item["commit_sha"] == "a" * 40
            assert item["url"] == github_citation("alice/public", "a" * 40, path,
                                                  item["start_line"], item["end_line"])


def test_typescript_evidence_and_mock_report_keep_verified_citations(client, factory, github_auth, monkeypatch):
    from app.modules.investigation.report_worker import process_report
    from app.workers.tasks import process_investigation
    from test_investigation_evidence import context, stub_retrieval, submit

    snapshot_id, chunk_id = context(client, factory, github_auth)
    with factory.begin() as db:
        chunk = db.get(CodeChunk, chunk_id)
        file = db.get(IndexedFile, chunk.file_id)
        file.path = "src/tasks.ts"
        chunk.source_text = "function process_sync() {\n  return null; }\n"
    stub_retrieval(monkeypatch, factory, chunk_id)
    parent = submit(client)
    process_investigation(parent, factory, github_auth)
    base = f"/v1/repositories/902/investigations/{parent}"
    evidence = client.get(base + "/evidence")
    assert evidence.status_code == 200
    assert "src/tasks.ts#L7-L8" in evidence.text
    requested = client.post(base + "/report", headers=csrf(client))
    assert requested.status_code == 202
    process_report(requested.json()["report_job_id"], factory, github_auth)
    report = client.get(base + "/report")
    assert report.status_code == 200 and report.json()["report"]["snapshot_id"] == snapshot_id
    assert "src/tasks.ts#L7-L8" in report.text
