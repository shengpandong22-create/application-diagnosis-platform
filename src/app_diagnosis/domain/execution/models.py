from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Self
from uuid import UUID, uuid4

from app_diagnosis.domain.diagnosis import AgentTerminationReason


class AgentRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ToolRunStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


def _require_utc(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError(f"{name} must be timezone-aware UTC")


@dataclass(slots=True)
class AgentRun:
    id: UUID
    diagnosis_id: UUID
    strategy: str
    status: AgentRunStatus
    termination_reason: AgentTerminationReason | None
    model: str | None
    round_count: int
    tool_call_count: int
    input_tokens: int
    output_tokens: int
    started_at: datetime
    finished_at: datetime | None
    error_code: str | None

    def __post_init__(self) -> None:
        _require_utc(self.started_at, "started_at")
        if self.finished_at is not None:
            _require_utc(self.finished_at, "finished_at")
            if self.finished_at < self.started_at:
                raise ValueError("finished_at must not be earlier than started_at")
        if min(self.round_count, self.tool_call_count, self.input_tokens, self.output_tokens) < 0:
            raise ValueError("agent run counters must not be negative")

    @classmethod
    def start(
        cls,
        *,
        diagnosis_id: UUID,
        strategy: str,
        run_id: UUID | None = None,
        now: datetime | None = None,
    ) -> Self:
        started_at = now or datetime.now(UTC)
        return cls(
            id=run_id or uuid4(),
            diagnosis_id=diagnosis_id,
            strategy=strategy,
            status=AgentRunStatus.RUNNING,
            termination_reason=None,
            model=None,
            round_count=0,
            tool_call_count=0,
            input_tokens=0,
            output_tokens=0,
            started_at=started_at,
            finished_at=None,
            error_code=None,
        )

    def record_model_response(
        self,
        *,
        model: str,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> None:
        self._require_running()
        self.model = model
        self.round_count += 1
        self.input_tokens += input_tokens or 0
        self.output_tokens += output_tokens or 0

    def record_tool_calls(self, count: int) -> None:
        self._require_running()
        if count <= 0:
            raise ValueError("tool call increment must be positive")
        self.tool_call_count += count

    def finish(
        self,
        reason: AgentTerminationReason,
        *,
        now: datetime | None = None,
        error_code: str | None = None,
    ) -> None:
        self._require_running()
        finished_at = now or datetime.now(UTC)
        _require_utc(finished_at, "finished_at")
        if finished_at < self.started_at:
            raise ValueError("finished_at must not be earlier than started_at")
        self.termination_reason = reason
        self.finished_at = finished_at
        self.error_code = error_code
        if reason is AgentTerminationReason.CANCELLED:
            self.status = AgentRunStatus.CANCELLED
        elif reason in {AgentTerminationReason.MODEL_ERROR, AgentTerminationReason.INTERNAL_ERROR}:
            self.status = AgentRunStatus.FAILED
        else:
            self.status = AgentRunStatus.COMPLETED

    def _require_running(self) -> None:
        if self.status is not AgentRunStatus.RUNNING:
            raise ValueError("agent run is already finished")


@dataclass(frozen=True, slots=True)
class ToolRun:
    id: UUID
    agent_run_id: UUID
    tool_call_id: str
    tool_name: str
    arguments_json: dict[str, Any] | None
    status: ToolRunStatus
    result_json: dict[str, Any] | None
    duration_ms: int
    error_code: str | None
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.tool_call_id.strip() or not self.tool_name.strip():
            raise ValueError("tool call id and name must not be blank")
        if self.duration_ms < 0:
            raise ValueError("tool run duration must not be negative")
        _require_utc(self.created_at, "created_at")
        if self.status is ToolRunStatus.SUCCESS and self.error_code is not None:
            raise ValueError("successful tool run cannot have an error code")
        if self.status is not ToolRunStatus.SUCCESS and not self.error_code:
            raise ValueError("unsuccessful tool run requires an error code")
