"""add phase 2 evidence values

Revision ID: 0008
Revises: 0007
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("evidence") as batch:
        batch.drop_constraint("ck_evidence_type", type_="check")
        batch.drop_constraint("ck_evidence_source", type_="check")
        batch.create_check_constraint(
            "ck_evidence_type",
            "type IN ('user_statement', 'log_excerpt', 'knowledge_entry', 'code_excerpt', "
            "'config_excerpt', 'health_check')",
        )
        batch.create_check_constraint(
            "ck_evidence_source",
            "source IN ('user_input', 'local_knowledge', 'local_code', 'local_config', "
            "'local_log', 'local_service')",
        )


def downgrade() -> None:
    with op.batch_alter_table("evidence") as batch:
        batch.drop_constraint("ck_evidence_type", type_="check")
        batch.drop_constraint("ck_evidence_source", type_="check")
        batch.create_check_constraint(
            "ck_evidence_type",
            "type IN ('user_statement', 'log_excerpt', 'knowledge_entry', 'code_excerpt')",
        )
        batch.create_check_constraint(
            "ck_evidence_source", "source IN ('user_input', 'local_knowledge', 'local_code')"
        )
