from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel

from app_diagnosis.domain.diagnosis import ProblemType
from app_diagnosis.ports.code_repository import CodeRepository
from app_diagnosis.ports.config_repository import ConfigRepository
from app_diagnosis.ports.health_check import HealthCheckClient
from app_diagnosis.ports.log_reader import LogReader


class ToolRiskLevel(StrEnum):
    READ_ONLY = "read_only"
    RESTRICTED = "restricted"
    STATE_CHANGE = "state_change"


class ToolExecutionStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class EvidenceDraft:
    type: str
    source: str
    source_reference: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolExecutionContext:
    diagnosis_id: UUID
    agent_run_id: UUID
    actor: str
    environment: str
    deadline: datetime
    audit_correlation_id: str
    permissions: frozenset[str]
    problem_type: ProblemType
    max_output_bytes: int
    code_repository: CodeRepository | None = None
    log_reader: LogReader | None = None
    config_repository: ConfigRepository | None = None
    health_check_client: HealthCheckClient | None = None

    def __post_init__(self) -> None:
        if not self.actor.strip():
            raise ValueError("tool actor must not be blank")
        if not self.environment.strip():
            raise ValueError("tool environment must not be blank")
        if not self.audit_correlation_id.strip():
            raise ValueError("audit correlation id must not be blank")
        if self.deadline.tzinfo is None or self.deadline.utcoffset() != UTC.utcoffset(
            self.deadline
        ):
            raise ValueError("tool deadline must be timezone-aware UTC")
        if self.max_output_bytes < 256:
            raise ValueError("tool max_output_bytes must be at least 256")


@dataclass(frozen=True, slots=True)
class ToolExecutionResult:
    status: ToolExecutionStatus
    data: BaseModel | None
    model_summary: str
    evidence_drafts: tuple[EvidenceDraft, ...] = ()
    error_code: str | None = None
    retryable: bool = False
    duration_ms: int = 0
    truncated: bool = False

    def __post_init__(self) -> None:
        if self.duration_ms < 0:
            raise ValueError("tool duration must not be negative")
        if self.status is ToolExecutionStatus.SUCCESS:
            if self.data is None or self.error_code is not None:
                raise ValueError("successful tool result requires data and no error code")
        elif not self.error_code:
            raise ValueError("unsuccessful tool result requires an error code")


class DiagnosticTool(Protocol):
    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    risk_level: ToolRiskLevel
    timeout_seconds: float
    required_permissions: frozenset[str]
    supported_problem_types: frozenset[ProblemType]

    async def execute(
        self,
        arguments: BaseModel,
        context: ToolExecutionContext,
    ) -> ToolExecutionResult: ...
