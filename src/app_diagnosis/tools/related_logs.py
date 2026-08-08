from datetime import datetime
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


class RelatedLogsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=500)
    trace_id: str = Field(min_length=1, max_length=200)
    started_at: datetime
    ended_at: datetime
    limit: int = Field(default=10, ge=1, le=50)


class RelatedLogItem(BaseModel):
    source_reference: str
    matched_line: int
    content: str


class RelatedLogsOutput(BaseModel):
    items: list[RelatedLogItem]


class RelatedLogsQueryTool:
    name = "related_logs__query"
    description = "Query trace-correlated events in one authorized log file and UTC time range."
    input_model = RelatedLogsInput
    output_model = RelatedLogsOutput
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
            if not isinstance(arguments, RelatedLogsInput):
                raise TypeError("related_logs__query requires RelatedLogsInput")
            reader = context.log_reader or self._reader
            if reader is None:
                raise PermissionError("log directory is not configured for this diagnosis")
            excerpts = reader.query_related(
                relative_path=arguments.path,
                trace_id=arguments.trace_id,
                started_at=arguments.started_at,
                ended_at=arguments.ended_at,
                limit=arguments.limit,
            )
            items = [
                RelatedLogItem(
                    source_reference=item.source_reference,
                    matched_line=item.matched_line,
                    content=self._redactor.redact(item.content).content,
                )
                for item in excerpts
            ]
            output = RelatedLogsOutput(items=items)
            summary = output.model_dump_json()
            if len(summary.encode()) > context.max_output_bytes:
                raise ValueError("related logs exceed tool output budget")
            return ToolExecutionResult(
                status=ToolExecutionStatus.SUCCESS,
                data=output,
                model_summary=summary,
                evidence_drafts=tuple(
                    EvidenceDraft(
                        type="log_excerpt",
                        source="local_log",
                        source_reference=item.source_reference,
                        content=item.content,
                        metadata={"trace_id": arguments.trace_id, "related_log": True},
                    )
                    for item in items
                ),
                duration_ms=int((perf_counter() - started) * 1000),
            )
        except Exception as error:
            return ToolExecutionResult(
                status=ToolExecutionStatus.FAILED,
                data=None,
                model_summary='{"error":"related_logs_query_failed"}',
                error_code=f"related_logs_{type(error).__name__.lower()}",
                duration_ms=int((perf_counter() - started) * 1000),
            )
