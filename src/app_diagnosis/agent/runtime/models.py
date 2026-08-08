from dataclasses import dataclass
from uuid import UUID

from app_diagnosis.agent.schemas.diagnosis import DiagnosisConclusion
from app_diagnosis.domain.diagnosis import AgentTerminationReason
from app_diagnosis.ports.code_repository import CodeRepository
from app_diagnosis.ports.config_repository import ConfigRepository
from app_diagnosis.ports.health_check import HealthCheckClient
from app_diagnosis.ports.log_reader import LogReader


@dataclass(frozen=True, slots=True)
class AgentBudget:
    max_rounds: int = 6
    max_tool_calls: int = 8
    total_timeout_seconds: float = 120

    def __post_init__(self) -> None:
        if self.max_rounds <= 0 or self.max_tool_calls <= 0 or self.total_timeout_seconds <= 0:
            raise ValueError("agent budgets must be positive")


@dataclass(frozen=True, slots=True)
class ToolResourceContext:
    """单次 AgentRun 可使用的受限外部资源。

    Phase 3C-2 之后，工具不再只能依赖应用启动时的全局目录配置。
    如果 Diagnosis 绑定了 ServiceProfile，这里会携带该服务显式授权的源码、日志、
    配置和健康检查资源；没有绑定服务时，则回退到 Settings 中的全局资源。
    """

    code_repository: CodeRepository | None = None
    log_reader: LogReader | None = None
    config_repository: ConfigRepository | None = None
    health_check_client: HealthCheckClient | None = None

    @property
    def available_tool_names(self) -> frozenset[str]:
        names = {"knowledge__search"}
        if self.code_repository is not None:
            names.update({"code__search", "code__read"})
        if self.log_reader is not None:
            names.update({"log__search", "related_logs__query"})
        if self.config_repository is not None:
            names.add("config__read")
        if self.health_check_client is not None:
            names.add("health__check")
        return frozenset(names)


@dataclass(frozen=True, slots=True)
class ToolLoopContext:
    actor: str
    environment: str
    audit_correlation_id: str
    permissions: frozenset[str]
    max_tool_output_bytes: int
    resources: ToolResourceContext = ToolResourceContext()


@dataclass(frozen=True, slots=True)
class ToolLoopResult:
    agent_run_id: UUID
    termination_reason: AgentTerminationReason
    conclusion: DiagnosisConclusion | None
