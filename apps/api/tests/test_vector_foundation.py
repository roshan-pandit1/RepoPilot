import hashlib
import base64
import importlib.util
import os
import math
import socket
import subprocess
import sys
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.domain.models import CodeChunk, CodeSnapshot, IndexedFile, SnapshotPublication, now
from app.modules.ingestion.embedding_store import persist_embedding
from app.modules.ingestion.embeddings import EmbeddingError, FakeEmbeddingProvider
from app.modules.ingestion.local_embeddings import (MODELS, LocalEmbeddingProvider, _pool_hidden,
                                                    _validate_signature)
from app.modules.ingestion.semantic_search import search_vectors
from app.workers.tasks import process_index
from test_auth_enrollment import csrf, github_auth as github_auth  # noqa: F401
from test_code_workflow import FakeSource, connect


def local_provider(tmp_path, runtime, *, model="sentence-transformers/all-MiniLM-L6-v2", dimensions=384):
    model_bytes, tokenizer = b"synthetic graph", b"synthetic tokenizer"
    (tmp_path / "model.onnx").write_bytes(model_bytes)
    (tmp_path / "tokenizer.json").write_bytes(tokenizer)
    return LocalEmbeddingProvider(model=model, revision="a" * 40, dimensions=dimensions, root=str(tmp_path),
        model_sha256=hashlib.sha256(model_bytes).hexdigest(), tokenizer_sha256=hashlib.sha256(tokenizer).hexdigest(),
        enabled=True, runtime=runtime)


def test_local_opt_in_identity_and_missing_artifacts(tmp_path):
    kwargs = dict(model="sentence-transformers/all-MiniLM-L6-v2", revision="a" * 40, dimensions=384,
                  root=str(tmp_path), model_sha256="b" * 64, tokenizer_sha256="c" * 64)
    with pytest.raises(EmbeddingError, match="LOCAL_EMBEDDINGS_DISABLED"):
        LocalEmbeddingProvider(**kwargs)
    with pytest.raises(EmbeddingError, match="LOCAL_CONFIGURATION_INVALID"):
        LocalEmbeddingProvider(**{**kwargs, "revision": "main"}, enabled=True)
    with pytest.raises(EmbeddingError, match="LOCAL_CONFIGURATION_INVALID"):
        LocalEmbeddingProvider(**{**kwargs, "dimensions": 1}, enabled=True)
    provider = LocalEmbeddingProvider(**kwargs, enabled=True)
    with pytest.raises(EmbeddingError, match="MODEL_NOT_AVAILABLE"):
        provider.available()


def test_local_query_document_prefixes_normalization_and_network_fence(tmp_path, monkeypatch):
    observed = []
    def runtime(model, tokenizer, texts, spec):
        observed.append((model, tokenizer, texts, spec.tokens))
        return [[3.0, 4.0] + [0.0] * 766 for _ in texts]
    provider = local_provider(tmp_path, runtime, model="nomic-ai/CodeRankEmbed", dimensions=768)
    monkeypatch.setattr(socket.socket, "connect", lambda *args: pytest.fail("unexpected network"))
    document = provider.embed(["def total(): pass"]).vectors[0]
    query = provider.embed_query("calculate total").vectors[0]
    assert math.isclose(math.hypot(*document), 1.0) and query == document
    assert observed[0][2] == ["def total(): pass"]
    assert observed[1][2] == ["Represent this query for searching relevant code: calculate total"]
    assert observed[0][3] == 512 and provider.revision == "a" * 40
    assert provider.version.startswith(provider.revision + ":") and len(provider.contract) == 64
    prefix = "Represent this query for searching relevant code: "
    provider.embed_query("  " + prefix + prefix + "calculate total")
    assert observed[-1][2] == [prefix + "calculate total"]
    with pytest.raises(EmbeddingError, match="embedding_input_invalid"):
        provider.embed_query(prefix)
    with pytest.raises(EmbeddingError, match="embedding_input_invalid"):
        provider.embed(["x"] * 9)
    (tmp_path / "model.onnx").write_bytes(b"tampered")
    with pytest.raises(EmbeddingError, match="MODEL_NOT_AVAILABLE"):
        provider.embed_query("x")


