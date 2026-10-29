from sqlalchemy import text

from app.core.config import get_settings
from app.domain.models import Installation, Membership, Repository, Tenant, User
from app.infra.database import get_session_factory


def seed(factory=None):
    config = get_settings()
    if config.app_env == "production" or not config.demo_auth_enabled:
        raise RuntimeError("Seed is restricted to the enabled development demo")
    with (factory or get_session_factory()).begin() as db:
        # PostgreSQL sequences are not advanced by explicit seed IDs. Serialize seed and
        # ordinary inserts while repairing both sequences, including on repeated seed runs.
        if db.bind.dialect.name == "postgresql":
            db.execute(text("LOCK TABLE users, tenants IN SHARE ROW EXCLUSIVE MODE"))
        if db.get(Tenant, config.demo_tenant_id):
            _advance_sequences(db)
            return  # Do not reactivate revoked installations on repeated seed.
        db.add(Tenant(id=config.demo_tenant_id, name="RepoPilot demo"))
        db.add(User(id=config.demo_user_id, github_user_id=1, login="demo"))
        db.flush()
        db.add(Membership(tenant_id=config.demo_tenant_id, user_id=config.demo_user_id))
        db.add(Installation(id=1001, tenant_id=config.demo_tenant_id, active=True))
        db.flush()
        db.add(Repository(id=2001, tenant_id=config.demo_tenant_id, installation_id=1001,
                          full_name="demo/repopilot-sandbox", enabled=True))
        db.flush()
        _advance_sequences(db)


def _advance_sequences(db):
    if db.bind.dialect.name != "postgresql":
        return
    # Names are fixed constants, never derived from user input. Do not rewind a sequence
    # that is already ahead of stored IDs (for example after rolled-back inserts).
    for table in ("users", "tenants"):
        db.execute(text(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                        f"GREATEST(COALESCE((SELECT MAX(id) FROM {table}), 1), "
                        f"COALESCE(pg_sequence_last_value(pg_get_serial_sequence('{table}', 'id')::regclass), 1)), true)"))


if __name__ == "__main__":
    seed()
