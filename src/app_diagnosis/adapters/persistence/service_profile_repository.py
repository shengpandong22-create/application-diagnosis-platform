from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_diagnosis.adapters.persistence.models import ServiceProfileRecord
from app_diagnosis.domain.service_profile import ServiceProfile


class ServiceProfileAlreadyExists(ValueError):
    pass


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class SqlAlchemyServiceProfileRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add(self, service: ServiceProfile) -> None:
        async with self._session_factory.begin() as session:
            try:
                async with session.begin_nested():
                    session.add(self._to_record(service))
                    await session.flush()
            except IntegrityError as error:
                raise ServiceProfileAlreadyExists(
                    f"service already exists: {service.name}/{service.environment}"
                ) from error

    async def get(self, service_id: UUID) -> ServiceProfile | None:
        async with self._session_factory() as session:
            record = await session.get(ServiceProfileRecord, str(service_id))
        return None if record is None else self._to_domain(record)

    async def list(self) -> tuple[ServiceProfile, ...]:
        async with self._session_factory() as session:
            records = (
                await session.scalars(
                    select(ServiceProfileRecord).order_by(
                        ServiceProfileRecord.environment,
                        ServiceProfileRecord.name,
                    )
                )
            ).all()
        return tuple(self._to_domain(record) for record in records)

    @staticmethod
    def _to_record(service: ServiceProfile) -> ServiceProfileRecord:
        return ServiceProfileRecord(
            id=str(service.id),
            name=service.name,
            description=service.description,
            environment=service.environment,
            code_workspace_path=service.code_workspace_path,
            log_directory=service.log_directory,
            config_workspace_path=service.config_workspace_path,
            health_targets_json=list(service.health_targets),
            tags_json=list(service.tags),
            created_at=service.created_at,
            updated_at=service.updated_at,
        )

    @staticmethod
    def _to_domain(record: ServiceProfileRecord) -> ServiceProfile:
        return ServiceProfile(
            id=UUID(record.id),
            name=record.name,
            description=record.description,
            environment=record.environment,
            code_workspace_path=record.code_workspace_path,
            log_directory=record.log_directory,
            config_workspace_path=record.config_workspace_path,
            health_targets=tuple(record.health_targets_json),
            tags=tuple(record.tags_json),
            created_at=_as_utc(record.created_at),
            updated_at=_as_utc(record.updated_at),
        )