def test_coderank_revisions_and_tokenizer_hash_are_bound_to_contract(tmp_path):
    provider = local_provider(tmp_path, lambda *_: [[1.0] * 768], model="nomic-ai/CodeRankEmbed", dimensions=768)
    args = dict(model=provider.model, revision=provider.revision, dimensions=768, root=str(tmp_path),
                model_sha256=provider.model_sha256, tokenizer_sha256=provider.tokenizer_sha256,
                enabled=True, runtime=provider.runtime)
    assert provider.tokenizer_revision == provider.revision
    other = LocalEmbeddingProvider(**args, tokenizer_revision="b" * 40)
    assert provider.contract != other.contract and provider.version != other.version
    with pytest.raises(EmbeddingError, match="LOCAL_CONFIGURATION_INVALID"):
        LocalEmbeddingProvider(**args, tokenizer_revision="main")
    with pytest.raises(EmbeddingError, match="LOCAL_CONFIGURATION_INVALID"):
        LocalEmbeddingProvider(**{**args, "dimensions": 384})
    (tmp_path / "tokenizer.json").write_bytes(b"tampered tokenizer")
    with pytest.raises(EmbeddingError, match="MODEL_NOT_AVAILABLE"):
        provider.embed_query("query")


def test_coderank_cls_pooling_and_documented_graph_signature():
    import numpy as np

    spec = MODELS["nomic-ai/CodeRankEmbed"]
    hidden = np.zeros((1, 2, 768), dtype=np.float32)
    hidden[0, 0, :2], hidden[0, 1, :2] = (3, 4), (99, 1)
    assert _pool_hidden(hidden, np.array([[1, 1]]), spec)[0, :2].tolist() == [3, 4]
    with pytest.raises(ValueError, match="invalid_output"):
        _pool_hidden(hidden, np.array([[1]]), spec)
    inputs = [SimpleNamespace(name=name, type="tensor(int64)", shape=["batch", "sequence"])
              for name in spec.input_names]
    output = SimpleNamespace(name="last_hidden_state", type="tensor(float)", shape=["batch", "sequence", 768])
    session = SimpleNamespace(get_inputs=lambda: inputs, get_outputs=lambda: [output])
    _validate_signature(session, spec)
    inputs[1].type = "tensor(float)"
    with pytest.raises(ValueError, match="incompatible_model_signature"):
        _validate_signature(session, spec)
    inputs[1].type = "tensor(int64)"
    output.name = "sentence_embedding"
    with pytest.raises(ValueError, match="incompatible_model_signature"):
        _validate_signature(session, spec)
    output.name, output.shape = "last_hidden_state", ["batch", "sequence", 384]
    with pytest.raises(ValueError, match="incompatible_model_signature"):
        _validate_signature(session, spec)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 0.0])
def test_local_invalid_vectors_are_rejected(tmp_path, value):
    provider = local_provider(tmp_path, lambda *_: [[value] * 384])
    with pytest.raises(EmbeddingError):
        provider.embed(["source"])


def test_local_runtime_errors_do_not_expose_source(tmp_path):
    def broken(*_args):
        raise RuntimeError("secret source")
    provider = local_provider(tmp_path, broken)
    with pytest.raises(EmbeddingError) as exc:
        provider.embed(["secret source"])
    assert str(exc.value) == "LOCAL_INFERENCE_FAILED"


def test_disabled_provider_does_not_import_ml_runtime():
    env = {**os.environ, "APP_ENV": "test", "DATABASE_URL": "sqlite://",
           "GITHUB_WEBHOOK_SECRET": "test-only-" + "x" * 40, "EMBEDDING_PROVIDER": "disabled",
           "DEMO_AUTH_ENABLED": "false", "GITHUB_OAUTH_ENABLED": "false"}
    check = subprocess.run([sys.executable, "-c", "import sys; import app.main; assert 'onnxruntime' not in sys.modules and 'tokenizers' not in sys.modules"],
                           env=env, capture_output=True, text=True, timeout=20)
    assert check.returncode == 0, check.stderr


