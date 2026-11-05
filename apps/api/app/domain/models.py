from datetime import datetime, timezone

from sqlalchemy import (
    JSON, BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey,
    ForeignKeyConstraint, Index, Integer, String, Text, UniqueConstraint, text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from app.infra.vector_type import Vector


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    github_user_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    login: Mapped[str] = mapped_column(String(100))


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))


class Membership(Base):
    __tablename__ = "memberships"
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)


class Installation(Base):
    __tablename__ = "installations"
    __table_args__ = (UniqueConstraint("id", "tenant_id"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=False)


class Repository(Base):
    __tablename__ = "repositories"
    __table_args__ = (
        ForeignKeyConstraint(["installation_id", "tenant_id"],
                             ["installations.id", "installations.tenant_id"]),
        UniqueConstraint("id", "tenant_id"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    installation_id: Mapped[int] = mapped_column(BigInteger)
    full_name: Mapped[str] = mapped_column(String(250))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)


class Issue(Base):
    __tablename__ = "issues"
    __table_args__ = (
        ForeignKeyConstraint(["repository_id", "tenant_id"],
                             ["repositories.id", "repositories.tenant_id"]),
        UniqueConstraint("repository_id", "number"),
        CheckConstraint("number > 0"),
        CheckConstraint("state IN ('open', 'closed')"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    repository_id: Mapped[int] = mapped_column(BigInteger, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer)
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(1024))
    body: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(10))
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Delivery(Base):
    __tablename__ = "webhook_deliveries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    body_hash: Mapped[str] = mapped_column(String(64))
    event: Mapped[str] = mapped_column(String(40))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Outbox(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        ForeignKeyConstraint(["repository_id", "tenant_id"],
                             ["repositories.id", "repositories.tenant_id"]),
        CheckConstraint("status IN ('pending', 'processed', 'ignored', 'failed')"),
    )
    id: Mapped[str] = mapped_column(ForeignKey("webhook_deliveries.id"), primary_key=True)
    repository_id: Mapped[int] = mapped_column(BigInteger)
    tenant_id: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_dispatch_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OAuthAttempt(Base):
    __tablename__ = "oauth_attempts"
    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    verifier_ciphertext: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    github_token_ciphertext: Mapped[str] = mapped_column(Text)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (ForeignKeyConstraint(["tenant_id", "user_id"],
                                          ["memberships.tenant_id", "memberships.user_id"]),)


class PersonalTenant(Base):
    __tablename__ = "personal_tenants"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), unique=True)
    __table_args__ = (ForeignKeyConstraint(["tenant_id", "user_id"],
                                          ["memberships.tenant_id", "memberships.user_id"]),)


class InstallationGuard(Base):
    __tablename__ = "installation_guards"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class RepositoryGuard(Base):
    __tablename__ = "repository_guards"
    installation_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    repository_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class SyncJob(Base):
    __tablename__ = "sync_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    repository_id: Mapped[int] = mapped_column(BigInteger)
    tenant_id: Mapped[int] = mapped_column(Integer)
    session_hash: Mapped[str] = mapped_column(ForeignKey("auth_sessions.id_hash"))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_dispatch_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(["repository_id", "tenant_id"],
                             ["repositories.id", "repositories.tenant_id"]),
        CheckConstraint("status IN ('pending', 'processed', 'partial', 'ignored', 'failed')"),
    )


class IndexJob(Base):
    __tablename__ = "index_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    repository_id: Mapped[int] = mapped_column(BigInteger)
    tenant_id: Mapped[int] = mapped_column(Integer)
    session_hash: Mapped[str] = mapped_column(ForeignKey("auth_sessions.id_hash"))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_dispatch_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    commit_sha: Mapped[str | None] = mapped_column(String(40))
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(["repository_id", "tenant_id"], ["repositories.id", "repositories.tenant_id"]),
        CheckConstraint("status IN ('pending', 'running', 'completed', 'partial', 'failed', 'cancelled')"),
        Index("ix_index_jobs_dispatch", "status", "next_dispatch_at"),
        Index("uq_index_jobs_active", "repository_id", unique=True,
              postgresql_where=text("status IN ('pending', 'running')"),
              sqlite_where=text("status IN ('pending', 'running')")),
    )


