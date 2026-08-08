"""link incidents to diagnoses

Revision ID: 0012
Revises: 0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("incidents") as batch:
        batch.add_column(sa.Column("diagnosis_id", sa.String(36), nullable=True))
        batch.create_unique_constraint("uq_incidents_diagnosis_id", ["diagnosis_id"])
        batch.create_foreign_key(
            "fk_incidents_diagnosis_id_diagnoses",
            "diagnoses",
            ["diagnosis_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("incidents") as batch:
        batch.drop_constraint("fk_incidents_diagnosis_id_diagnoses", type_="foreignkey")
        batch.drop_constraint("uq_incidents_diagnosis_id", type_="unique")
        batch.drop_column("diagnosis_id")
