from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app_diagnosis.adapters.persistence.models import Base


class IncidentRecord(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'resolved')", name="ck_incidents_status"),
        CheckConstraint("occurrence_count >= 1", name="ck_incidents_occurrence_positive"),
        Index("uq_incidents_aggregation_key", "aggregation_key", unique=True),
        Index("ix_incidents_service_last_seen", "service_id", "last_seen_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    service_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("service_profiles.id", ondelete="CASCADE"), nullable=False
    )
    environment: Mapped[str] = mapped_column(String(64), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    fingerprint_version: Mapped[str] = mapped_column(String(32), nullable=False)
    aggregation_key: Mapped[str] = mapped_column(String(300), nullable=False)
    diagnosis_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("diagnoses.id", ondelete="SET NULL"), unique=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    exception_type: Mapped[str] = mapped_column(String(300), nullable=False)
    sample_message: Mapped[str] = mapped_column(Text, nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DeduplicationKeyRecord(Base):
    __tablename__ = "deduplication_keys"

    key: Mapped[str] = mapped_column(String(300), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
