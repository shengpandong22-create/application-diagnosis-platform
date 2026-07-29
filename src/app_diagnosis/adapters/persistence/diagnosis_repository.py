from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app_diagnosis.adapters.persistence.models import DiagnosisRecord
from app_diagnosis.domain.diagnosis import DiagnosisCase, DiagnosisStatus, ProblemType
from app_diagnosis.ports.diagnosis_repository import (
    ConcurrentDiagnosisUpdate,
    DiagnosisAlreadyExists,
)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class SqlAlchemyDiagnosisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, diagnosis: DiagnosisCase) -> None:
        record = DiagnosisRecord(
            id=str(diagnosis.id),
            service_id=str(diagnosis.service_id) if diagnosis.service_id else None,
            title=diagnosis.title,
            problem_type=diagnosis.problem_type.value,
            status=diagnosis.status.value,
            symptom=diagnosis.symptom,
            submitted_log=diagnosis.submitted_log,
            conclusion_json=diagnosis.conclusion,
            version=diagnosis.version,
            created_at=diagnosis.created_at,
            updated_at=diagnosis.updated_at,
        )
        try:
            async with self._session.begin_nested():
                self._session.add(record)
                await self._session.flush()
        except IntegrityError as error:
            raise DiagnosisAlreadyExists(diagnosis.id) from error

    async def get(self, diagnosis_id: UUID) -> DiagnosisCase | None:
        record = await self._session.get(DiagnosisRecord, str(diagnosis_id))
        if record is None:
            return None
        return DiagnosisCase(
            id=UUID(record.id),
            service_id=UUID(record.service_id) if record.service_id else None,
            title=record.title,
            problem_type=ProblemType(record.problem_type),
            status=DiagnosisStatus(record.status),
            symptom=record.symptom,
            submitted_log=record.submitted_log,
            version=record.version,
            created_at=_as_utc(record.created_at),
            updated_at=_as_utc(record.updated_at),
            conclusion=record.conclusion_json,
        )

    async def save(self, diagnosis: DiagnosisCase, *, expected_version: int) -> None:
        statement = (
            update(DiagnosisRecord)
            .where(
                DiagnosisRecord.id == str(diagnosis.id),
                DiagnosisRecord.version == expected_version,
            )
            .values(
                title=diagnosis.title,
                service_id=str(diagnosis.service_id) if diagnosis.service_id else None,
                problem_type=diagnosis.problem_type.value,
                status=diagnosis.status.value,
                symptom=diagnosis.symptom,
                submitted_log=diagnosis.submitted_log,
                conclusion_json=diagnosis.conclusion,
                version=diagnosis.version,
                updated_at=diagnosis.updated_at,
            )
        )
        result = await self._session.execute(statement)
        if result.rowcount != 1:
            raise ConcurrentDiagnosisUpdate(diagnosis.id, expected_version)
