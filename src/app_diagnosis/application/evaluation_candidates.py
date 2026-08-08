from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_diagnosis.adapters.persistence.evaluation_candidate_repository import (
    SqlAlchemyEvaluationCandidateRepository,
)
from app_diagnosis.adapters.persistence.evidence_repository import SqlAlchemyEvidenceRepository
from app_diagnosis.domain.evaluation_candidate import EvaluationCandidate


class EvaluationCandidateNotFound(LookupError):
    pass


class EvaluationCandidateConflict(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class EvaluationCandidateTrend:
    status_counts: dict[str, int]
    prompt_version_counts: dict[str, int]


class EvaluationCandidateService:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def list(self) -> tuple[EvaluationCandidate, ...]:
        async with self._sessions() as session:
            return await SqlAlchemyEvaluationCandidateRepository(session).list()

    async def label(
        self,
        candidate_id: UUID,
        *,
        expected_category: str,
        expected_root_cause: str,
        required_evidence_ids: tuple[UUID, ...],
        prompt_version: str,
    ) -> EvaluationCandidate:
        async with self._sessions.begin() as session:
            repository = SqlAlchemyEvaluationCandidateRepository(session)
            item = await repository.get(candidate_id)
            if item is None:
                raise EvaluationCandidateNotFound(str(candidate_id))
            evidence = await SqlAlchemyEvidenceRepository(session).list_by_diagnosis(
                item.diagnosis_id
            )
            available = {value.id for value in evidence}
            if not set(required_evidence_ids) <= available:
                raise EvaluationCandidateConflict(
                    "evaluation label contains foreign evidence IDs"
                )
            try:
                item = item.label(
                    expected_category=expected_category,
                    expected_root_cause=expected_root_cause,
                    required_evidence_ids=required_evidence_ids,
                    prompt_version=prompt_version,
                )
            except ValueError as error:
                raise EvaluationCandidateConflict(str(error)) from error
            await repository.save(item)
            return item

    async def promote(self, candidate_id: UUID) -> EvaluationCandidate:
        async with self._sessions.begin() as session:
            repository = SqlAlchemyEvaluationCandidateRepository(session)
            item = await repository.get(candidate_id)
            if item is None:
                raise EvaluationCandidateNotFound(str(candidate_id))
            try:
                item = item.promote()
            except ValueError as error:
                raise EvaluationCandidateConflict(str(error)) from error
            await repository.save(item)
            return item

    async def trend(self) -> EvaluationCandidateTrend:
        items = await self.list()
        statuses: dict[str, int] = {}
        prompts: dict[str, int] = {}
        for item in items:
            statuses[item.status.value] = statuses.get(item.status.value, 0) + 1
            prompts[item.prompt_version] = prompts.get(item.prompt_version, 0) + 1
        return EvaluationCandidateTrend(statuses, prompts)