class CodeSnapshot(Base):
    __tablename__ = "code_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    repository_id: Mapped[int] = mapped_column(BigInteger)
    tenant_id: Mapped[int] = mapped_column(Integer)
    commit_sha: Mapped[str] = mapped_column(String(40))
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (
        ForeignKeyConstraint(["repository_id", "tenant_id"], ["repositories.id", "repositories.tenant_id"]),
        UniqueConstraint("id", "repository_id", "tenant_id"),
        Index("uq_code_snapshots_published", "repository_id", unique=True,
              postgresql_where=text("published"), sqlite_where=text("published = 1")),
    )


class SnapshotPublication(Base):
    __tablename__ = "snapshot_publications"
    snapshot_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    repository_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocation_reason: Mapped[str | None] = mapped_column(String(40))
    __table_args__ = (
        ForeignKeyConstraint(["snapshot_id", "repository_id", "tenant_id"],
                             ["code_snapshots.id", "code_snapshots.repository_id", "code_snapshots.tenant_id"],
                             name="fk_snapshot_publication_owner"),
        CheckConstraint("(revoked_at IS NULL AND revocation_reason IS NULL) OR "
                        "(revoked_at IS NOT NULL AND revocation_reason IS NOT NULL AND revocation_reason IN ('security', 'integrity'))",
                        name="ck_snapshot_publication_revocation"),
    )


class IndexedFile(Base):
    __tablename__ = "indexed_files"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(36))
    repository_id: Mapped[int] = mapped_column(BigInteger)
    tenant_id: Mapped[int] = mapped_column(Integer)
    path: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    __table_args__ = (
        ForeignKeyConstraint(["snapshot_id", "repository_id", "tenant_id"],
                             ["code_snapshots.id", "code_snapshots.repository_id", "code_snapshots.tenant_id"]),
        UniqueConstraint("snapshot_id", "path"),
        UniqueConstraint("id", "repository_id", "tenant_id"),
        Index("ix_indexed_files_path_fts", text("to_tsvector('simple', path)"),
              postgresql_using="gin").ddl_if(dialect="postgresql"),
    )


class CodeChunk(Base):
    __tablename__ = "code_chunks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    file_id: Mapped[str] = mapped_column(String(36))
    repository_id: Mapped[int] = mapped_column(BigInteger)
    tenant_id: Mapped[int] = mapped_column(Integer)
    symbol: Mapped[str | None] = mapped_column(Text)
    start_line: Mapped[int] = mapped_column(Integer)
    end_line: Mapped[int] = mapped_column(Integer)
    source_text: Mapped[str] = mapped_column(Text)
    __table_args__ = (
        ForeignKeyConstraint(["file_id", "repository_id", "tenant_id"],
                             ["indexed_files.id", "indexed_files.repository_id", "indexed_files.tenant_id"]),
        UniqueConstraint("file_id", "start_line"),
        UniqueConstraint("id", "repository_id", "tenant_id", name="uq_code_chunks_owner"),
        CheckConstraint("start_line > 0 AND end_line >= start_line"),
        Index("ix_code_chunks_tenant_repository", "tenant_id", "repository_id"),
        Index("ix_code_chunks_fts", text("to_tsvector('simple', (coalesce(symbol, '') || ' ') || source_text)"),
              postgresql_using="gin").ddl_if(dialect="postgresql"),
    )


class EmbeddingCache(Base):
    __tablename__ = "embedding_cache"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    repository_id: Mapped[int] = mapped_column(BigInteger)
    tenant_id: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(150))
    model_version: Mapped[str] = mapped_column(String(80))
    dimensions: Mapped[int] = mapped_column(Integer)
    vector: Mapped[list[float]] = mapped_column(Vector().with_variant(JSON(), "sqlite"))
    status: Mapped[str] = mapped_column(String(16), default="ready")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(["repository_id", "tenant_id"], ["repositories.id", "repositories.tenant_id"]),
        UniqueConstraint("id", "repository_id", "tenant_id"),
        UniqueConstraint("repository_id", "tenant_id", "content_hash", "provider", "model", "model_version", "dimensions",
                         name="uq_embedding_cache_key"),
        CheckConstraint("dimensions BETWEEN 1 AND 2000"),
        CheckConstraint("status IN ('ready', 'failed')"),
    )


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"
    chunk_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    cache_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    repository_id: Mapped[int] = mapped_column(BigInteger)
    tenant_id: Mapped[int] = mapped_column(Integer)
    __table_args__ = (
        ForeignKeyConstraint(["chunk_id", "repository_id", "tenant_id"],
                             ["code_chunks.id", "code_chunks.repository_id", "code_chunks.tenant_id"]),
        ForeignKeyConstraint(["cache_id", "repository_id", "tenant_id"],
                             ["embedding_cache.id", "embedding_cache.repository_id", "embedding_cache.tenant_id"]),
        Index("ix_chunk_embeddings_owner", "tenant_id", "repository_id"),
    )