def test_local_onnx_runtime_with_synthetic_graph_and_no_network(tmp_path, monkeypatch):
    if any(importlib.util.find_spec(name) is None for name in ("onnxruntime", "numpy", "tokenizers")):
        pytest.skip("optional local inference dependencies are not installed")
    from tokenizers import Tokenizer, models, pre_tokenizers

    # Tiny synthetic Cast/Unsqueeze/Tile graph: output repeats token IDs 384 times.
    # It contains no downloaded model weights and tests mechanics only.
    graph = base64.b64decode("CAg6wQEKHwoJaW5wdXRfaWRzEgF4IgRDYXN0KgkKAnRvGAGgAQIKFwoBeAoEYXhlcxIBeSIJVW5zcXVlZXplChkKAXkKBnJlcGVhdBIGb3V0cHV0IgRUaWxlEgdmaXh0dXJlKg0IARAHOgECQgRheGVzKhIIAxAHOgQBAYADQgZyZXBlYXRaHQoJaW5wdXRfaWRzEhAKDggHEgoKAxIBYgoDEgFzYh8KBm91dHB1dBIVChMIARIPCgMSAWIKAxIBcwoDCIADQgQKABAN")
    tokenizer = Tokenizer(models.WordLevel({"[PAD]": 0, "[UNK]": 1, "sample": 2}, unk_token="[UNK]"))
    tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
    encoded = tokenizer.to_str().encode()
    (tmp_path / "model.onnx").write_bytes(graph)
    (tmp_path / "tokenizer.json").write_bytes(encoded)
    provider = LocalEmbeddingProvider(model="sentence-transformers/all-MiniLM-L6-v2", revision="a" * 40,
        dimensions=384, root=str(tmp_path), model_sha256=hashlib.sha256(graph).hexdigest(),
        tokenizer_sha256=hashlib.sha256(encoded).hexdigest(), enabled=True)
    monkeypatch.setenv("ORT_DISABLE_TELEMETRY", "1")
    monkeypatch.setattr(socket.socket, "connect", lambda *args: pytest.fail("unexpected network"))
    vector = provider.embed_query("sample").vectors[0]
    assert len(vector) == 384 and math.isclose(math.hypot(*vector), 1.0)
    assert all(math.isclose(value, 1 / math.sqrt(384), rel_tol=1e-6) for value in vector)


