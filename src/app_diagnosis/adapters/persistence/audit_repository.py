from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app_diagnosis.adapters.persistence.audit_models import AuditEventRecord
from app_diagnosis.domain.audit import AuditEvent


class SqlAlchemyAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event: AuditEvent) -> None:
        self._session.add(
            AuditEventRecord(
                id=str(event.id),
                actor=event.actor,
                action=event.action,
                target_type=event.target_type,
                target_id=event.target_id,
                summary=event.summary,
                correlation_id=event.correlation_id,
                created_at=event.created_at,
            )
        )
        await self._session.flush()

    async def list_for_target(self, target_type: str, target_id: str) -> tuple[AuditEvent, ...]:
        statement = (
            select(AuditEventRecord)
            .where(
                AuditEventRecord.target_type == target_type,
                AuditEventRecord.target_id == target_id,
            )
            .order_by(AuditEventRecord.created_at, AuditEventRecord.id)
        )
        records = (await self._session.scalars(statement)).all()
        return tuple(
            AuditEvent(
                id=UUID(item.id),
                actor=item.actor,
                action=item.action,
                target_type=item.target_type,
                target_id=item.target_id,
                summary=item.summary,
                correlation_id=item.correlation_id,
                created_at=_as_utc(item.created_at),
            )
            for item in records
        )


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
