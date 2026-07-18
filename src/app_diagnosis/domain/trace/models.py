from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class TraceEventType(StrEnum):
    RUN_STARTED = "run_started"
    TOOL_CALL = "tool_call"
    RUN_FINISHED = "run_finished"


@dataclass(frozen=True, slots=True)
class TraceEvent:
    type: TraceEventType
    sequence: int
    occurred_at: datetime
    summary: str
    tool_name: str | None = None
    status: str | None = None
    duration_ms: int | None = None
    error_code: str | None = None
    evidence_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class AgentRunTrace:
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
    events: tuple[TraceEvent, ...]


@dataclass(frozen=True, slots=True)
class DiagnosisTrace:
    diagnosis_id: UUID
    diagnosis_status: str
    runs: tuple[AgentRunTrace, ...]