class EmbeddingJob(Base):
    __tablename__ = "embedding_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(36))
    repository_id: Mapped[int] = mapped_column(BigInteger)
    tenant_id: Mapped[int] = mapped_column(Integer)
    session_hash: Mapped[str] = mapped_column(ForeignKey("auth_sessions.id_hash"))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(150))
    model_version: Mapped[str] = mapped_column(String(80))
    dimensions: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_dispatch_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    total_chunks: Mapped[int] = mapped_column(Integer, default=0)
    completed_chunks: Mapped[int] = mapped_column(Integer, default=0)
    token_usage: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (
        ForeignKeyConstraint(["snapshot_id", "repository_id", "tenant_id"],
                             ["code_snapshots.id", "code_snapshots.repository_id", "code_snapshots.tenant_id"]),
        CheckConstraint("status IN ('pending', 'running', 'completed', 'failed', 'cancelled')"),
        CheckConstraint("dimensions BETWEEN 1 AND 2000"),
        Index("ix_embedding_jobs_dispatch", "status", "next_dispatch_at"),
        Index("uq_embedding_jobs_active", "repository_id", unique=True,
              postgresql_where=text("status IN ('pending', 'running')"),
              sqlite_where=text("status IN ('pending', 'running')")),
    )


class InvestigationJob(Base):
    __tablename__ = "investigation_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    repository_id: Mapped[int] = mapped_column(BigInteger)
    tenant_id: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    session_hash: Mapped[str] = mapped_column(ForeignKey("auth_sessions.id_hash"))
    issue_id: Mapped[int] = mapped_column(BigInteger)
    issue_number: Mapped[int] = mapped_column(Integer)
    operation: Mapped[str] = mapped_column(String(30), default="mock_orchestration", server_default="mock_orchestration")
    snapshot_id: Mapped[str | None] = mapped_column(String(36))
    snapshot_commit_sha: Mapped[str | None] = mapped_column(String(40))
    source_repository_name: Mapped[str | None] = mapped_column(String(250))
    retrieval_warning: Mapped[str | None] = mapped_column(String(40))
    query_version: Mapped[str | None] = mapped_column(String(30))
    query_limit: Mapped[int | None] = mapped_column(Integer)
    per_query_limit: Mapped[int | None] = mapped_column(Integer)
    evidence_limit: Mapped[int | None] = mapped_column(Integer)
    query_body_limit: Mapped[int | None] = mapped_column(Integer)
    query_input_truncated: Mapped[bool | None] = mapped_column(Boolean)
    issue_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    context_retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    __table_args__ = (
        ForeignKeyConstraint(["repository_id", "tenant_id"], ["repositories.id", "repositories.tenant_id"]),
        UniqueConstraint("id", "repository_id", "tenant_id"),
        UniqueConstraint("id", "snapshot_id", "repository_id", "tenant_id", name="uq_investigation_snapshot_owner"),
        ForeignKeyConstraint(["snapshot_id", "repository_id", "tenant_id"],
                             ["code_snapshots.id", "code_snapshots.repository_id", "code_snapshots.tenant_id"],
                             name="fk_investigation_snapshot_owner"),
        CheckConstraint("(operation = 'mock_orchestration' AND snapshot_id IS NULL AND snapshot_commit_sha IS NULL AND source_repository_name IS NULL AND query_version IS NULL) OR (operation = 'code_evidence' AND snapshot_id IS NOT NULL AND snapshot_commit_sha IS NOT NULL AND source_repository_name IS NOT NULL AND query_version IS NOT NULL AND query_limit IS NOT NULL AND query_limit BETWEEN 1 AND 3 AND per_query_limit IS NOT NULL AND per_query_limit BETWEEN 1 AND 20 AND evidence_limit IS NOT NULL AND evidence_limit BETWEEN 1 AND 30 AND query_body_limit IS NOT NULL AND query_body_limit BETWEEN 1 AND 4000)", name="ck_investigation_operation_snapshot"),
        CheckConstraint("issue_number > 0 AND issue_id > 0 AND attempts >= 0"),
        CheckConstraint("status IN ('queued', 'running', 'completed', 'failed', 'cancelled')"),
        Index("uq_investigation_active", "tenant_id", "user_id", "repository_id", "issue_number", unique=True,
              postgresql_where=text("status IN ('queued', 'running')"),
              sqlite_where=text("status IN ('queued', 'running')")),
    )


