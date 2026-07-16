"""create knowledge entries

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_entries",
        sa.Column("id", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("error_types_json", sa.JSON(), nullable=False),
        sa.Column("tags_json", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('candidate', 'confirmed', 'retired')", name="ck_knowledge_status"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_status_updated", "knowledge_entries", ["status", "updated_at"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_status_updated", table_name="knowledge_entries")
    op.drop_table("knowledge_entries")