def test_coderank_onnx_synthetic_graph_tokenizer_and_repeatability(tmp_path, monkeypatch):
    if any(importlib.util.find_spec(name) is None for name in ("onnxruntime", "numpy", "tokenizers")):
        pytest.skip("optional local inference dependencies are not installed")
    from tokenizers import Tokenizer, models, pre_tokenizers, processors

    # Hand-built 768-dimensional graph, with the documented names and no real weights.
    graph = base64.b64decode("CAg6nwIKHwoJaW5wdXRfaWRzEgF4IgRDYXN0KgkKAnRvGAGgAQIKFwoBeAoEYXhlcxIBeSIJVW5zcXVlZXplCiQKAXkKBnJlcGVhdBIRbGFzdF9oaWRkZW5fc3RhdGUiBFRpbGUSB2ZpeHR1cmUqDQgBEAc6AQJCBGF4ZXMqEggDEAc6BAEBgAZCBnJlcGVhdFodCglpbnB1dF9pZHMSEAoOCAcSCgoDEgFiCgMSAXNaIgoOYXR0ZW50aW9uX21hc2sSEAoOCAcSCgoDEgFiCgMSAXNaIgoOdG9rZW5fdHlwZV9pZHMSEAoOCAcSCgoDEgFiCgMSAXNiKgoRbGFzdF9oaWRkZW5fc3RhdGUSFQoTCAESDwoDEgFiCgMSAXMKAwiABkIECgAQDQ==")
    vocab = {f"v{i}": i for i in range(105)}
    for token, index in (("[PAD]", 0), ("[UNK]", 100), ("[CLS]", 101), ("[SEP]", 102), ("sample", 104)):
        del vocab[f"v{index}"]
        vocab[token] = index
    tokenizer = Tokenizer(models.WordLevel(vocab, unk_token="[UNK]"))
    tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
    tokenizer.post_processor = processors.TemplateProcessing(single="[CLS] $A [SEP]",
        special_tokens=[("[CLS]", 101), ("[SEP]", 102)])
    encoded = tokenizer.to_str().encode()
    (tmp_path / "model.onnx").write_bytes(graph)
    (tmp_path / "tokenizer.json").write_bytes(encoded)
    args = dict(model="nomic-ai/CodeRankEmbed", revision="a" * 40, dimensions=768, root=str(tmp_path),
        model_sha256=hashlib.sha256(graph).hexdigest(), tokenizer_sha256=hashlib.sha256(encoded).hexdigest(),
        enabled=True)
    provider = LocalEmbeddingProvider(**args)
    monkeypatch.setenv("ORT_DISABLE_TELEMETRY", "1")
    monkeypatch.setattr(socket.socket, "connect", lambda *args: pytest.fail("unexpected network"))
    first = provider.embed_query("sample").vectors[0]
    second = provider.embed_query("sample").vectors[0]
    assert first == pytest.approx(second, abs=1e-7)
    assert math.isclose(math.hypot(*first), 1.0) and len(first) == 768
    tokenizer.post_processor = None
    invalid = tokenizer.to_str().encode()
    (tmp_path / "tokenizer.json").write_bytes(invalid)
    args["tokenizer_sha256"] = hashlib.sha256(invalid).hexdigest()
    with pytest.raises(EmbeddingError, match="LOCAL_INFERENCE_FAILED"):
        LocalEmbeddingProvider(**args).embed_query("sample")


def test_missing_local_model_is_clear_and_does_not_enqueue(client, factory, github_auth, monkeypatch, tmp_path):
    from app.core.config import get_settings
    from app.domain.models import EmbeddingJob
    config = get_settings()
    for name, value in {"embedding_provider": "local", "embedding_local_enabled": True,
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2", "embedding_dimensions": 384,
        "embedding_local_revision": "a" * 40, "embedding_local_model_sha256": "b" * 64,
        "embedding_local_tokenizer_sha256": "c" * 64, "embedding_local_path": str(tmp_path)}.items():
        monkeypatch.setattr(config, name, value)
    monkeypatch.setattr(socket.socket, "connect", lambda *args: pytest.fail("unexpected network"))
    connect(client)
    response = client.post("/v1/repositories/902/embeddings", headers=csrf(client))
    assert response.status_code == 503 and response.json()["detail"] == "MODEL_NOT_AVAILABLE"
    assert client.get("/v1/repositories/902/embedding-status").json()["error_code"] == "MODEL_NOT_AVAILABLE"
    assert client.get("/v1/repositories/902/embedding-status").json()["availability_error"] == "MODEL_NOT_AVAILABLE"
    with factory() as db:
        assert db.scalar(select(EmbeddingJob)) is None


