from sqlalchemy import func, select

from app.core.config import get_settings
from app.domain.models import ChunkEmbedding, CodeSnapshot, EmbeddingCache, EmbeddingJob, Installation
from app.modules.ingestion.embeddings import FakeEmbeddingProvider
from app.workers.dispatcher import dispatch_once
from app.workers.tasks import process_embedding, process_index
from test_auth_enrollment import csrf, github_auth as github_auth, sign_in
from test_code_workflow import FakeSource, connect

def setup_index(client, factory, github, monkeypatch):
    monkeypatch.setattr(get_settings(), "embedding_provider", "fake")
    monkeypatch.setattr(get_settings(), "embedding_dimensions", 8)
    connect(client)
    index_id = client.post("/v1/repositories/902/index", headers=csrf(client)).json()["job_id"]
    process_index(index_id, factory, github, FakeSource())


def test_fake_embedding_job_is_durable_reuses_cache_and_processes(client, factory, github_auth, monkeypatch):
    setup_index(client, factory, github_auth, monkeypatch)
    before = client.get("/v1/repositories/902/embedding-status").json()
    assert before["generation_available"] and not before["ready"] and before["snapshot_commit"]
    assert client.post("/v1/repositories/902/embeddings").status_code == 403
    first = client.post("/v1/repositories/902/embeddings", headers=csrf(client))
    assert first.status_code == 202
    job_id = first.json()["job_id"]
    assert client.post("/v1/repositories/902/embeddings", headers=csrf(client)).json()["job_id"] == job_id
    sent = []
    dispatch_once(factory, lambda _: None, lambda _: None, lambda _: None, sent.append)
    assert sent == [job_id]
    process_embedding(job_id, factory, github_auth, FakeEmbeddingProvider(8))
    process_embedding(job_id, factory, github_auth, FakeEmbeddingProvider(8))
    with factory() as db:
        job = db.get(EmbeddingJob, job_id)
        assert (job.status, job.total_chunks, job.completed_chunks, job.token_usage) == ("completed", 1, 1, 0)
        assert db.scalar(select(func.count()).select_from(EmbeddingCache)) == 1
        assert db.scalar(select(func.count()).select_from(ChunkEmbedding)) == 1
    status = client.get("/v1/repositories/902/embedding-status").json()
    assert status["status"] == "completed" and status["ready"]
    assert status["job_commit"] == status["snapshot_commit"]
    assert (status["provider"], status["model"], status["dimensions"]) == ("fake", "deterministic-hash", 8)
    monkeypatch.setattr(get_settings(), "embedding_dimensions", 9)
    assert not client.get("/v1/repositories/902/embedding-status").json()["ready"]
    monkeypatch.setattr(get_settings(), "embedding_dimensions", 8)
    second = client.post("/v1/repositories/902/embeddings", headers=csrf(client)).json()["job_id"]
    process_embedding(second, factory, github_auth, FakeEmbeddingProvider(8))
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(EmbeddingCache)) == 1
        assert db.scalar(select(func.count()).select_from(ChunkEmbedding)) == 1


def test_embedding_job_cancels_if_installation_revoked(client, factory, github_auth, monkeypatch):
    setup_index(client, factory, github_auth, monkeypatch)
    job_id = client.post("/v1/repositories/902/embeddings", headers=csrf(client)).json()["job_id"]
    with factory.begin() as db:
        db.get(Installation, 901).active = False
    process_embedding(job_id, factory, github_auth, FakeEmbeddingProvider(8))
    with factory() as db:
        assert db.get(EmbeddingJob, job_id).status == "cancelled"
        assert db.scalar(select(func.count()).select_from(EmbeddingCache)) == 0
        assert db.scalar(select(CodeSnapshot).where(CodeSnapshot.published.is_(True)))


def test_embedding_revoked_during_provider_call_is_not_persisted(client, factory, github_auth, monkeypatch):
    setup_index(client, factory, github_auth, monkeypatch)
    job_id = client.post("/v1/repositories/902/embeddings", headers=csrf(client)).json()["job_id"]

    class RevokingProvider(FakeEmbeddingProvider):
        def embed(self, inputs):
            with factory.begin() as db:
                db.get(Installation, 901).active = False
            return super().embed(inputs)

    process_embedding(job_id, factory, github_auth, RevokingProvider(8))
    with factory() as db:
        assert db.get(EmbeddingJob, job_id).status == "cancelled"
        assert db.scalar(select(func.count()).select_from(EmbeddingCache)) == 0


