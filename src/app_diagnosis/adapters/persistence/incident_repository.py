from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_diagnosis.adapters.persistence.incident_models import IncidentRecord
from app_diagnosis.domain.incident import Incident, IncidentAggregation, IncidentStatus


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class SqlAlchemyIncidentRepository:
    """依靠 aggregation_key 唯一约束实现跨协程的原子聚合。"""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def aggregate(self, candidate: Incident) -> IncidentAggregation:
        async with self._sessions.begin() as session:
            try:
                async with session.begin_nested():
                    session.add(self._record(candidate))
                    await session.flush()
                return IncidentAggregation(candidate, is_novel=True)
            except IntegrityError:
                # 唯一键冲突表示同一时间桶已有 Incident；原子 UPDATE 避免读改写丢失。
                await session.execute(
                    update(IncidentRecord)
                    .where(IncidentRecord.aggregation_key == candidate.aggregation_key)
                    .values(
                        occurrence_count=IncidentRecord.occurrence_count + 1,
                        first_seen_at=func.min(
                            IncidentRecord.first_seen_at, candidate.first_seen_at
                        ),
                        last_seen_at=func.max(
                            IncidentRecord.last_seen_at, candidate.last_seen_at
                        ),
                        updated_at=func.max(IncidentRecord.updated_at, candidate.updated_at),
                    )
                )
                record = await session.scalar(
                    select(IncidentRecord).where(
                        IncidentRecord.aggregation_key == candidate.aggregation_key
                    )
                )
                if record is None:
                    raise RuntimeError(
                        "incident aggregation conflict could not be resolved"
                    ) from None
                return IncidentAggregation(self._domain(record), is_novel=False)

    async def get(self, incident_id: UUID) -> Incident | None:
        async with self._sessions() as session:
            record = await session.get(IncidentRecord, str(incident_id))
        return None if record is None else self._domain(record)

    async def get_by_aggregation_key(self, key: str) -> Incident | None:
        async with self._sessions() as session:
            record = await session.scalar(
                select(IncidentRecord).where(IncidentRecord.aggregation_key == key)
            )
        return None if record is None else self._domain(record)

    async def list(self, *, service_id: UUID | None = None) -> tuple[Incident, ...]:
        statement = select(IncidentRecord).order_by(IncidentRecord.last_seen_at.desc())
        if service_id is not None:
            statement = statement.where(IncidentRecord.service_id == str(service_id))
        async with self._sessions() as session:
            records = (await session.scalars(statement)).all()
        return tuple(self._domain(record) for record in records)

    @staticmethod
    def _record(value: Incident) -> IncidentRecord:
        return IncidentRecord(
            id=str(value.id), service_id=str(value.service_id), environment=value.environment,
            fingerprint=value.fingerprint, fingerprint_version=value.fingerprint_version,
            aggregation_key=value.aggregation_key, status=value.status.value,
            exception_type=value.exception_type, sample_message=value.sample_message,
            occurrence_count=value.occurrence_count, first_seen_at=value.first_seen_at,
            last_seen_at=value.last_seen_at, window_started_at=value.window_started_at,
            window_ends_at=value.window_ends_at, created_at=value.created_at,
            updated_at=value.updated_at,
        )

    @staticmethod
    def _domain(value: IncidentRecord) -> Incident:
        return Incident(
            id=UUID(value.id), service_id=UUID(value.service_id), environment=value.environment,
            fingerprint=value.fingerprint, fingerprint_version=value.fingerprint_version,
            aggregation_key=value.aggregation_key, status=IncidentStatus(value.status),
            exception_type=value.exception_type, sample_message=value.sample_message,
            occurrence_count=value.occurrence_count, first_seen_at=_utc(value.first_seen_at),
            last_seen_at=_utc(value.last_seen_at), window_started_at=_utc(value.window_started_at),
            window_ends_at=_utc(value.window_ends_at), created_at=_utc(value.created_at),
            updated_at=_utc(value.updated_at),
        )
