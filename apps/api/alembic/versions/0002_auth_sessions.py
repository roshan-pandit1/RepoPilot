"""Add browser-bound OAuth attempts and encrypted server-side sessions."""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "installation_guards",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "repository_guards",
        sa.Column("installation_id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("repository_id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "oauth_attempts",
        sa.Column("state_hash", sa.String(64), primary_key=True),
        sa.Column("verifier_ciphertext", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "personal_tenants",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, unique=True),
        sa.ForeignKeyConstraint(["tenant_id", "user_id"],
                                ["memberships.tenant_id", "memberships.user_id"]),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("github_token_ciphertext", sa.Text(), nullable=False),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["tenant_id", "user_id"],
                                ["memberships.tenant_id", "memberships.user_id"]),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_table(
        "sync_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("repository_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("session_hash", sa.String(64), sa.ForeignKey("auth_sessions.id_hash"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_dispatch_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["repository_id", "tenant_id"],
                                ["repositories.id", "repositories.tenant_id"]),
        sa.CheckConstraint("status IN ('pending', 'processed', 'partial', 'ignored', 'failed')"),
    )
    op.create_index("ix_sync_jobs_status", "sync_jobs", ["status"])


def downgrade():
    op.drop_table("sync_jobs")
    op.drop_table("auth_sessions")
    op.drop_table("oauth_attempts")
    op.drop_table("personal_tenants")
    op.drop_table("repository_guards")
    op.drop_table("installation_guards")
