from datetime import datetime, timezone

from sqlalchemy import (
    JSON, BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey,
    ForeignKeyConstraint, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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
