from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app_diagnosis.domain.trace import DiagnosisTrace


class TraceEventResponse(BaseModel):
    type: str
    sequence: int
    occurred_at: datetime
    summary: str
    tool_name: str | None
    status: str | None
    duration_ms: int | None
    error_code: str | None
    evidence_ids: list[UUID]


class AgentRunTraceResponse(BaseModel):
    agent_run_id: UUID
    strategy: str
    status: str
    termination_reason: str | None
    model: str | None
    round_count: int
    tool_call_count: int
    input_tokens: int
    output_tokens: int
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    events: list[TraceEventResponse]


class DiagnosisTraceResponse(BaseModel):
    diagnosis_id: UUID
    diagnosis_status: str
    runs: list[AgentRunTraceResponse]

    @classmethod
    def from_domain(cls, trace: DiagnosisTrace) -> "DiagnosisTraceResponse":
        return cls.model_validate(trace, from_attributes=True)
