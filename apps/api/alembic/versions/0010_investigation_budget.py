"""Add isolated real-provider experiment, reservation, and report records."""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("investigation_experiments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("budget_microusd", sa.BigInteger(), nullable=False),
        sa.Column("investigation_budget_microusd", sa.BigInteger(), nullable=False),
        sa.Column("max_input_tokens", sa.Integer(), nullable=False),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False),
        sa.Column("max_concurrent", sa.Integer(), nullable=False),
        sa.Column("max_requests", sa.Integer(), nullable=False),
        sa.Column("pricing_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "tenant_id", name="uq_experiment_tenant"),
        sa.CheckConstraint("mode IN ('actual', 'simulated') AND provider = 'openai' AND "
            "budget_microusd > 0 AND investigation_budget_microusd > 0 AND max_input_tokens > 0 AND "
            "max_output_tokens > 0 AND max_concurrent > 0 AND max_requests > 0", name="ck_experiment_limits"))
    op.create_table("investigation_provider_selections",
        sa.Column("job_id", sa.String(36), primary_key=True),
        sa.Column("repository_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("experiment_id", sa.String(36), nullable=False),
        sa.ForeignKeyConstraint(["job_id", "repository_id", "tenant_id"],
            ["investigation_report_jobs.id", "investigation_report_jobs.repository_id", "investigation_report_jobs.tenant_id"], name="fk_provider_selection_job"),
        sa.ForeignKeyConstraint(["experiment_id", "tenant_id"],
            ["investigation_experiments.id", "investigation_experiments.tenant_id"], name="fk_provider_selection_experiment"),
        sa.UniqueConstraint("job_id", "experiment_id", "tenant_id", name="uq_provider_selection_experiment"))
    op.create_table("investigation_usage_reservations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), nullable=False, unique=True),
        sa.Column("experiment_id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("repository_id", sa.BigInteger(), nullable=False),
        sa.Column("investigation_id", sa.String(36), nullable=False),
        sa.Column("snapshot_id", sa.String(36), nullable=False),
        sa.Column("lease_token", sa.String(36), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("reserved_microusd", sa.BigInteger(), nullable=False),
        sa.Column("max_input_tokens", sa.Integer(), nullable=False),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("pricing_policy", sa.String(80), nullable=False),
        sa.Column("input_rate_tenths", sa.Integer(), nullable=False),
        sa.Column("output_rate_tenths", sa.Integer(), nullable=False),
        sa.Column("accounted_microusd", sa.BigInteger()),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["experiment_id", "tenant_id"],
            ["investigation_experiments.id", "investigation_experiments.tenant_id"], name="fk_usage_experiment"),
        sa.ForeignKeyConstraint(["job_id", "investigation_id", "snapshot_id", "repository_id", "tenant_id"],
            ["investigation_report_jobs.id", "investigation_report_jobs.investigation_id", "investigation_report_jobs.snapshot_id", "investigation_report_jobs.repository_id", "investigation_report_jobs.tenant_id"], name="fk_usage_job"),
        sa.ForeignKeyConstraint(["job_id", "experiment_id", "tenant_id"],
            ["investigation_provider_selections.job_id", "investigation_provider_selections.experiment_id",
             "investigation_provider_selections.tenant_id"], name="fk_usage_selection"),
        sa.CheckConstraint("state IN ('reserved', 'sent', 'known', 'uncertain') AND "
            "mode IN ('actual', 'simulated') AND reserved_microusd > 0 AND max_input_tokens > 0 AND max_output_tokens > 0 AND input_rate_tenths > 0 AND output_rate_tenths > 0 AND "
            "(accounted_microusd IS NULL OR accounted_microusd >= 0) AND "
            "(input_tokens IS NULL OR input_tokens >= 0) AND (output_tokens IS NULL OR output_tokens >= 0) AND "
            "((state = 'known' AND accounted_microusd IS NOT NULL AND accounted_microusd <= reserved_microusd "
            "AND input_tokens IS NOT NULL AND output_tokens IS NOT NULL) OR "
            "(state <> 'known' AND accounted_microusd IS NULL AND input_tokens IS NULL AND output_tokens IS NULL))", name="ck_usage_reservation"))
    op.create_index("ix_usage_experiment", "investigation_usage_reservations", ["experiment_id", "investigation_id"])
    op.create_table("investigation_real_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("report_job_id", sa.String(36), nullable=False, unique=True),
        sa.Column("investigation_id", sa.String(36), nullable=False, unique=True),
        sa.Column("snapshot_id", sa.String(36), nullable=False),
        sa.Column("repository_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("commit_sha", sa.String(40), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("cost_microusd", sa.BigInteger()),
        sa.Column("input_truncated", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["report_job_id", "investigation_id", "snapshot_id", "repository_id", "tenant_id"],
            ["investigation_report_jobs.id", "investigation_report_jobs.investigation_id", "investigation_report_jobs.snapshot_id", "investigation_report_jobs.repository_id", "investigation_report_jobs.tenant_id"], name="fk_real_report_job_full_owner"),
        sa.ForeignKeyConstraint(["report_job_id"], ["investigation_provider_selections.job_id"], name="fk_real_report_selection"),
        sa.CheckConstraint("provider = 'openai' AND model = 'gpt-5.6-terra'", name="ck_real_report_provider"))


def downgrade():
    op.drop_table("investigation_real_reports")
    op.drop_index("ix_usage_experiment", table_name="investigation_usage_reservations")
    op.drop_table("investigation_usage_reservations")
    op.drop_table("investigation_provider_selections")
    op.drop_table("investigation_experiments")