def test_postgres_vector_identity_ties_integrity_and_isolation(client, factory, github_auth):
    if factory.kw["bind"].dialect.name != "postgresql":
        pytest.skip("PostgreSQL pgvector is required")
    connect(client)
    job = client.post("/v1/repositories/902/index", headers=csrf(client)).json()["job_id"]
    process_index(job, factory, github_auth, FakeSource())
    provider = FakeEmbeddingProvider(2)
    with factory.begin() as db:
        original = db.scalar(select(CodeChunk))
        file = db.get(IndexedFile, original.file_id)
        second = CodeChunk(id="second-fixture", file_id=file.id, repository_id=902, tenant_id=file.tenant_id,
                           symbol="other", start_line=3, end_line=3, source_text="other = 1\n")
        db.add(second)
        db.flush()
        persist_embedding(db, original, provider, [1.0, 0.0])
        persist_embedding(db, second, provider, [1.0, 0.0])
        snapshot_id, tenant_id = file.snapshot_id, file.tenant_id
    with factory() as db:
        rows = search_vectors(db, repository_id=902, tenant_id=tenant_id, snapshot_id=snapshot_id,
                              provider=provider, query_vector=[1.0, 0.0], limit=2, expected_chunks=2)
        assert [row[0].start_line for row in rows] == [1, 3]
        assert all(abs(float(row[2])) < 1e-6 for row in rows)
        assert search_vectors(db, repository_id=902, tenant_id=tenant_id + 1, snapshot_id=snapshot_id,
                              provider=provider, query_vector=[1.0, 0.0]) == []
        with pytest.raises(EmbeddingError, match="embeddings_incomplete"):
            search_vectors(db, repository_id=902, tenant_id=tenant_id, snapshot_id=snapshot_id,
                           provider=provider, query_vector=[1.0, 0.0], expected_chunks=3)
        class DifferentContract(FakeEmbeddingProvider):
            contract = "f" * 64
        assert search_vectors(db, repository_id=902, tenant_id=tenant_id, snapshot_id=snapshot_id,
                              provider=DifferentContract(2), query_vector=[1.0, 0.0]) == []
        with pytest.raises(EmbeddingError):
            search_vectors(db, repository_id=902, tenant_id=tenant_id, snapshot_id=snapshot_id,
                           provider=provider, query_vector=[math.nan, 1.0])
    with factory.begin() as db:
        db.get(CodeChunk, "second-fixture").source_text = "other = 2\n"
    with factory() as db:
        with pytest.raises(EmbeddingError, match="embedding_integrity_failed"):
            search_vectors(db, repository_id=902, tenant_id=tenant_id, snapshot_id=snapshot_id,
                           provider=provider, query_vector=[1.0, 0.0])
    with factory.begin() as db:
        db.get(CodeSnapshot, snapshot_id).published = False
    with factory() as db:
        assert search_vectors(db, repository_id=902, tenant_id=tenant_id, snapshot_id=snapshot_id,
                              provider=provider, query_vector=[1.0, 0.0]) == []


