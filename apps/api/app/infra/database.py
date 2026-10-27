from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine():
    url = get_settings().database_url
    args = {"connect_timeout": 3} if url.startswith("postgresql") else {}
    return create_engine(url, pool_pre_ping=True, hide_parameters=True, connect_args=args)


@lru_cache
def get_session_factory():
    return sessionmaker(get_engine(), expire_on_commit=False)


def get_db():
    with get_session_factory()() as session:
        yield session