class InvestigationOutbox(Base):
    __tablename__ = "investigation_outbox"
    job_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    repository_id: Mapped[int] = mapped_column(BigInteger)
    tenant_id: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_dispatch_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(["job_id", "repository_id", "tenant_id"],
                             ["investigation_jobs.id", "investigation_jobs.repository_id", "investigation_jobs.tenant_id"]),
        CheckConstraint("status IN ('pending', 'processed') AND attempts >= 0"),
        Index("ix_investigation_outbox_dispatch", "status", "next_dispatch_at"),
    )


class InvestigationEvidence(Base):
    __tablename__ = "investigation_evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(36))
    snapshot_id: Mapped[str] = mapped_column(String(36))
    repository_id: Mapped[int] = mapped_column(BigInteger)
    tenant_id: Mapped[int] = mapped_column(Integer)
    chunk_id: Mapped[str] = mapped_column(String(36))
    rank: Mapped[int] = mapped_column(Integer)
    query_id: Mapped[str] = mapped_column(String(40))
    query_hash: Mapped[str] = mapped_column(String(64))
    chunk_fingerprint: Mapped[str] = mapped_column(String(64))
    query_rank: Mapped[int] = mapped_column(Integer)
    method: Mapped[str] = mapped_column(String(20), default="keyword")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(["job_id", "snapshot_id", "repository_id", "tenant_id"],
            ["investigation_jobs.id", "investigation_jobs.snapshot_id", "investigation_jobs.repository_id", "investigation_jobs.tenant_id"],
            name="fk_evidence_investigation_snapshot"),
        ForeignKeyConstraint(["chunk_id", "repository_id", "tenant_id"],
            ["code_chunks.id", "code_chunks.repository_id", "code_chunks.tenant_id"], name="fk_evidence_chunk_owner"),
        UniqueConstraint("job_id", "chunk_id", name="uq_evidence_job_chunk"),
        UniqueConstraint("job_id", "rank", name="uq_evidence_job_rank"),
        CheckConstraint("rank > 0 AND query_rank > 0 AND method = 'keyword'", name="ck_evidence_rank_method"),
    )


class InvestigationEvidenceManifest(Base):
    __tablename__ = "investigation_evidence_manifests"
    job_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(36), nullable=False)
    repository_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False)
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(30), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now)
    __table_args__ = (
        ForeignKeyConstraint(["job_id", "snapshot_id", "repository_id", "tenant_id"],
            ["investigation_jobs.id", "investigation_jobs.snapshot_id", "investigation_jobs.repository_id", "investigation_jobs.tenant_id"],
            name="fk_evidence_manifest_owner"),
        CheckConstraint("evidence_count BETWEEN 0 AND 30", name="ck_evidence_manifest_count"),
        CheckConstraint("version = 'evidence-v1'", name="ck_evidence_manifest_version"),
    )


