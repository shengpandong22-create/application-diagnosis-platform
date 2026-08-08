"""create incidents and deduplication keys

Revision ID: 0011
Revises: 0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("service_id", sa.String(36), nullable=False),
        sa.Column("environment", sa.String(64), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("fingerprint_version", sa.String(32), nullable=False),
        sa.Column("aggregation_key", sa.String(300), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("exception_type", sa.String(300), nullable=False),
        sa.Column("sample_message", sa.Text(), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('open', 'resolved')", name="ck_incidents_status"),
        sa.CheckConstraint("occurrence_count >= 1", name="ck_incidents_occurrence_positive"),
        sa.ForeignKeyConstraint(["service_id"], ["service_profiles.id"], ondelete="CASCADE"),
    )
    op.create_index("uq_incidents_aggregation_key", "incidents", ["aggregation_key"], unique=True)
    op.create_index("ix_incidents_service_last_seen", "incidents", ["service_id", "last_seen_at"])
    op.create_table(
        "deduplication_keys",
        sa.Column("key", sa.String(300), primary_key=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("deduplication_keys")
    op.drop_index("ix_incidents_service_last_seen", table_name="incidents")
    op.drop_index("uq_incidents_aggregation_key", table_name="incidents")
    op.drop_table("incidents")
