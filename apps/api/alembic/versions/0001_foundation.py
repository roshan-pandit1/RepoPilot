"""Sprint 1 foundation; deliberately independent of live ORM metadata."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table("users", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("github_user_id", sa.BigInteger(), nullable=False, unique=True),
                    sa.Column("login", sa.String(100), nullable=False))
    op.create_table("tenants", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("name", sa.String(200), nullable=False))
    op.create_table("memberships",
                    sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), primary_key=True),
                    sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True))
    op.create_table("installations",
                    sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=False),
                    sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
                    sa.Column("active", sa.Boolean(), nullable=False),
                    sa.UniqueConstraint("id", "tenant_id"))
    op.create_table("repositories",
                    sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=False),
                    sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
                    sa.Column("installation_id", sa.BigInteger(), nullable=False),
                    sa.Column("full_name", sa.String(250), nullable=False),
                    sa.Column("enabled", sa.Boolean(), nullable=False),
                    sa.ForeignKeyConstraint(["installation_id", "tenant_id"],
                                            ["installations.id", "installations.tenant_id"]),
                    sa.UniqueConstraint("id", "tenant_id"))
    op.create_index("ix_repositories_tenant_id", "repositories", ["tenant_id"])
    op.create_table("issues",
                    sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=False),
                    sa.Column("repository_id", sa.BigInteger(), nullable=False),
                    sa.Column("tenant_id", sa.Integer(), nullable=False),
                    sa.Column("number", sa.Integer(), nullable=False),
                    sa.Column("title", sa.String(1024), nullable=False),
                    sa.Column("body", sa.Text()),
                    sa.Column("state", sa.String(10), nullable=False),
                    sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
                    sa.ForeignKeyConstraint(["repository_id", "tenant_id"],
                                            ["repositories.id", "repositories.tenant_id"]),
                    sa.UniqueConstraint("repository_id", "number"),
                    sa.CheckConstraint("number > 0"),
                    sa.CheckConstraint("state IN ('open', 'closed')"))
    op.create_index("ix_issues_repository_id", "issues", ["repository_id"])
    op.create_table("webhook_deliveries",
                    sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("body_hash", sa.String(64), nullable=False),
                    sa.Column("event", sa.String(40), nullable=False),
                    sa.Column("received_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("outbox_events",
                    sa.Column("id", sa.String(36), sa.ForeignKey("webhook_deliveries.id"),
                              primary_key=True),
                    sa.Column("repository_id", sa.BigInteger(), nullable=False),
                    sa.Column("tenant_id", sa.Integer(), nullable=False),
                    sa.Column("payload", sa.JSON(), nullable=False),
                    sa.Column("status", sa.String(20), nullable=False),
                    sa.Column("attempts", sa.Integer(), nullable=False),
                    sa.Column("next_dispatch_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("processed_at", sa.DateTime(timezone=True)),
                    sa.ForeignKeyConstraint(["repository_id", "tenant_id"],
                                            ["repositories.id", "repositories.tenant_id"]),
                    sa.CheckConstraint("status IN ('pending', 'processed', 'ignored', 'failed')"))
    op.create_index("ix_outbox_events_status", "outbox_events", ["status"])


def downgrade():
    for table in ("outbox_events", "webhook_deliveries", "issues", "repositories", "installations",
                  "memberships", "users", "tenants"):
        op.drop_table(table)
    # Extension may be shared by other consumers: do not remove it.