class InvestigationReportJob(Base):
    __tablename__ = "investigation_report_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(String(36))
    snapshot_id: Mapped[str] = mapped_column(String(36))
    repository_id: Mapped[int] = mapped_column(BigInteger)
    tenant_id: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    session_hash: Mapped[str] = mapped_column(ForeignKey("auth_sessions.id_hash"))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    __table_args__ = (
        ForeignKeyConstraint(["investigation_id", "snapshot_id", "repository_id", "tenant_id"],
            ["investigation_jobs.id", "investigation_jobs.snapshot_id", "investigation_jobs.repository_id", "investigation_jobs.tenant_id"],
            name="fk_report_job_investigation_snapshot"),
        UniqueConstraint("investigation_id", name="uq_report_job_investigation"),
        UniqueConstraint("id", "repository_id", "tenant_id", name="uq_report_job_owner"),
        UniqueConstraint("id", "investigation_id", "snapshot_id", "repository_id", "tenant_id", name="uq_report_job_full_owner"),
        CheckConstraint("status IN ('queued', 'running', 'completed', 'failed', 'cancelled') AND attempts >= 0", name="ck_report_job_status"),
    )


class InvestigationReportOutbox(Base):
    __tablename__ = "investigation_report_outbox"
    job_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    repository_id: Mapped[int] = mapped_column(BigInteger)
    tenant_id: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_dispatch_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(["job_id", "repository_id", "tenant_id"],
            ["investigation_report_jobs.id", "investigation_report_jobs.repository_id", "investigation_report_jobs.tenant_id"],
            name="fk_report_outbox_owner"),
        CheckConstraint("status IN ('pending', 'processed') AND attempts >= 0", name="ck_report_outbox_status"),
        Index("ix_report_outbox_dispatch", "status", "next_dispatch_at"),
    )


class InvestigationReport(Base):
    __tablename__ = "investigation_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    report_job_id: Mapped[str] = mapped_column(String(36))
    investigation_id: Mapped[str] = mapped_column(String(36))
    snapshot_id: Mapped[str] = mapped_column(String(36))
    repository_id: Mapped[int] = mapped_column(BigInteger)
    tenant_id: Mapped[int] = mapped_column(Integer)
    commit_sha: Mapped[str] = mapped_column(String(40))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict] = mapped_column(JSON)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_microusd: Mapped[int | None] = mapped_column(Integer)
    input_truncated: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(["report_job_id", "investigation_id", "snapshot_id", "repository_id", "tenant_id"],
            ["investigation_report_jobs.id", "investigation_report_jobs.investigation_id", "investigation_report_jobs.snapshot_id", "investigation_report_jobs.repository_id", "investigation_report_jobs.tenant_id"],
            name="fk_report_job_full_owner"),
        UniqueConstraint("investigation_id", name="uq_report_investigation"),
        UniqueConstraint("report_job_id", name="uq_report_job"),
        CheckConstraint("provider = 'mock' AND model = 'deterministic-v1'", name="ck_report_mock_provider"),
        CheckConstraint("(input_tokens IS NULL OR input_tokens >= 0) AND (output_tokens IS NULL OR output_tokens >= 0) AND (cost_microusd IS NULL OR cost_microusd >= 0)", name="ck_report_usage"),
    )


class InvestigationExperiment(Base):
    __tablename__ = "investigation_experiments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mode: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    budget_microusd: Mapped[int] = mapped_column(BigInteger)
    investigation_budget_microusd: Mapped[int] = mapped_column(BigInteger)
    max_input_tokens: Mapped[int] = mapped_column(Integer)
    max_output_tokens: Mapped[int] = mapped_column(Integer)
    max_concurrent: Mapped[int] = mapped_column(Integer)
    max_requests: Mapped[int] = mapped_column(Integer)
    pricing_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_experiment_tenant"),
        CheckConstraint("mode IN ('actual', 'simulated') AND provider = 'openai' AND "
            "budget_microusd > 0 AND investigation_budget_microusd > 0 AND max_input_tokens > 0 AND "
            "max_output_tokens > 0 AND max_concurrent > 0 AND max_requests > 0", name="ck_experiment_limits"),
    )


class InvestigationProviderSelection(Base):
    __tablename__ = "investigation_provider_selections"
    job_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    repository_id: Mapped[int] = mapped_column(BigInteger)
    tenant_id: Mapped[int] = mapped_column(Integer)
    experiment_id: Mapped[str] = mapped_column(String(36))
    __table_args__ = (
        ForeignKeyConstraint(["job_id", "repository_id", "tenant_id"],
            ["investigation_report_jobs.id", "investigation_report_jobs.repository_id", "investigation_report_jobs.tenant_id"], name="fk_provider_selection_job"),
        ForeignKeyConstraint(["experiment_id", "tenant_id"],
            ["investigation_experiments.id", "investigation_experiments.tenant_id"], name="fk_provider_selection_experiment"),
        UniqueConstraint("job_id", "experiment_id", "tenant_id", name="uq_provider_selection_experiment"),
    )


