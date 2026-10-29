"""Minimal pgvector type; SQLite JSON is used only for non-vector unit tests."""
import json
import math

from sqlalchemy.types import UserDefinedType
from sqlalchemy.dialects.postgresql.base import ischema_names


class Vector(UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **kw):
        return "vector"

    def bind_processor(self, dialect):
        def bind(value):
            if value is None:
                return None
            if not isinstance(value, (list, tuple)) or not value or any(
                isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in value
            ):
                raise ValueError("Invalid vector")
            return "[" + ",".join(str(float(v)) for v in value) + "]"
        return bind

    def result_processor(self, dialect, coltype):
        def result(value):
            return None if value is None else json.loads(value) if isinstance(value, str) else list(value)
        return result


# SQLAlchemy does not include pgvector in its built-in reflection registry.
ischema_names.setdefault("vector", Vector)
