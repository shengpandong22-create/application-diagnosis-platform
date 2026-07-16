from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app_diagnosis.agent.runtime import ToolLoopResult
from app_diagnosis.application.diagnoses import DiagnosisRunDetails
from app_diagnosis.domain.confirmation import Confirmation, ConfirmationAction
from app_diagnosis.domain.diagnosis import DiagnosisCase
from app_diagnosis.domain.evidence import Evidence, EvidenceType


class CreateDiagnosisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    symptom: str = Field(min_length=1, max_length=10_000)
    submitted_log: str | None = None


class DiagnosisResponse(BaseModel):
    id: UUID
    title: str
    problem_type: str
    status: str
    symptom: str
    submitted_log: str | None
    conclusion: dict[str, Any] | None
    version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, diagnosis: DiagnosisCase) -> "DiagnosisResponse":
        return cls(
            id=diagnosis.id,
            title=diagnosis.title,
            problem_type=diagnosis.problem_type.value,
            status=diagnosis.status.value,
            symptom=diagnosis.symptom,
            submitted_log=diagnosis.submitted_log,
            conclusion=diagnosis.conclusion,
            version=diagnosis.version,
            created_at=diagnosis.created_at,
            updated_at=diagnosis.updated_at,
        )


class SupplementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=16_384)
    type: EvidenceType = EvidenceType.USER_STATEMENT


class ConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: ConfirmationAction
    comment: str | None = Field(default=None, max_length=2000)


class EvidenceResponse(BaseModel):
    id: UUID
    diagnosis_id: UUID
    type: str
    source: str
    source_reference: str | None
    content: str
    content_hash: str
    reliability: str
    metadata: dict[str, Any]
    redaction_status: str
    created_at: datetime

    @classmethod
    def from_domain(cls, evidence: Evidence) -> "EvidenceResponse":
        return cls(
            id=evidence.id,
            diagnosis_id=evidence.diagnosis_id,
            type=evidence.type.value,
            source=evidence.source.value,
            source_reference=evidence.source_reference,
            content=evidence.content,
            content_hash=evidence.content_hash,
            reliability=evidence.reliability.value,
            metadata=evidence.metadata,
            redaction_status=evidence.redaction_status.value,
            created_at=evidence.created_at,
        )


class SupplementResponse(BaseModel):
    diagnosis: DiagnosisResponse
    evidence: EvidenceResponse


class ConfirmationRecordResponse(BaseModel):
    id: UUID
    diagnosis_id: UUID
    action: str
    actor: str
    comment: str | None
    created_at: datetime

    @classmethod
    def from_domain(cls, item: Confirmation) -> "ConfirmationRecordResponse":
        return cls(
            id=item.id,
            diagnosis_id=item.diagnosis_id,
            action=item.action.value,
            actor=item.actor,
            comment=item.comment,
            created_at=item.created_at,
        )


class ConfirmationResponse(BaseModel):
    diagnosis: DiagnosisResponse
    confirmation: ConfirmationRecordResponse


class RunResultResponse(BaseModel):
    agent_run_id: UUID
    termination_reason: str
    conclusion: dict[str, Any] | None

    @classmethod
    def from_result(cls, result: ToolLoopResult) -> "RunResultResponse":
        return cls(
            agent_run_id=result.agent_run_id,
            termination_reason=result.termination_reason.value,
            conclusion=(result.conclusion.model_dump(mode="json") if result.conclusion else None),
        )


class ToolRunResponse(BaseModel):
    id: UUID
    tool_call_id: str
    tool_name: str
    arguments: dict[str, Any] | None
    status: str
    result: dict[str, Any] | None
    duration_ms: int
    error_code: str | None
    created_at: datetime


class AgentRunResponse(BaseModel):
    id: UUID
    status: str
    termination_reason: str | None
    strategy: str
    model: str | None
    round_count: int
    tool_call_count: int
    input_tokens: int
    output_tokens: int
    started_at: datetime
    finished_at: datetime | None
    error_code: str | None
    tool_runs: list[ToolRunResponse]

    @classmethod
    def from_details(cls, details: DiagnosisRunDetails) -> "AgentRunResponse":
        run = details.run
        return cls(
            id=run.id,
            status=run.status.value,
            termination_reason=(run.termination_reason.value if run.termination_reason else None),
            strategy=run.strategy,
            model=run.model,
            round_count=run.round_count,
            tool_call_count=run.tool_call_count,
            input_tokens=run.input_tokens,
            output_tokens=run.output_tokens,
            started_at=run.started_at,
            finished_at=run.finished_at,
            error_code=run.error_code,
            tool_runs=[
                ToolRunResponse(
                    id=item.id,
                    tool_call_id=item.tool_call_id,
                    tool_name=item.tool_name,
                    arguments=item.arguments_json,
                    status=item.status.value,
                    result=item.result_json,
                    duration_ms=item.duration_ms,
                    error_code=item.error_code,
                    created_at=item.created_at,
                )
                for item in details.tool_runs
            ],
        )
