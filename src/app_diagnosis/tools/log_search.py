from time import perf_counter

from pydantic import BaseModel, ConfigDict, Field

from app_diagnosis.domain.diagnosis import ProblemType
from app_diagnosis.ports.log_reader import LogReader
from app_diagnosis.ports.redaction import Redactor
from app_diagnosis.tools.contracts import (
    EvidenceDraft,
    ToolExecutionContext,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolRiskLevel,
)


class LogSearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=500)
    keyword: str = Field(min_length=1, max_length=200)


class LogSearchOutput(BaseModel):
    source_reference: str
    matched_line: int
    content: str


class LogSearchTool:
    name = "log__search"
    description = "Read the latest matching event from an authorized local log file."
    input_model = LogSearchInput
    output_model = LogSearchOutput
    risk_level = ToolRiskLevel.READ_ONLY
    timeout_seconds = 2.0
    required_permissions = frozenset({"log:read"})
    supported_problem_types = frozenset({ProblemType.GENERIC_APPLICATION_ERROR})

    def __init__(self, reader: LogReader | None, redactor: Redactor) -> None:
        self._reader = reader
        self._redactor = redactor

    async def execute(
        self, arguments: BaseModel, context: ToolExecutionContext
    ) -> ToolExecutionResult:
        started = perf_counter()
        try:
            if not isinstance(arguments, LogSearchInput):
                raise TypeError("log__search requires LogSearchInput")
            reader = context.log_reader or self._reader
            if reader is None:
                raise PermissionError("log directory is not configured for this diagnosis")
            excerpt = reader.read_latest(
                relative_path=arguments.path,
                keyword=arguments.keyword,
            )
            safe = self._redactor.redact(excerpt.content).content
            output = LogSearchOutput(
                source_reference=excerpt.source_reference,
                matched_line=excerpt.matched_line,
                content=safe,
            )
            summary = output.model_dump_json()
            if len(summary.encode()) > context.max_output_bytes:
                raise ValueError("log excerpt exceeds tool output budget")
            return ToolExecutionResult(
                status=ToolExecutionStatus.SUCCESS,
                data=output,
                model_summary=summary,
                evidence_drafts=(
                    EvidenceDraft(
                        type="log_excerpt",
                        source="local_log",
                        source_reference=excerpt.source_reference,
                        content=safe,
                        metadata={"matched_line": excerpt.matched_line},
                    ),
                ),
                duration_ms=int((perf_counter() - started) * 1000),
            )
        except Exception as error:
            return ToolExecutionResult(
                status=ToolExecutionStatus.FAILED,
                data=None,
                model_summary='{"error":"log_search_failed"}',
                error_code=f"log_search_{type(error).__name__.lower()}",
                duration_ms=int((perf_counter() - started) * 1000),
            )
