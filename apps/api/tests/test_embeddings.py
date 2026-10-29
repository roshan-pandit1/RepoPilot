import math

import httpx
import pytest
from sqlalchemy import func, select

from app.domain.models import ChunkEmbedding, CodeChunk, EmbeddingCache, Repository
from app.modules.ingestion.code_chunking import chunk_python
from app.modules.ingestion.code_collect import CollectedFile, Collection
from app.modules.ingestion.code_persistence import publish_snapshot
from app.modules.ingestion.code_snapshot import SnapshotPlan
from app.modules.ingestion.embedding_store import persist_embedding
from app.modules.ingestion.embeddings import (
    EmbeddingError, FakeEmbeddingProvider, OpenAIEmbeddingProvider, validate_vectors,
)


def test_fake_provider_is_deterministic_and_rejects_invalid_vectors():
    provider = FakeEmbeddingProvider(8)
    assert provider.embed(["def find_item(): pass"]).vectors == provider.embed(["def find_item(): pass"]).vectors
    for vector in [[0.0] * 8, [math.nan] * 8, [True] * 8, [1.0] * 7]:
        with pytest.raises(EmbeddingError):
            validate_vectors([vector], 1, 8)


def test_vector_distance_is_a_scalar_not_a_vector():
    from sqlalchemy import Float
    from app.modules.ingestion.semantic_search import cosine_distance

    assert isinstance(cosine_distance().type, Float)


def test_real_provider_requires_explicit_opt_in_and_sanitizes_errors():
    with pytest.raises(EmbeddingError, match="paid_embeddings_not_authorized"):
        OpenAIEmbeddingProvider("test", 3, "secret")
    provider = OpenAIEmbeddingProvider("test", 3, "secret", allow_paid=True,
        transport=httpx.MockTransport(lambda request: httpx.Response(429, text="private response")), sleep=lambda _: None)
    with pytest.raises(EmbeddingError) as error:
        provider.embed(["source content"])
    assert "secret" not in str(error.value) and "source content" not in str(error.value)


def test_real_provider_retries_transient_failure_and_accounts_for_usage():
    calls = []
    def handler(request):
        calls.append(request.url.host)
        if len(calls) == 1:
            raise httpx.ReadTimeout("private detail", request=request)
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.1, 0.2]}],
                                         "usage": {"total_tokens": 10}})
    provider = OpenAIEmbeddingProvider("fixture", 2, "fixture-key", allow_paid=True,
        cost_per_million=2.0, transport=httpx.MockTransport(handler), sleep=lambda _: None)
    result = provider.embed(["fixture source"])
    assert result.vectors == [[0.1, 0.2]]
    assert result.tokens == 10 and result.estimated_cost_usd == 0.00002
    assert calls == ["api.openai.com", "api.openai.com"]


def test_cache_reuses_content_per_tenant_repository_model_and_dimensions(factory):
    source = "def hello():\n    return 42\n"
    collection = Collection((CollectedFile("hello.py", "b" * 64, tuple(chunk_python(source))),), 0, len(source))
    provider = FakeEmbeddingProvider(8)
    with factory.begin() as db:
        publish_snapshot(db, db.get(Repository, 2001), SnapshotPlan("a" * 40, ()), collection)
        chunk = db.scalar(select(CodeChunk))
        vector = provider.embed([chunk.source_text]).vectors[0]
        first = persist_embedding(db, chunk, provider, vector)
        second = persist_embedding(db, chunk, provider, vector)
        assert first.id == second.id
        assert db.scalar(select(func.count()).select_from(EmbeddingCache)) == 1
        assert db.scalar(select(func.count()).select_from(ChunkEmbedding)) == 1
        persist_embedding(db, chunk, FakeEmbeddingProvider(4), [1.0] * 4)
        assert db.scalar(select(func.count()).select_from(EmbeddingCache)) == 2
