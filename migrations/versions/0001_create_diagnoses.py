"""create diagnoses table

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "diagnoses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("problem_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("symptom", sa.Text(), nullable=False),
        sa.Column("submitted_log", sa.Text(), nullable=True),
        sa.Column("conclusion_json", sa.JSON(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "problem_type IN ('generic_application_error')",
            name="ck_diagnoses_problem_type",
        ),
        sa.CheckConstraint(
            "status IN ('created', 'investigating', 'waiting_for_input', "
            "'waiting_for_confirmation', 'confirmed', 'rejected', 'inconclusive', "
            "'cancelled')",
            name="ck_diagnoses_status",
        ),
        sa.CheckConstraint("version >= 0", name="ck_diagnoses_version_non_negative"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_diagnoses_status_created_at",
        "diagnoses",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_diagnoses_status_created_at", table_name="diagnoses")
    op.drop_table("diagnoses")
