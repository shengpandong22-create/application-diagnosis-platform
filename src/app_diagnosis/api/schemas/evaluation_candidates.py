from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app_diagnosis.application.evaluation_candidates import EvaluationCandidateTrend
from app_diagnosis.domain.evaluation_candidate import EvaluationCandidate


class EvaluationCandidateResponse(BaseModel):
    id: UUID
    diagnosis_id: UUID
    source_action: str
    status: str
    feedback_summary: str | None
    expected_category: str | None
    expected_root_cause: str | None
    required_evidence_ids: list[UUID]
    prompt_version: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, value: EvaluationCandidate) -> "EvaluationCandidateResponse":
        return cls.model_validate(value, from_attributes=True)


class LabelEvaluationCandidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_category: str = Field(min_length=1, max_length=100)
    expected_root_cause: str = Field(min_length=1, max_length=2000)
    required_evidence_ids: list[UUID] = Field(default_factory=list, max_length=50)
    prompt_version: str = Field(min_length=1, max_length=100)


class EvaluationCandidateTrendResponse(BaseModel):
    status_counts: dict[str, int]
    prompt_version_counts: dict[str, int]

    @classmethod
    def from_domain(cls, value: EvaluationCandidateTrend) -> "EvaluationCandidateTrendResponse":
        return cls.model_validate(value, from_attributes=True)
