"""Record new snapshot publications and finalized evidence manifests without backfill."""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("snapshot_publications",
        sa.Column("snapshot_id", sa.String(36), primary_key=True),
        sa.Column("repository_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("commit_sha", sa.String(40), nullable=False),
        sa.Column("file_count", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revocation_reason", sa.String(40)),
        sa.ForeignKeyConstraint(["snapshot_id", "repository_id", "tenant_id"],
            ["code_snapshots.id", "code_snapshots.repository_id", "code_snapshots.tenant_id"],
            name="fk_snapshot_publication_owner"),
        sa.CheckConstraint("(revoked_at IS NULL AND revocation_reason IS NULL) OR "
            "(revoked_at IS NOT NULL AND revocation_reason IS NOT NULL AND revocation_reason IN ('security', 'integrity'))",
            name="ck_snapshot_publication_revocation"))
    op.create_table("investigation_evidence_manifests",
        sa.Column("job_id", sa.String(36), primary_key=True),
        sa.Column("snapshot_id", sa.String(36), nullable=False),
        sa.Column("repository_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("commit_sha", sa.String(40), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("version", sa.String(30), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id", "snapshot_id", "repository_id", "tenant_id"],
            ["investigation_jobs.id", "investigation_jobs.snapshot_id", "investigation_jobs.repository_id", "investigation_jobs.tenant_id"],
            name="fk_evidence_manifest_owner"),
        sa.CheckConstraint("evidence_count BETWEEN 0 AND 30", name="ck_evidence_manifest_count"),
        sa.CheckConstraint("version = 'evidence-v1'", name="ck_evidence_manifest_version"))


def downgrade():
    op.drop_table("investigation_evidence_manifests")
    op.drop_table("snapshot_publications")
