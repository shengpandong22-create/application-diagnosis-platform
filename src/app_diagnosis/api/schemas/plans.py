from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app_diagnosis.domain.diagnosis_plan import DiagnosisPlan


class PlanStepResponse(BaseModel):
    order: int
    title: str
    description: str
    tool_name: str | None
    expected_evidence: list[str]


class DiagnosisPlanResponse(BaseModel):
    id: UUID
    diagnosis_id: UUID
    agent_run_id: UUID
    summary: str
    hypotheses: list[str]
    steps: list[PlanStepResponse]
    expected_evidence: list[str]
    allowed_tools: list[str]
    status: str
    created_at: datetime

    @classmethod
    def from_domain(cls, plan: DiagnosisPlan) -> "DiagnosisPlanResponse":
        return cls.model_validate(plan, from_attributes=True)
