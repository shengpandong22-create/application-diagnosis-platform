from dataclasses import dataclass
from uuid import UUID

from app_diagnosis.agent.schemas.diagnosis import DiagnosisConclusion
from app_diagnosis.domain.diagnosis import AgentTerminationReason


@dataclass(frozen=True, slots=True)
class AgentBudget:
    max_rounds: int = 6
    max_tool_calls: int = 8
    total_timeout_seconds: float = 120

    def __post_init__(self) -> None:
        if self.max_rounds <= 0 or self.max_tool_calls <= 0 or self.total_timeout_seconds <= 0:
            raise ValueError("agent budgets must be positive")


@dataclass(frozen=True, slots=True)
class ToolLoopContext:
    actor: str
    environment: str
    audit_correlation_id: str
    permissions: frozenset[str]
    max_tool_output_bytes: int


@dataclass(frozen=True, slots=True)
class ToolLoopResult:
    agent_run_id: UUID
    termination_reason: AgentTerminationReason
    conclusion: DiagnosisConclusion | None
