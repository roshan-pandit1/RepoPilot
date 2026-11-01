"""Add one-use, request-bound executor approval records."""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("investigation_executor_approvals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), nullable=False, unique=True),
        sa.Column("experiment_id", sa.String(36), nullable=False, unique=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.String(36), nullable=False),
        sa.Column("source_commit", sa.String(40), nullable=False),
        sa.Column("fixture_id", sa.String(80), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("request_sha256", sa.String(64), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["job_id", "experiment_id", "tenant_id"],
            ["investigation_provider_selections.job_id", "investigation_provider_selections.experiment_id",
             "investigation_provider_selections.tenant_id"], name="fk_executor_approval_selection"),
        sa.CheckConstraint("state IN ('ready', 'consumed') AND mode IN ('simulated', 'actual') AND provider = 'openai' AND "
            "((state = 'ready' AND consumed_at IS NULL) OR (state = 'consumed' AND consumed_at IS NOT NULL))",
            name="ck_executor_approval_state"))


def downgrade():
    op.drop_table("investigation_executor_approvals")
