from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app_diagnosis.adapters.persistence.models import Base


class KnowledgeEntryRecord(Base):
    __tablename__ = "knowledge_entries"
    __table_args__ = (
        CheckConstraint(
            "status IN ('candidate', 'confirmed', 'retired')", name="ck_knowledge_status"
        ),
        Index("ix_knowledge_status_updated", "status", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    error_types_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    tags_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
