from pydantic import BaseModel, ConfigDict, Field

from app_diagnosis.domain.diagnosis import ProblemType
from app_diagnosis.ports.health_check import HealthCheckClient
from app_diagnosis.tools.contracts import (
    EvidenceDraft,
    ToolExecutionContext,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolRiskLevel,
)


class HealthCheckInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: str = Field(min_length=1, max_length=100)


class HealthCheckOutput(BaseModel):
    target: str
    reachable: bool
    status_code: int | None
    duration_ms: int
    summary: str
    error_code: str | None


class HealthCheckTool:
    name = "health__check"
    description = "Check a preconfigured local HTTP health target by alias."
    input_model = HealthCheckInput
    output_model = HealthCheckOutput
    risk_level = ToolRiskLevel.READ_ONLY
    timeout_seconds = 5.0
    required_permissions = frozenset({"health:read"})
    supported_problem_types = frozenset({ProblemType.GENERIC_APPLICATION_ERROR})

    def __init__(self, client: HealthCheckClient | None = None) -> None:
        self._client = client

    async def execute(
        self, arguments: BaseModel, context: ToolExecutionContext
    ) -> ToolExecutionResult:
        try:
            if not isinstance(arguments, HealthCheckInput):
                raise TypeError("health__check requires HealthCheckInput")
            client = context.health_check_client or self._client
            if client is None:
                raise PermissionError("health targets are not configured for this diagnosis")
            result = await client.check(arguments.target)
            output = HealthCheckOutput(
                target=result.target,
                reachable=result.reachable,
                status_code=result.status_code,
                duration_ms=result.duration_ms,
                summary=result.summary,
                error_code=result.error_code,
            )
            summary = output.model_dump_json()
            if len(summary.encode()) > context.max_output_bytes:
                raise ValueError("health output exceeds tool output budget")
            return ToolExecutionResult(
                status=ToolExecutionStatus.SUCCESS,
                data=output,
                model_summary=summary,
                evidence_drafts=(
                    EvidenceDraft(
                        type="health_check",
                        source="local_service",
                        source_reference=result.target,
                        content=summary,
                    ),
                ),
                duration_ms=result.duration_ms,
            )
        except Exception as error:
            return ToolExecutionResult(
                status=ToolExecutionStatus.FAILED,
                data=None,
                model_summary='{"error":"health_check_failed"}',
                error_code=f"health_check_{type(error).__name__.lower()}",
            )