def test_postgres_local_injected_provider_job_search_fallback_and_revocation(client, factory, github_auth, monkeypatch, tmp_path):
    if factory.kw["bind"].dialect.name != "postgresql":
        pytest.skip("PostgreSQL pgvector is required")
    from app.workers.tasks import process_embedding

    provider = local_provider(tmp_path, lambda _model, _tokenizer, texts, _spec:
                              [[1.0] + [0.0] * 383 for _ in texts])
    monkeypatch.setattr("app.modules.ingestion.code_routes.configured_provider", lambda: provider)
    connect(client)
    index_id = client.post("/v1/repositories/902/index", headers=csrf(client)).json()["job_id"]
    process_index(index_id, factory, github_auth, FakeSource())
    job_response = client.post("/v1/repositories/902/embeddings", headers=csrf(client))
    assert job_response.status_code == 202
    job = job_response.json()["job_id"]
    process_embedding(job, factory, github_auth, provider)
    process_embedding(job, factory, github_auth, provider)
    assert client.get("/v1/repositories/902/embedding-status").json()["ready"]
    for mode in ("semantic", "hybrid"):
        response = client.post("/v1/repositories/902/search", headers=csrf(client),
                               json={"query": "calculate_total", "mode": mode})
        assert response.status_code == 200 and response.json()["mode"] == mode
        assert response.json()["semantic_identity"]["provider"] == "local-onnx"
        assert response.json()["semantic_identity"]["dimensions"] == 384
        assert response.json()["semantic_identity"]["quality"] == "not_evaluated"
        assert response.json()["missing_embeddings"] is False
        assert response.json()["items"][0]["url"].endswith("/src/total.py#L1-L2")
    other_tokenizer = LocalEmbeddingProvider(model=provider.model, revision=provider.revision,
        dimensions=provider.dimensions, root=str(tmp_path), model_sha256=provider.model_sha256,
        tokenizer_sha256=provider.tokenizer_sha256, tokenizer_revision="b" * 40,
        enabled=True, runtime=provider.runtime)
    monkeypatch.setattr("app.modules.ingestion.code_routes.configured_provider", lambda: other_tokenizer)
    incompatible = client.post("/v1/repositories/902/search", headers=csrf(client),
        json={"query": "calculate_total", "mode": "semantic"}).json()
    assert incompatible["mode"] == "keyword" and incompatible["fallback_reason"] == "embeddings_not_ready"
    assert incompatible["missing_embeddings"] is True
    monkeypatch.setattr("app.modules.ingestion.code_routes.configured_provider", lambda: provider)
    from app.domain.models import EmbeddingJob
    with factory.begin() as db:
        embedding_job = db.get(EmbeddingJob, job)
        embedding_job.total_chunks += 1
        embedding_job.completed_chunks += 1
    incomplete = client.post("/v1/repositories/902/search", headers=csrf(client),
                             json={"query": "calculate_total", "mode": "semantic"}).json()
    assert incomplete["mode"] == "keyword" and incomplete["fallback_reason"] == "embeddings_incomplete"
    assert incomplete["missing_embeddings"] is True
    with factory.begin() as db:
        embedding_job = db.get(EmbeddingJob, job)
        embedding_job.total_chunks -= 1
        embedding_job.completed_chunks -= 1
    with factory.begin() as db:
        snapshot = db.scalar(select(CodeSnapshot).where(CodeSnapshot.repository_id == 902))
        publication = db.get(SnapshotPublication, snapshot.id)
        publication.revoked_at, publication.revocation_reason = now(), "security"
    revoked = client.post("/v1/repositories/902/search", headers=csrf(client),
                          json={"query": "calculate_total", "mode": "semantic"})
    assert revoked.status_code == 409
    with factory.begin() as db:
        snapshot = db.scalar(select(CodeSnapshot).where(CodeSnapshot.repository_id == 902))
        publication = db.get(SnapshotPublication, snapshot.id)
        publication.revoked_at, publication.revocation_reason = None, None
    (tmp_path / "model.onnx").unlink()
    response = client.post("/v1/repositories/902/search", headers=csrf(client),
                           json={"query": "calculate_total", "mode": "semantic"})
    assert response.json()["mode"] == "keyword" and response.json()["fallback_reason"] == "MODEL_NOT_AVAILABLE"
    github_auth.include_repository = False
    assert client.post("/v1/repositories/902/search", headers=csrf(client),
                       json={"query": "calculate_total", "mode": "semantic"}).status_code == 404


def test_postgres_concurrent_active_embedding_jobs_are_unique(client, factory, github_auth):
    if factory.kw["bind"].dialect.name != "postgresql":
        pytest.skip("PostgreSQL concurrency is required")
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from uuid import uuid4
    from sqlalchemy.exc import IntegrityError
    from app.domain.models import AuthSession, EmbeddingJob

    connect(client)
    index_id = client.post("/v1/repositories/902/index", headers=csrf(client)).json()["job_id"]
    process_index(index_id, factory, github_auth, FakeSource())
    with factory() as db:
        snapshot = db.scalar(select(CodeSnapshot).where(CodeSnapshot.repository_id == 902))
        session = db.scalar(select(AuthSession).where(AuthSession.tenant_id == snapshot.tenant_id))
        snapshot_id, tenant_id, session_hash = snapshot.id, snapshot.tenant_id, session.id_hash
    barrier = Barrier(2)
    provider = FakeEmbeddingProvider(2)
    def insert():
        barrier.wait(timeout=5)
        try:
            with factory.begin() as db:
                db.add(EmbeddingJob(id=str(uuid4()), snapshot_id=snapshot_id, repository_id=902,
                    tenant_id=tenant_id, session_hash=session_hash, provider=provider.provider,
                    model=provider.model, model_version=provider.version, dimensions=provider.dimensions,
                    model_revision=provider.revision, representation_contract=provider.contract,
                    normalization=provider.normalization))
            return "created"
        except IntegrityError:
            return "rejected"
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(lambda _: insert(), range(2))) == ["created", "rejected"]
