"""create evidence records

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evidence",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("diagnosis_id", sa.String(length=36), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_reference", sa.String(length=500), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("reliability", sa.String(length=16), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("redaction_status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "type IN ('user_statement', 'log_excerpt', 'knowledge_entry')",
            name="ck_evidence_type",
        ),
        sa.CheckConstraint(
            "source IN ('user_input', 'local_knowledge')", name="ck_evidence_source"
        ),
        sa.CheckConstraint(
            "reliability IN ('low', 'medium', 'high')", name="ck_evidence_reliability"
        ),
        sa.CheckConstraint(
            "redaction_status IN ('not_required', 'redacted', 'rejected')",
            name="ck_evidence_redaction_status",
        ),
        sa.ForeignKeyConstraint(["diagnosis_id"], ["diagnoses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("diagnosis_id", "content_hash", name="uq_evidence_diagnosis_hash"),
    )
    op.create_index("ix_evidence_diagnosis_created", "evidence", ["diagnosis_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_evidence_diagnosis_created", table_name="evidence")
    op.drop_table("evidence")
