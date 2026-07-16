"""create confirmation records

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "confirmations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("diagnosis_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("actor", sa.String(length=100), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "action IN ('confirm', 'reject', 'continue_investigation')",
            name="ck_confirmations_action",
        ),
        sa.ForeignKeyConstraint(["diagnosis_id"], ["diagnoses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_confirmations_diagnosis_created", "confirmations", ["diagnosis_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_confirmations_diagnosis_created", table_name="confirmations")
    op.drop_table("confirmations")
