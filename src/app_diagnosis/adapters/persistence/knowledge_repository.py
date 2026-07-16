from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app_diagnosis.adapters.persistence.knowledge_models import KnowledgeEntryRecord
from app_diagnosis.domain.knowledge import KnowledgeEntry, KnowledgeStatus
from app_diagnosis.ports.knowledge_repository import KnowledgeAlreadyExists


class SqlAlchemyKnowledgeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entry: KnowledgeEntry) -> None:
        record = KnowledgeEntryRecord(
            id=entry.id,
            title=entry.title,
            summary=entry.summary,
            error_types_json=list(entry.error_types),
            tags_json=list(entry.tags),
            source=entry.source,
            status=entry.status.value,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
        )
        try:
            async with self._session.begin_nested():
                self._session.add(record)
                await self._session.flush()
        except IntegrityError as error:
            raise KnowledgeAlreadyExists(entry.id) from error

    async def get(self, entry_id: str) -> KnowledgeEntry | None:
        record = await self._session.get(KnowledgeEntryRecord, entry_id)
        return _to_domain(record) if record else None

    async def save(self, entry: KnowledgeEntry) -> None:
        statement = (
            update(KnowledgeEntryRecord)
            .where(KnowledgeEntryRecord.id == entry.id)
            .values(
                title=entry.title,
                summary=entry.summary,
                error_types_json=list(entry.error_types),
                tags_json=list(entry.tags),
                source=entry.source,
                status=entry.status.value,
                updated_at=entry.updated_at,
            )
        )
        result = await self._session.execute(statement)
        if result.rowcount != 1:
            raise LookupError(f"knowledge entry does not exist: {entry.id}")

    async def list_by_status(self, status: KnowledgeStatus) -> tuple[KnowledgeEntry, ...]:
        statement = (
            select(KnowledgeEntryRecord)
            .where(KnowledgeEntryRecord.status == status.value)
            .order_by(KnowledgeEntryRecord.id)
        )
        records = (await self._session.scalars(statement)).all()
        return tuple(_to_domain(record) for record in records)


def _to_domain(record: KnowledgeEntryRecord) -> KnowledgeEntry:
    return KnowledgeEntry(
        id=record.id,
        title=record.title,
        summary=record.summary,
        error_types=tuple(record.error_types_json),
        tags=tuple(record.tags_json),
        source=record.source,
        status=KnowledgeStatus(record.status),
        created_at=_as_utc(record.created_at),
        updated_at=_as_utc(record.updated_at),
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
