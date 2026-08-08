"""create evaluation candidates

Revision ID: 0013
Revises: 0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evaluation_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("diagnosis_id", sa.String(36), nullable=False),
        sa.Column("source_action", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("feedback_summary", sa.Text()),
        sa.Column("expected_category", sa.String(100)),
        sa.Column("expected_root_cause", sa.Text()),
        sa.Column("required_evidence_ids_json", sa.JSON(), nullable=False),
        sa.Column("prompt_version", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('candidate', 'labeled', 'promoted')",
            name="ck_evaluation_candidates_status",
        ),
        sa.ForeignKeyConstraint(["diagnosis_id"], ["diagnoses.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("diagnosis_id", name="uq_evaluation_candidates_diagnosis"),
    )


def downgrade() -> None:
    op.drop_table("evaluation_candidates")
