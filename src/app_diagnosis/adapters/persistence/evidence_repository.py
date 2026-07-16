from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app_diagnosis.adapters.persistence.evidence_models import EvidenceRecord
from app_diagnosis.adapters.persistence.models import DiagnosisRecord
from app_diagnosis.domain.evidence import (
    Evidence,
    EvidenceReliability,
    EvidenceSource,
    EvidenceType,
    RedactionStatus,
)
from app_diagnosis.ports.evidence_repository import (
    EvidenceAlreadyExists,
    EvidenceDiagnosisNotFound,
)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _to_domain(record: EvidenceRecord) -> Evidence:
    return Evidence(
        id=UUID(record.id),
        diagnosis_id=UUID(record.diagnosis_id),
        type=EvidenceType(record.type),
        source=EvidenceSource(record.source),
        source_reference=record.source_reference,
        content=record.content,
        content_hash=record.content_hash,
        reliability=EvidenceReliability(record.reliability),
        metadata=record.metadata_json or {},
        redaction_status=RedactionStatus(record.redaction_status),
        created_at=_as_utc(record.created_at),
    )


class SqlAlchemyEvidenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, evidence: Evidence) -> None:
        if await self._session.get(DiagnosisRecord, str(evidence.diagnosis_id)) is None:
            raise EvidenceDiagnosisNotFound(evidence.diagnosis_id)
        record = EvidenceRecord(
            id=str(evidence.id),
            diagnosis_id=str(evidence.diagnosis_id),
            type=evidence.type.value,
            source=evidence.source.value,
            source_reference=evidence.source_reference,
            content=evidence.content,
            content_hash=evidence.content_hash,
            reliability=evidence.reliability.value,
            metadata_json=evidence.metadata,
            redaction_status=evidence.redaction_status.value,
            created_at=evidence.created_at,
        )
        try:
            async with self._session.begin_nested():
                self._session.add(record)
                await self._session.flush()
        except IntegrityError as error:
            raise EvidenceAlreadyExists(evidence.diagnosis_id, evidence.content_hash) from error

    async def get(self, evidence_id: UUID) -> Evidence | None:
        record = await self._session.get(EvidenceRecord, str(evidence_id))
        return _to_domain(record) if record is not None else None

    async def find_by_hash(self, diagnosis_id: UUID, content_hash: str) -> Evidence | None:
        statement = select(EvidenceRecord).where(
            EvidenceRecord.diagnosis_id == str(diagnosis_id),
            EvidenceRecord.content_hash == content_hash,
        )
        record = await self._session.scalar(statement)
        return _to_domain(record) if record is not None else None

    async def list_by_diagnosis(self, diagnosis_id: UUID) -> list[Evidence]:
        statement = (
            select(EvidenceRecord)
            .where(EvidenceRecord.diagnosis_id == str(diagnosis_id))
            .order_by(EvidenceRecord.created_at, EvidenceRecord.id)
        )
        records = (await self._session.scalars(statement)).all()
        return [_to_domain(record) for record in records]
