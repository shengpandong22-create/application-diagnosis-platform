from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class EvaluationCandidateStatus(StrEnum):
    CANDIDATE = "candidate"
    LABELED = "labeled"
    PROMOTED = "promoted"


@dataclass(frozen=True, slots=True)
class EvaluationCandidate:
    id: UUID
    diagnosis_id: UUID
    source_action: str
    status: EvaluationCandidateStatus
    feedback_summary: str | None
    expected_category: str | None
    expected_root_cause: str | None
    required_evidence_ids: tuple[UUID, ...]
    prompt_version: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls, *, diagnosis_id: UUID, source_action: str, feedback_summary: str | None
    ) -> "EvaluationCandidate":
        now = datetime.now(UTC)
        return cls(
            id=uuid4(), diagnosis_id=diagnosis_id, source_action=source_action,
            status=EvaluationCandidateStatus.CANDIDATE,
            feedback_summary=feedback_summary,
            expected_category=None, expected_root_cause=None, required_evidence_ids=(),
            prompt_version="unlabeled", created_at=now, updated_at=now,
        )

    def label(
        self,
        *,
        expected_category: str,
        expected_root_cause: str,
        required_evidence_ids: tuple[UUID, ...],
        prompt_version: str,
    ) -> "EvaluationCandidate":
        if self.status is EvaluationCandidateStatus.PROMOTED:
            raise ValueError("promoted candidate cannot be relabeled")
        if not expected_category.strip() or not expected_root_cause.strip():
            raise ValueError("evaluation label must not be blank")
        return replace(
            self, status=EvaluationCandidateStatus.LABELED,
            expected_category=expected_category.strip(),
            expected_root_cause=expected_root_cause.strip(),
            required_evidence_ids=required_evidence_ids,
            prompt_version=prompt_version.strip() or "unspecified",
            updated_at=datetime.now(UTC),
        )

    def promote(self) -> "EvaluationCandidate":
        if self.status is not EvaluationCandidateStatus.LABELED:
            raise ValueError("only labeled candidate can be promoted")
        return replace(
            self, status=EvaluationCandidateStatus.PROMOTED, updated_at=datetime.now(UTC)
        )
