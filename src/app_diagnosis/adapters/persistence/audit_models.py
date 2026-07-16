from datetime import datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app_diagnosis.adapters.persistence.models import Base


class AuditEventRecord(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_target_created", "target_type", "target_id", "created_at"),
        Index("ix_audit_action_created", "action", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