class InvestigationUsageReservation(Base):
    __tablename__ = "investigation_usage_reservations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(36), unique=True)
    experiment_id: Mapped[str] = mapped_column(String(36))
    tenant_id: Mapped[int] = mapped_column(Integer)
    repository_id: Mapped[int] = mapped_column(BigInteger)
    investigation_id: Mapped[str] = mapped_column(String(36))
    snapshot_id: Mapped[str] = mapped_column(String(36))
    lease_token: Mapped[str] = mapped_column(String(36))
    state: Mapped[str] = mapped_column(String(16))
    mode: Mapped[str] = mapped_column(String(16))
    reserved_microusd: Mapped[int] = mapped_column(BigInteger)
    max_input_tokens: Mapped[int] = mapped_column(Integer)
    max_output_tokens: Mapped[int] = mapped_column(Integer)
    model: Mapped[str] = mapped_column(String(80))
    pricing_policy: Mapped[str] = mapped_column(String(80))
    input_rate_tenths: Mapped[int] = mapped_column(Integer)
    output_rate_tenths: Mapped[int] = mapped_column(Integer)
    accounted_microusd: Mapped[int | None] = mapped_column(BigInteger)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(["experiment_id", "tenant_id"],
            ["investigation_experiments.id", "investigation_experiments.tenant_id"], name="fk_usage_experiment"),
        ForeignKeyConstraint(["job_id", "investigation_id", "snapshot_id", "repository_id", "tenant_id"],
            ["investigation_report_jobs.id", "investigation_report_jobs.investigation_id", "investigation_report_jobs.snapshot_id", "investigation_report_jobs.repository_id", "investigation_report_jobs.tenant_id"], name="fk_usage_job"),
        ForeignKeyConstraint(["job_id", "experiment_id", "tenant_id"],
            ["investigation_provider_selections.job_id", "investigation_provider_selections.experiment_id",
             "investigation_provider_selections.tenant_id"], name="fk_usage_selection"),
        CheckConstraint("state IN ('reserved', 'sent', 'known', 'uncertain') AND "
            "mode IN ('actual', 'simulated') AND reserved_microusd > 0 AND max_input_tokens > 0 AND max_output_tokens > 0 AND input_rate_tenths > 0 AND output_rate_tenths > 0 AND "
            "(accounted_microusd IS NULL OR accounted_microusd >= 0) AND "
            "(input_tokens IS NULL OR input_tokens >= 0) AND (output_tokens IS NULL OR output_tokens >= 0) AND "
            "((state = 'known' AND accounted_microusd IS NOT NULL AND accounted_microusd <= reserved_microusd "
            "AND input_tokens IS NOT NULL AND output_tokens IS NOT NULL) OR "
            "(state <> 'known' AND accounted_microusd IS NULL AND input_tokens IS NULL AND output_tokens IS NULL))", name="ck_usage_reservation"),
        Index("ix_usage_experiment", "experiment_id", "investigation_id"),
    )


class InvestigationExecutorApproval(Base):
    """One-use simulated executor binding; no actual-mode approval is created here."""
    __tablename__ = "investigation_executor_approvals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(36), unique=True)
    experiment_id: Mapped[str] = mapped_column(String(36), unique=True)
    tenant_id: Mapped[int] = mapped_column(Integer)
    snapshot_id: Mapped[str] = mapped_column(String(36))
    source_commit: Mapped[str] = mapped_column(String(40))
    fixture_id: Mapped[str] = mapped_column(String(80))
    mode: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    request_sha256: Mapped[str] = mapped_column(String(64))
    manifest_sha256: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(16))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(["job_id", "experiment_id", "tenant_id"],
            ["investigation_provider_selections.job_id", "investigation_provider_selections.experiment_id",
             "investigation_provider_selections.tenant_id"], name="fk_executor_approval_selection"),
        CheckConstraint("state IN ('ready', 'consumed') AND mode IN ('simulated', 'actual') AND provider = 'openai' AND "
            "((state = 'ready' AND consumed_at IS NULL) OR (state = 'consumed' AND consumed_at IS NOT NULL))",
            name="ck_executor_approval_state"),
    )


