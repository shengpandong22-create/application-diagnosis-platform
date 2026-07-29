from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class DiagnosisRecord(Base):
    __tablename__ = "diagnoses"
    __table_args__ = (
        CheckConstraint("version >= 0", name="ck_diagnoses_version_non_negative"),
        CheckConstraint(
            "status IN ('created', 'investigating', 'waiting_for_input', "
            "'waiting_for_confirmation', 'confirmed', 'rejected', 'inconclusive', "
            "'cancelled')",
            name="ck_diagnoses_status",
        ),
        CheckConstraint(
            "problem_type IN ('generic_application_error')",
            name="ck_diagnoses_problem_type",
        ),
        Index("ix_diagnoses_status_created_at", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    service_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("service_profiles.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    problem_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    symptom: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_log: Mapped[str | None] = mapped_column(Text)
    conclusion_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AgentRunRecord(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'cancelled')",
            name="ck_agent_runs_status",
        ),
        Index("ix_agent_runs_diagnosis_started", "diagnosis_id", "started_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    diagnosis_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("diagnoses.id", ondelete="CASCADE"), nullable=False
    )
    strategy: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    termination_reason: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(200))
    round_count: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_call_count: Mapped[int] = mapped_column(Integer, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))


class ToolRunRecord(Base):
    __tablename__ = "tool_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('success', 'failed', 'timeout', 'cancelled')",
            name="ck_tool_runs_status",
        ),
        UniqueConstraint("agent_run_id", "tool_call_id", name="uq_tool_runs_call"),
        Index("ix_tool_runs_agent_created", "agent_run_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    agent_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    tool_call_id: Mapped[str] = mapped_column(String(200), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    arguments_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DiagnosisPlanRecord(Base):
    __tablename__ = "diagnosis_plans"
    __table_args__ = (
        CheckConstraint("status IN ('planned')", name="ck_diagnosis_plans_status"),
        UniqueConstraint("agent_run_id", name="uq_diagnosis_plans_agent_run"),
        Index("ix_diagnosis_plans_diagnosis_created", "diagnosis_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    diagnosis_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("diagnoses.id", ondelete="CASCADE"), nullable=False
    )
    agent_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    hypotheses_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    steps_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    expected_evidence_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    allowed_tools_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ServiceProfileRecord(Base):
    __tablename__ = "service_profiles"
    __table_args__ = (
        UniqueConstraint("name", "environment", name="uq_service_profiles_name_env"),
        Index("ix_service_profiles_environment_name", "environment", "name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    environment: Mapped[str] = mapped_column(String(64), nullable=False)
    code_workspace_path: Mapped[str | None] = mapped_column(Text)
    log_directory: Mapped[str | None] = mapped_column(Text)
    config_workspace_path: Mapped[str | None] = mapped_column(Text)
    health_targets_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    tags_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
