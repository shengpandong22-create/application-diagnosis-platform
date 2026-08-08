from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app_diagnosis.adapters.persistence.models import Base


class EvaluationCandidateRecord(Base):
    __tablename__ = "evaluation_candidates"
    __table_args__ = (
        UniqueConstraint("diagnosis_id", name="uq_evaluation_candidates_diagnosis"),
        CheckConstraint(
            "status IN ('candidate', 'labeled', 'promoted')",
            name="ck_evaluation_candidates_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    diagnosis_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("diagnoses.id", ondelete="CASCADE"), nullable=False
    )
    source_action: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    feedback_summary: Mapped[str | None] = mapped_column(Text)
    expected_category: Mapped[str | None] = mapped_column(String(100))
    expected_root_cause: Mapped[str | None] = mapped_column(Text)
    required_evidence_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
