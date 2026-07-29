"""create service profiles

Revision ID: 0010
Revises: 0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "service_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("environment", sa.String(length=64), nullable=False),
        sa.Column("code_workspace_path", sa.Text(), nullable=True),
        sa.Column("log_directory", sa.Text(), nullable=True),
        sa.Column("config_workspace_path", sa.Text(), nullable=True),
        sa.Column("health_targets_json", sa.JSON(), nullable=False),
        sa.Column("tags_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "environment", name="uq_service_profiles_name_env"),
    )
    op.create_index(
        "ix_service_profiles_environment_name",
        "service_profiles",
        ["environment", "name"],
    )
    with op.batch_alter_table("diagnoses") as batch:
        batch.add_column(sa.Column("service_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            "fk_diagnoses_service_id_service_profiles",
            "service_profiles",
            ["service_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("diagnoses") as batch:
        batch.drop_constraint("fk_diagnoses_service_id_service_profiles", type_="foreignkey")
        batch.drop_column("service_id")
    op.drop_index("ix_service_profiles_environment_name", table_name="service_profiles")
    op.drop_table("service_profiles")
