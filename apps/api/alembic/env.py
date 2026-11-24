import os
import re

from alembic import context
from sqlalchemy import create_engine

from app.core.config import get_settings
from app.domain.models import Base


def _version_table_schema() -> str | None:
    schema = os.environ.get("ALEMBIC_VERSION_TABLE_SCHEMA")
    if schema is not None and not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", schema):
        raise RuntimeError("invalid Alembic version-table schema")
    return schema


def _include_object(obj, name, type_, reflected, compare_to) -> bool:
    # Alembic's version table is migration bookkeeping, not application metadata.
    return not (type_ == "table" and name == "alembic_version")


def _configure(**kwargs) -> None:
    schema = _version_table_schema()
    if schema is not None:
        kwargs["version_table_schema"] = schema
    kwargs["include_object"] = _include_object
    context.configure(**kwargs)

if context.is_offline_mode():
    _configure(url=get_settings().database_url, target_metadata=Base.metadata,
               literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with create_engine(get_settings().database_url).connect() as connection:
        _configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
