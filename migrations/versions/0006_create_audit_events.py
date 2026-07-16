"""create audit events

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("actor", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("target_id", sa.String(length=100), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_target_created",
        "audit_events",
        ["target_type", "target_id", "created_at"],
    )
    op.create_index("ix_audit_action_created", "audit_events", ["action", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_action_created", table_name="audit_events")
    op.drop_index("ix_audit_target_created", table_name="audit_events")
    op.drop_table("audit_events")
