"""Add externally sourced count authorization and reserved-fee metadata.

The existing simulated-count table remains unchanged; no count or approval is created.
"""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("investigation_provider_token_counts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), nullable=False, unique=True),
        sa.Column("experiment_id", sa.String(36), nullable=False, unique=True),
        sa.Column("investigation_id", sa.String(36), nullable=False),
        sa.Column("snapshot_id", sa.String(36), nullable=False),
        sa.Column("repository_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("source_commit", sa.String(40), nullable=False),
        sa.Column("fixture_id", sa.String(80), nullable=False),
        sa.Column("origin", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("account_sha256", sa.String(64), nullable=False),
        sa.Column("project_sha256", sa.String(64), nullable=False),
        sa.Column("generation_sha256", sa.String(64), nullable=False),
        sa.Column("count_sha256", sa.String(64), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column("binding_sha256", sa.String(64), nullable=False),
        sa.Column("pricing_policy", sa.String(80), nullable=False),
        sa.Column("fee_policy", sa.String(80), nullable=False),
        sa.Column("service_tier", sa.String(24), nullable=False),
        sa.Column("cache_ttl", sa.String(8), nullable=False),
        sa.Column("max_input_tokens", sa.Integer(), nullable=False),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("fee_state", sa.String(16), nullable=False),
        sa.Column("fee_reserved_microusd", sa.BigInteger(), nullable=False),
        sa.Column("fee_accounted_microusd", sa.BigInteger()),
        sa.Column("generation_approval_id", sa.String(36), sa.ForeignKey("investigation_executor_approvals.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("invalidated_at", sa.DateTime(timezone=True)),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["job_id", "investigation_id", "snapshot_id", "repository_id", "tenant_id"],
            ["investigation_report_jobs.id", "investigation_report_jobs.investigation_id",
             "investigation_report_jobs.snapshot_id", "investigation_report_jobs.repository_id",
             "investigation_report_jobs.tenant_id"], name="fk_provider_count_job_owner"),
        sa.ForeignKeyConstraint(["job_id", "experiment_id", "tenant_id"],
            ["investigation_provider_selections.job_id", "investigation_provider_selections.experiment_id",
             "investigation_provider_selections.tenant_id"], name="fk_provider_count_selection"),
        sa.CheckConstraint("origin = 'external' AND provider = 'openai' AND max_input_tokens > 0 AND "
            "max_output_tokens > 0 AND fee_reserved_microusd >= 0 AND "
            "fee_state IN ('reserved', 'known', 'uncertain') AND "
            "((fee_state = 'known' AND fee_accounted_microusd IS NOT NULL AND fee_accounted_microusd >= 0 "
            "AND fee_accounted_microusd <= fee_reserved_microusd) OR "
            "(fee_state <> 'known' AND fee_accounted_microusd IS NULL)) AND "
            "((status = 'pending' AND sent_at IS NULL AND completed_at IS NULL AND input_tokens IS NULL "
            "AND invalidated_at IS NULL AND consumed_at IS NULL AND generation_approval_id IS NULL) OR "
            "(status = 'sent' AND sent_at IS NOT NULL AND completed_at IS NULL AND input_tokens IS NULL "
            "AND invalidated_at IS NULL AND consumed_at IS NULL AND generation_approval_id IS NULL) OR "
            "(status = 'verified' AND sent_at IS NOT NULL AND completed_at IS NOT NULL AND input_tokens IS NOT NULL "
            "AND input_tokens >= 0 AND invalidated_at IS NULL AND consumed_at IS NULL AND generation_approval_id IS NULL) OR "
            "(status = 'uncertain' AND sent_at IS NOT NULL AND completed_at IS NOT NULL AND input_tokens IS NULL "
            "AND invalidated_at IS NULL AND consumed_at IS NULL AND generation_approval_id IS NULL) OR "
            "(status = 'invalid' AND invalidated_at IS NOT NULL AND consumed_at IS NULL AND generation_approval_id IS NULL) OR "
            "(status = 'consumed' AND sent_at IS NOT NULL AND completed_at IS NOT NULL AND input_tokens IS NOT NULL "
            "AND input_tokens >= 0 AND invalidated_at IS NULL AND consumed_at IS NOT NULL AND generation_approval_id IS NOT NULL))",
            name="ck_provider_count_state"))


def downgrade():
    op.drop_table("investigation_provider_token_counts")
