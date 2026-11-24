"""Record explicitly scoped partial inventories and verified upstream issue identity."""
from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("code_snapshots") as batch:
        batch.add_column(sa.Column("inventory_coverage", sa.String(24), nullable=False, server_default="UNKNOWN_INVENTORY"))
        batch.add_column(sa.Column("inventory_manifest", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("inventory_manifest_sha256", sa.String(64), nullable=True))
        batch.create_unique_constraint("uq_snapshot_inventory_owner", ["id", "repository_id", "tenant_id", "inventory_manifest_sha256"])
        batch.create_check_constraint("ck_snapshot_inventory_coverage", "((inventory_coverage = 'PARTIAL_INVENTORY' AND published = false) OR inventory_coverage = 'COMPLETE_INVENTORY') AND inventory_manifest IS NOT NULL AND inventory_manifest_sha256 IS NOT NULL AND length(inventory_manifest_sha256) = 64 OR (inventory_coverage = 'UNKNOWN_INVENTORY' AND inventory_manifest IS NULL AND inventory_manifest_sha256 IS NULL)")
    # SQLite batch recreation must explicitly preserve pre-existing unnamed checks.
    with op.batch_alter_table("investigation_jobs", table_args=(
            sa.CheckConstraint("issue_number > 0 AND issue_id > 0 AND attempts >= 0"),
            sa.CheckConstraint("status IN ('queued', 'running', 'completed', 'failed', 'cancelled')"),
    )) as batch:
        batch.add_column(sa.Column("issue_origin_repository_id", sa.BigInteger(), nullable=True))
        batch.create_unique_constraint("uq_investigation_origin_owner", ["id", "repository_id", "tenant_id", "issue_id", "issue_number", "issue_origin_repository_id"])
    op.drop_index("uq_investigation_active", table_name="investigation_jobs")
    op.create_index("uq_investigation_active", "investigation_jobs", ["tenant_id", "user_id", "repository_id", sa.text("coalesce(issue_origin_repository_id, repository_id)"), "issue_number"], unique=True, postgresql_where=sa.text("status IN ('queued', 'running')"), sqlite_where=sa.text("status IN ('queued', 'running')"))
    op.create_table("investigation_issue_origins",
        sa.Column("job_id", sa.String(36), primary_key=True),
        sa.Column("repository_id", sa.BigInteger(), nullable=False), sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("origin_repository_id", sa.BigInteger(), nullable=False), sa.Column("origin_repository_name", sa.String(250), nullable=False),
        sa.Column("issue_id", sa.BigInteger(), nullable=False), sa.Column("issue_number", sa.Integer(), nullable=False),
        sa.Column("issue_url", sa.String(512), nullable=False), sa.Column("issue_title", sa.String(1024), nullable=False),
        sa.Column("issue_body_sha256", sa.String(64), nullable=False), sa.Column("issue_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False), sa.Column("relationship", sa.String(30), nullable=False),
        sa.ForeignKeyConstraint(["job_id", "repository_id", "tenant_id", "issue_id", "issue_number", "origin_repository_id"],
            ["investigation_jobs.id", "investigation_jobs.repository_id", "investigation_jobs.tenant_id", "investigation_jobs.issue_id", "investigation_jobs.issue_number", "investigation_jobs.issue_origin_repository_id"], name="fk_investigation_issue_origin_owner"),
        sa.CheckConstraint("relationship = 'direct_public_parent' AND origin_repository_id > 0 AND issue_id > 0 AND issue_number > 0 AND length(issue_body_sha256) = 64", name="ck_investigation_issue_origin_identity"))
    op.create_table("partial_snapshot_scopes",
        sa.Column("job_id", sa.String(36), primary_key=True), sa.Column("snapshot_id", sa.String(36), nullable=False, unique=True),
        sa.Column("repository_id", sa.BigInteger(), nullable=False), sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["job_id", "snapshot_id", "repository_id", "tenant_id"],
            ["investigation_jobs.id", "investigation_jobs.snapshot_id", "investigation_jobs.repository_id", "investigation_jobs.tenant_id"], name="fk_partial_scope_investigation_owner"),
        sa.ForeignKeyConstraint(["snapshot_id", "repository_id", "tenant_id", "manifest_sha256"],
            ["code_snapshots.id", "code_snapshots.repository_id", "code_snapshots.tenant_id", "code_snapshots.inventory_manifest_sha256"], name="fk_partial_scope_inventory_owner"),
        sa.CheckConstraint("length(manifest_sha256) = 64", name="ck_partial_scope_manifest_sha256"))


def downgrade():
    op.drop_table("partial_snapshot_scopes")
    op.drop_table("investigation_issue_origins")
    op.drop_index("uq_investigation_active", table_name="investigation_jobs")
    op.create_index("uq_investigation_active", "investigation_jobs", ["tenant_id", "user_id", "repository_id", "issue_number"], unique=True, postgresql_where=sa.text("status IN ('queued', 'running')"), sqlite_where=sa.text("status IN ('queued', 'running')"))
    with op.batch_alter_table("investigation_jobs") as batch:
        batch.drop_constraint("uq_investigation_origin_owner", type_="unique")
        batch.drop_column("issue_origin_repository_id")
    with op.batch_alter_table("code_snapshots") as batch:
        batch.drop_constraint("ck_snapshot_inventory_coverage", type_="check")
        batch.drop_constraint("uq_snapshot_inventory_owner", type_="unique")
        batch.drop_column("inventory_manifest_sha256")
        batch.drop_column("inventory_manifest")
        batch.drop_column("inventory_coverage")