class InvestigationTokenCount(Base):
    """Separate, simulated one-use count authorization and its bounded result."""
    __tablename__ = "investigation_token_counts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(36), unique=True)
    experiment_id: Mapped[str] = mapped_column(String(36), unique=True)
    investigation_id: Mapped[str] = mapped_column(String(36))
    snapshot_id: Mapped[str] = mapped_column(String(36))
    repository_id: Mapped[int] = mapped_column(BigInteger)
    tenant_id: Mapped[int] = mapped_column(Integer)
    source_commit: Mapped[str] = mapped_column(String(40))
    fixture_id: Mapped[str] = mapped_column(String(80))
    mode: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    account_sha256: Mapped[str] = mapped_column(String(64))
    project_sha256: Mapped[str] = mapped_column(String(64))
    generation_sha256: Mapped[str] = mapped_column(String(64))
    count_sha256: Mapped[str] = mapped_column(String(64))
    manifest_sha256: Mapped[str] = mapped_column(String(64))
    binding_sha256: Mapped[str] = mapped_column(String(64))
    pricing_policy: Mapped[str] = mapped_column(String(80))
    max_output_tokens: Mapped[int] = mapped_column(Integer)
    max_input_tokens: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(["job_id", "investigation_id", "snapshot_id", "repository_id", "tenant_id"],
            ["investigation_report_jobs.id", "investigation_report_jobs.investigation_id",
             "investigation_report_jobs.snapshot_id", "investigation_report_jobs.repository_id",
             "investigation_report_jobs.tenant_id"], name="fk_token_count_job_owner"),
        ForeignKeyConstraint(["job_id", "experiment_id", "tenant_id"],
            ["investigation_provider_selections.job_id", "investigation_provider_selections.experiment_id",
             "investigation_provider_selections.tenant_id"], name="fk_token_count_selection"),
        CheckConstraint("mode = 'simulated' AND provider = 'openai' AND max_input_tokens > 0 AND "
            "max_output_tokens > 0 AND status IN ('ready', 'sent', 'complete', 'uncertain') AND "
            "((status = 'ready' AND sent_at IS NULL AND completed_at IS NULL AND input_tokens IS NULL) OR "
            "(status = 'sent' AND sent_at IS NOT NULL AND completed_at IS NULL AND input_tokens IS NULL) OR "
            "(status = 'complete' AND sent_at IS NOT NULL AND completed_at IS NOT NULL AND input_tokens IS NOT NULL AND input_tokens >= 0) OR "
            "(status = 'uncertain' AND sent_at IS NOT NULL AND completed_at IS NOT NULL AND input_tokens IS NULL))",
            name="ck_token_count_state"),
    )