def test_disabled_provider_fails_queued_job_safely(client, factory, github_auth, monkeypatch):
    setup_index(client, factory, github_auth, monkeypatch)
    job_id = client.post("/v1/repositories/902/embeddings", headers=csrf(client)).json()["job_id"]
    monkeypatch.setattr(get_settings(), "embedding_provider", "disabled")
    process_embedding(job_id, factory, github_auth)
    with factory() as db:
        assert db.get(EmbeddingJob, job_id).error_code == "embedding_provider_disabled"


def test_other_tenant_cannot_generate_or_search_embeddings(client, factory, github_auth, monkeypatch):
    setup_index(client, factory, github_auth, monkeypatch)
    assert client.post("/v1/auth/logout", headers=csrf(client)).status_code == 200
    assert client.get("/v1/repositories/902/embedding-status").status_code == 401
    github_auth.user_id = github_auth.account_id = 78
    sign_in(client)
    assert client.post("/v1/repositories/902/embeddings", headers=csrf(client)).status_code == 404
    assert client.get("/v1/repositories/902/embedding-status").status_code == 404
    assert client.post("/v1/repositories/902/search", headers=csrf(client),
                       json={"query": "calculate_total", "mode": "semantic"}).status_code == 404


def test_postgres_exact_vector_search_respects_owner(client, factory, github_auth, monkeypatch):
    import pytest
    from app.modules.ingestion.semantic_search import search_vectors

    if factory.kw["bind"].dialect.name != "postgresql":
        pytest.skip("PostgreSQL pgvector is required")
    setup_index(client, factory, github_auth, monkeypatch)
    unavailable = client.post("/v1/repositories/902/search", headers=csrf(client),
                              json={"query": "calculate_total", "mode": "hybrid"})
    assert unavailable.status_code == 200
    assert unavailable.json()["mode"] == "keyword"
    assert unavailable.json()["fallback_reason"] == "embeddings_not_ready"
    job_id = client.post("/v1/repositories/902/embeddings", headers=csrf(client)).json()["job_id"]
    provider = FakeEmbeddingProvider(8)
    process_embedding(job_id, factory, github_auth, provider)
    vector = provider.embed([FakeSource.source.decode()]).vectors[0]
    with factory() as db:
        job = db.get(EmbeddingJob, job_id)
        rows = search_vectors(db, repository_id=902, tenant_id=job.tenant_id, snapshot_id=job.snapshot_id,
                              provider=provider, query_vector=vector)
        assert len(rows) == 1 and rows[0][0].symbol == "calculate_total"
        assert abs(float(rows[0][2])) < 1e-5
        assert search_vectors(db, repository_id=902, tenant_id=job.tenant_id + 1000,
                              snapshot_id=job.snapshot_id, provider=provider, query_vector=vector) == []
        class DifferentModel(FakeEmbeddingProvider):
            model = 'another-model'

        assert search_vectors(db, repository_id=902, tenant_id=job.tenant_id,
                              snapshot_id=job.snapshot_id, provider=DifferentModel(8), query_vector=vector) == []
        assert search_vectors(db, repository_id=902, tenant_id=job.tenant_id,
                              snapshot_id=job.snapshot_id, provider=FakeEmbeddingProvider(9),
                              query_vector=[1.0] * 9) == []
        snapshot_id, tenant_id = job.snapshot_id, job.tenant_id
    with factory.begin() as db:
        db.get(CodeSnapshot, snapshot_id).published = False
    with factory() as db:
        assert search_vectors(db, repository_id=902, tenant_id=tenant_id,
                              snapshot_id=snapshot_id, provider=provider, query_vector=vector) == []


def test_postgres_search_modes_and_keyword_fallback(client, factory, github_auth, monkeypatch):
    import pytest

    if factory.kw["bind"].dialect.name != "postgresql":
        pytest.skip("PostgreSQL pgvector is required")
    setup_index(client, factory, github_auth, monkeypatch)
    job_id = client.post("/v1/repositories/902/embeddings", headers=csrf(client)).json()["job_id"]
    process_embedding(job_id, factory, github_auth, FakeEmbeddingProvider(8))
    for mode in ("keyword", "semantic", "hybrid"):
        response = client.post("/v1/repositories/902/search", headers=csrf(client),
                               json={"query": "calculate_total", "mode": mode})
        assert response.status_code == 200
        result = response.json()
        assert result["mode"] == mode
        assert result["items"][0]["symbol"] == "calculate_total"
        assert result["items"][0]["url"].endswith("/src/total.py#L1-L2")
        assert "vector" not in result["items"][0]
    monkeypatch.setattr(get_settings(), "embedding_provider", "disabled")
    response = client.post("/v1/repositories/902/search", headers=csrf(client),
                           json={"query": "calculate_total", "mode": "semantic"})
    assert response.json()["mode"] == "keyword"
    assert response.json()["fallback_reason"] == "embedding_provider_disabled"
    assert response.json()["items"][0]["retrieval_method"] == "keyword"
