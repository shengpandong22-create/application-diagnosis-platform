"""create agent and tool execution records

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("diagnosis_id", sa.String(length=36), nullable=False),
        sa.Column("strategy", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("termination_reason", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=200), nullable=True),
        sa.Column("round_count", sa.Integer(), nullable=False),
        sa.Column("tool_call_count", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'cancelled')",
            name="ck_agent_runs_status",
        ),
        sa.ForeignKeyConstraint(["diagnosis_id"], ["diagnoses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_runs_diagnosis_started", "agent_runs", ["diagnosis_id", "started_at"])
    op.create_table(
        "tool_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("agent_run_id", sa.String(length=36), nullable=False),
        sa.Column("tool_call_id", sa.String(length=200), nullable=False),
        sa.Column("tool_name", sa.String(length=64), nullable=False),
        sa.Column("arguments_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('success', 'failed', 'timeout', 'cancelled')",
            name="ck_tool_runs_status",
        ),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_run_id", "tool_call_id", name="uq_tool_runs_call"),
    )
    op.create_index("ix_tool_runs_agent_created", "tool_runs", ["agent_run_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_tool_runs_agent_created", table_name="tool_runs")
    op.drop_table("tool_runs")
    op.drop_index("ix_agent_runs_diagnosis_started", table_name="agent_runs")
    op.drop_table("agent_runs")