class InvestigationProviderTokenCount(Base):
    """Externally sourced count authorization; separate from all simulated counts."""
    __tablename__ = "investigation_provider_token_counts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(36), unique=True)
    experiment_id: Mapped[str] = mapped_column(String(36), unique=True)
    investigation_id: Mapped[str] = mapped_column(String(36))
    snapshot_id: Mapped[str] = mapped_column(String(36))
    repository_id: Mapped[int] = mapped_column(BigInteger)
    tenant_id: Mapped[int] = mapped_column(Integer)
    source_commit: Mapped[str] = mapped_column(String(40))
    fixture_id: Mapped[str] = mapped_column(String(80))
    origin: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    account_sha256: Mapped[str] = mapped_column(String(64))
    project_sha256: Mapped[str] = mapped_column(String(64))
    generation_sha256: Mapped[str] = mapped_column(String(64))
    count_sha256: Mapped[str] = mapped_column(String(64))
    manifest_sha256: Mapped[str] = mapped_column(String(64))
    binding_sha256: Mapped[str] = mapped_column(String(64))
    pricing_policy: Mapped[str] = mapped_column(String(80))
    fee_policy: Mapped[str] = mapped_column(String(80))
    service_tier: Mapped[str] = mapped_column(String(24))
    cache_ttl: Mapped[str] = mapped_column(String(8))
    max_input_tokens: Mapped[int] = mapped_column(Integer)
    max_output_tokens: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    fee_state: Mapped[str] = mapped_column(String(16))
    fee_reserved_microusd: Mapped[int] = mapped_column(BigInteger)
    fee_accounted_microusd: Mapped[int | None] = mapped_column(BigInteger)
    generation_approval_id: Mapped[str | None] = mapped_column(ForeignKey("investigation_executor_approvals.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(["job_id", "investigation_id", "snapshot_id", "repository_id", "tenant_id"],
            ["investigation_report_jobs.id", "investigation_report_jobs.investigation_id",
             "investigation_report_jobs.snapshot_id", "investigation_report_jobs.repository_id",
             "investigation_report_jobs.tenant_id"], name="fk_provider_count_job_owner"),
        ForeignKeyConstraint(["job_id", "experiment_id", "tenant_id"],
            ["investigation_provider_selections.job_id", "investigation_provider_selections.experiment_id",
             "investigation_provider_selections.tenant_id"], name="fk_provider_count_selection"),
        CheckConstraint("origin = 'external' AND provider = 'openai' AND max_input_tokens > 0 AND "
            "max_output_tokens > 0 AND fee_reserved_microusd >= 0 AND "
            "fee_state IN ('reserved', 'known', 'uncertain') AND "
            "((fee_state = 'known' AND fee_accounted_microusd IS NOT NULL AND fee_accounted_microusd >= 0 "
            "AND fee_accounted_microusd <= fee_reserved_microusd) OR "
            "(fee_state <> 'known' AND fee_accounted_microusd IS NULL)) AND "
            "((status = 'pending' AND sent_at IS NULL AND completed_at IS NULL AND input_tokens IS NULL "
            "AND invalidated_at IS NULL AND consumed_at IS NULL AND generation_approval_id IS NULL) OR "
            "(status = 'sent' AND sent_at IS NOT NULL AND completed_at IS NULL AND input_tokens IS NULL "
            "AND invalidated_at IS NULL AND consumed_at IS NULL AND generation_approval_id IS NULL) OR "
            "(status = 'verified' AND sent_at IS NOT NULL AND completed_at IS NOT NULL AND input_tokens IS NOT NULL "
            "AND input_tokens >= 0 AND invalidated_at IS NULL AND consumed_at IS NULL AND generation_approval_id IS NULL) OR "
            "(status = 'uncertain' AND sent_at IS NOT NULL AND completed_at IS NOT NULL AND input_tokens IS NULL "
            "AND invalidated_at IS NULL AND consumed_at IS NULL AND generation_approval_id IS NULL) OR "
            "(status = 'invalid' AND invalidated_at IS NOT NULL AND consumed_at IS NULL AND generation_approval_id IS NULL) OR "
            "(status = 'consumed' AND sent_at IS NOT NULL AND completed_at IS NOT NULL AND input_tokens IS NOT NULL "
            "AND input_tokens >= 0 AND invalidated_at IS NULL AND consumed_at IS NOT NULL AND generation_approval_id IS NOT NULL))",
            name="ck_provider_count_state"),
    )


class InvestigationRealReport(Base):
    __tablename__ = "investigation_real_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    report_job_id: Mapped[str] = mapped_column(String(36), unique=True)
    investigation_id: Mapped[str] = mapped_column(String(36), unique=True)
    snapshot_id: Mapped[str] = mapped_column(String(36))
    repository_id: Mapped[int] = mapped_column(BigInteger)
    tenant_id: Mapped[int] = mapped_column(Integer)
    commit_sha: Mapped[str] = mapped_column(String(40))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict] = mapped_column(JSON)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_microusd: Mapped[int | None] = mapped_column(BigInteger)
    input_truncated: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(["report_job_id", "investigation_id", "snapshot_id", "repository_id", "tenant_id"],
            ["investigation_report_jobs.id", "investigation_report_jobs.investigation_id", "investigation_report_jobs.snapshot_id", "investigation_report_jobs.repository_id", "investigation_report_jobs.tenant_id"], name="fk_real_report_job_full_owner"),
        ForeignKeyConstraint(["report_job_id"], ["investigation_provider_selections.job_id"], name="fk_real_report_selection"),
        CheckConstraint("provider = 'openai' AND model = 'gpt-5.6-terra'", name="ck_real_report_provider"),
    )
