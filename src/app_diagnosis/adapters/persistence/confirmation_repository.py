from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app_diagnosis.adapters.persistence.confirmation_models import ConfirmationRecord
from app_diagnosis.domain.confirmation import Confirmation, ConfirmationAction


class SqlAlchemyConfirmationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, confirmation: Confirmation) -> None:
        self._session.add(
            ConfirmationRecord(
                id=str(confirmation.id),
                diagnosis_id=str(confirmation.diagnosis_id),
                action=confirmation.action.value,
                actor=confirmation.actor,
                comment=confirmation.comment,
                created_at=confirmation.created_at,
            )
        )
        await self._session.flush()

    async def list_by_diagnosis(self, diagnosis_id: UUID) -> tuple[Confirmation, ...]:
        statement = (
            select(ConfirmationRecord)
            .where(ConfirmationRecord.diagnosis_id == str(diagnosis_id))
            .order_by(ConfirmationRecord.created_at, ConfirmationRecord.id)
        )
        records = (await self._session.scalars(statement)).all()
        return tuple(
            Confirmation(
                id=UUID(item.id),
                diagnosis_id=UUID(item.diagnosis_id),
                action=ConfirmationAction(item.action),
                actor=item.actor,
                comment=item.comment,
                created_at=_as_utc(item.created_at),
            )
            for item in records
        )


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
