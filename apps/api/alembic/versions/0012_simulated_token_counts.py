"""Add fake-only, one-use input-token counting records."""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("investigation_token_counts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), nullable=False, unique=True),
        sa.Column("experiment_id", sa.String(36), nullable=False, unique=True),
        sa.Column("investigation_id", sa.String(36), nullable=False),
        sa.Column("snapshot_id", sa.String(36), nullable=False),
        sa.Column("repository_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("source_commit", sa.String(40), nullable=False),
        sa.Column("fixture_id", sa.String(80), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("account_sha256", sa.String(64), nullable=False),
        sa.Column("project_sha256", sa.String(64), nullable=False),
        sa.Column("generation_sha256", sa.String(64), nullable=False),
        sa.Column("count_sha256", sa.String(64), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column("binding_sha256", sa.String(64), nullable=False),
        sa.Column("pricing_policy", sa.String(80), nullable=False),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False),
        sa.Column("max_input_tokens", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("invalidated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["job_id", "investigation_id", "snapshot_id", "repository_id", "tenant_id"],
            ["investigation_report_jobs.id", "investigation_report_jobs.investigation_id",
             "investigation_report_jobs.snapshot_id", "investigation_report_jobs.repository_id",
             "investigation_report_jobs.tenant_id"], name="fk_token_count_job_owner"),
        sa.ForeignKeyConstraint(["job_id", "experiment_id", "tenant_id"],
            ["investigation_provider_selections.job_id", "investigation_provider_selections.experiment_id",
             "investigation_provider_selections.tenant_id"], name="fk_token_count_selection"),
        sa.CheckConstraint("mode = 'simulated' AND provider = 'openai' AND max_input_tokens > 0 AND "
            "max_output_tokens > 0 AND status IN ('ready', 'sent', 'complete', 'uncertain') AND "
            "((status = 'ready' AND sent_at IS NULL AND completed_at IS NULL AND input_tokens IS NULL) OR "
            "(status = 'sent' AND sent_at IS NOT NULL AND completed_at IS NULL AND input_tokens IS NULL) OR "
            "(status = 'complete' AND sent_at IS NOT NULL AND completed_at IS NOT NULL AND input_tokens IS NOT NULL AND input_tokens >= 0) OR "
            "(status = 'uncertain' AND sent_at IS NOT NULL AND completed_at IS NOT NULL AND input_tokens IS NULL))",
            name="ck_token_count_state"))


def downgrade():
    op.drop_table("investigation_token_counts")
