from app.domain.models import Tenant, User


def test_generated_ids_do_not_collide_with_seed(factory):
    """The demo's explicit IDs must not collide with later GitHub users and tenants."""
    with factory.begin() as db:
        user = User(github_user_id=98765, login="sequence-test")
        tenant = Tenant(name="sequence-test")
        db.add_all([user, tenant])
        db.flush()
        assert user.id != 1
        assert tenant.id != 1


def test_repeated_seed_does_not_rewind_postgres_sequences(factory):
    import pytest
    from sqlalchemy import text
    from app.seed import seed

    if factory.kw["bind"].dialect.name != "postgresql":
        pytest.skip("PostgreSQL sequences are required")
    with factory.begin() as db:
        before = db.scalar(text("SELECT nextval(pg_get_serial_sequence('users', 'id'))"))
    seed(factory)
    with factory.begin() as db:
        after = db.scalar(text("SELECT nextval(pg_get_serial_sequence('users', 'id'))"))
    assert after > before
