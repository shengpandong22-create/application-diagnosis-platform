from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app_diagnosis.adapters.persistence.models import Base


class EvidenceRecord(Base):
    __tablename__ = "evidence"
    __table_args__ = (
        CheckConstraint(
            "type IN ('user_statement', 'log_excerpt', 'knowledge_entry')", name="ck_evidence_type"
        ),
        CheckConstraint("source IN ('user_input', 'local_knowledge')", name="ck_evidence_source"),
        CheckConstraint("reliability IN ('low', 'medium', 'high')", name="ck_evidence_reliability"),
        CheckConstraint(
            "redaction_status IN ('not_required', 'redacted', 'rejected')",
            name="ck_evidence_redaction_status",
        ),
        UniqueConstraint("diagnosis_id", "content_hash", name="uq_evidence_diagnosis_hash"),
        Index("ix_evidence_diagnosis_created", "diagnosis_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    diagnosis_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("diagnoses.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reliability: Mapped[str] = mapped_column(String(16), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    redaction_status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
