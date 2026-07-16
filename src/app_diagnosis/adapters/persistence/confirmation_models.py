from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app_diagnosis.adapters.persistence.models import Base


class ConfirmationRecord(Base):
    __tablename__ = "confirmations"
    __table_args__ = (
        CheckConstraint(
            "action IN ('confirm', 'reject', 'continue_investigation')",
            name="ck_confirmations_action",
        ),
        Index("ix_confirmations_diagnosis_created", "diagnosis_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    diagnosis_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("diagnoses.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
