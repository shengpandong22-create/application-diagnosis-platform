from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app_diagnosis.adapters.persistence.evaluation_candidate_models import (
    EvaluationCandidateRecord,
)
from app_diagnosis.domain.evaluation_candidate import (
    EvaluationCandidate,
    EvaluationCandidateStatus,
)


class SqlAlchemyEvaluationCandidateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, item: EvaluationCandidate) -> None:
        self._session.add(self._record(item))
        await self._session.flush()

    async def get(self, candidate_id: UUID) -> EvaluationCandidate | None:
        record = await self._session.get(EvaluationCandidateRecord, str(candidate_id))
        return None if record is None else self._domain(record)

    async def get_by_diagnosis(self, diagnosis_id: UUID) -> EvaluationCandidate | None:
        record = await self._session.scalar(
            select(EvaluationCandidateRecord).where(
                EvaluationCandidateRecord.diagnosis_id == str(diagnosis_id)
            )
        )
        return None if record is None else self._domain(record)

    async def list(self) -> tuple[EvaluationCandidate, ...]:
        records = (
            await self._session.scalars(
                select(EvaluationCandidateRecord).order_by(
                    EvaluationCandidateRecord.created_at.desc()
                )
            )
        ).all()
        return tuple(self._domain(item) for item in records)

    async def save(self, item: EvaluationCandidate) -> None:
        record = await self._session.get(EvaluationCandidateRecord, str(item.id))
        if record is None:
            raise LookupError(str(item.id))
        record.status = item.status.value
        record.feedback_summary = item.feedback_summary
        record.expected_category = item.expected_category
        record.expected_root_cause = item.expected_root_cause
        record.required_evidence_ids_json = [str(value) for value in item.required_evidence_ids]
        record.prompt_version = item.prompt_version
        record.updated_at = item.updated_at
        await self._session.flush()

    @staticmethod
    def _record(item: EvaluationCandidate) -> EvaluationCandidateRecord:
        return EvaluationCandidateRecord(
            id=str(item.id), diagnosis_id=str(item.diagnosis_id),
            source_action=item.source_action, status=item.status.value,
            feedback_summary=item.feedback_summary, expected_category=item.expected_category,
            expected_root_cause=item.expected_root_cause,
            required_evidence_ids_json=[str(value) for value in item.required_evidence_ids],
            prompt_version=item.prompt_version, created_at=item.created_at,
            updated_at=item.updated_at,
        )

    @staticmethod
    def _domain(item: EvaluationCandidateRecord) -> EvaluationCandidate:
        def utc(value: datetime) -> datetime:
            return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

        return EvaluationCandidate(
            id=UUID(item.id), diagnosis_id=UUID(item.diagnosis_id),
            source_action=item.source_action, status=EvaluationCandidateStatus(item.status),
            feedback_summary=item.feedback_summary, expected_category=item.expected_category,
            expected_root_cause=item.expected_root_cause,
            required_evidence_ids=tuple(UUID(value) for value in item.required_evidence_ids_json),
            prompt_version=item.prompt_version, created_at=utc(item.created_at),
            updated_at=utc(item.updated_at),
        )
