"""Serialize lifecycle revocations with enrollment, including previously unknown IDs."""
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.domain.models import InstallationGuard, RepositoryGuard


def installation_guard(db: Session, installation_id: int) -> InstallationGuard:
    values = {"id": installation_id, "revoked": False}
    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    db.execute(insert(InstallationGuard).values(**values).on_conflict_do_nothing())
    return db.scalar(select(InstallationGuard).where(InstallationGuard.id == installation_id).with_for_update())


def repository_guard(db: Session, installation_id: int, repository_id: int) -> RepositoryGuard:
    values = {"installation_id": installation_id, "repository_id": repository_id, "revoked": False}
    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    db.execute(insert(RepositoryGuard).values(**values).on_conflict_do_nothing())
    return db.scalar(select(RepositoryGuard).where(
        RepositoryGuard.installation_id == installation_id,
        RepositoryGuard.repository_id == repository_id).with_for_update())
