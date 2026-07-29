from time import perf_counter

from pydantic import BaseModel, ConfigDict, Field

from app_diagnosis.domain.diagnosis import ProblemType
from app_diagnosis.ports.config_repository import ConfigRepository
from app_diagnosis.ports.redaction import Redactor
from app_diagnosis.tools.contracts import (
    EvidenceDraft,
    ToolExecutionContext,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolRiskLevel,
)


class ConfigReadInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=500)
    start_line: int = Field(default=1, ge=1)
    end_line: int = Field(default=120, ge=1)


class ConfigReadOutput(BaseModel):
    path: str
    start_line: int
    end_line: int
    content: str


class ConfigReadTool:
    name = "config__read"
    description = "Read a bounded, redacted excerpt from the authorized config workspace."
    input_model = ConfigReadInput
    output_model = ConfigReadOutput
    risk_level = ToolRiskLevel.READ_ONLY
    timeout_seconds = 2.0
    required_permissions = frozenset({"config:read"})
    supported_problem_types = frozenset({ProblemType.GENERIC_APPLICATION_ERROR})

    def __init__(self, repository: ConfigRepository | None, redactor: Redactor) -> None:
        self._repository = repository
        self._redactor = redactor

    async def execute(
        self, arguments: BaseModel, context: ToolExecutionContext
    ) -> ToolExecutionResult:
        started = perf_counter()
        try:
            if not isinstance(arguments, ConfigReadInput):
                raise TypeError("config__read requires ConfigReadInput")
            repository = context.config_repository or self._repository
            if repository is None:
                raise PermissionError("config workspace is not configured for this diagnosis")
            excerpt = await repository.read(
                arguments.path,
                start_line=arguments.start_line,
                end_line=arguments.end_line,
            )
            safe = self._redactor.redact(excerpt.content).content
            output = ConfigReadOutput(
                path=excerpt.path,
                start_line=excerpt.start_line,
                end_line=excerpt.end_line,
                content=safe,
            )
            summary = output.model_dump_json()
            if len(summary.encode()) > context.max_output_bytes:
                raise ValueError("config excerpt exceeds tool output budget")
            return ToolExecutionResult(
                status=ToolExecutionStatus.SUCCESS,
                data=output,
                model_summary=summary,
                evidence_drafts=(
                    EvidenceDraft(
                        type="config_excerpt",
                        source="local_config",
                        source_reference=f"{excerpt.path}:{excerpt.start_line}-{excerpt.end_line}",
                        content=safe,
                        metadata={"path": excerpt.path},
                    ),
                ),
                duration_ms=int((perf_counter() - started) * 1000),
            )
        except Exception as error:
            return ToolExecutionResult(
                status=ToolExecutionStatus.FAILED,
                data=None,
                model_summary='{"error":"config_read_failed"}',
                error_code=f"config_read_{type(error).__name__.lower()}",
                duration_ms=int((perf_counter() - started) * 1000),
            )
