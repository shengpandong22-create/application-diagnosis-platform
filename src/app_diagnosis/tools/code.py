from time import perf_counter

from pydantic import BaseModel, ConfigDict, Field

from app_diagnosis.domain.diagnosis import ProblemType
from app_diagnosis.ports.code_repository import CodeRepository
from app_diagnosis.tools.contracts import (
    EvidenceDraft,
    ToolExecutionContext,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolRiskLevel,
)


class CodeSearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=10, ge=1, le=20)


class CodeMatchOutput(BaseModel):
    path: str
    line: int
    preview: str


class CodeSearchOutput(BaseModel):
    matches: list[CodeMatchOutput]


class CodeReadInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=500)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)


class CodeReadOutput(BaseModel):
    workspace: str
    revision: str
    path: str
    start_line: int
    end_line: int
    content: str


class CodeSearchTool:
    name = "code__search"
    description = "Search text only inside the pre-authorized local code workspace."
    input_model = CodeSearchInput
    output_model = CodeSearchOutput
    risk_level = ToolRiskLevel.READ_ONLY
    timeout_seconds = 3.0
    required_permissions = frozenset({"code:read"})
    supported_problem_types = frozenset({ProblemType.GENERIC_APPLICATION_ERROR})

    def __init__(self, repository: CodeRepository) -> None:
        self._repository = repository

    async def execute(
        self, arguments: BaseModel, context: ToolExecutionContext
    ) -> ToolExecutionResult:
        started = perf_counter()
        try:
            if not isinstance(arguments, CodeSearchInput):
                raise TypeError("code__search requires CodeSearchInput")
            found = await self._repository.search(arguments.query, limit=arguments.limit)
            output = CodeSearchOutput(
                matches=[
                    CodeMatchOutput(path=item.path, line=item.line, preview=item.preview)
                    for item in found
                ]
            )
            summary = output.model_dump_json()
            return ToolExecutionResult(
                status=ToolExecutionStatus.SUCCESS,
                data=output,
                model_summary=summary,
                duration_ms=int((perf_counter() - started) * 1000),
            )
        except Exception as error:
            return ToolExecutionResult(
                status=ToolExecutionStatus.FAILED,
                data=None,
                model_summary='{"error":"code_search_failed"}',
                error_code=f"code_search_{type(error).__name__.lower()}",
                duration_ms=int((perf_counter() - started) * 1000),
            )


class CodeReadTool:
    name = "code__read"
    description = "Read a bounded line range from a file returned by code__search."
    input_model = CodeReadInput
    output_model = CodeReadOutput
    risk_level = ToolRiskLevel.READ_ONLY
    timeout_seconds = 2.0
    required_permissions = frozenset({"code:read"})
    supported_problem_types = frozenset({ProblemType.GENERIC_APPLICATION_ERROR})

    def __init__(self, repository: CodeRepository) -> None:
        self._repository = repository

    async def execute(
        self, arguments: BaseModel, context: ToolExecutionContext
    ) -> ToolExecutionResult:
        started = perf_counter()
        try:
            if not isinstance(arguments, CodeReadInput):
                raise TypeError("code__read requires CodeReadInput")
            excerpt = await self._repository.read(
                arguments.path, start_line=arguments.start_line, end_line=arguments.end_line
            )
            output = CodeReadOutput(
                workspace=excerpt.workspace,
                revision=excerpt.revision,
                path=excerpt.path,
                start_line=excerpt.start_line,
                end_line=excerpt.end_line,
                content=excerpt.content,
            )
            summary = output.model_dump_json()
            if len(summary.encode("utf-8")) > context.max_output_bytes:
                raise ValueError("code excerpt exceeds tool output budget")
            evidence = EvidenceDraft(
                type="code_excerpt",
                source="local_code",
                source_reference=f"{excerpt.path}:{excerpt.start_line}-{excerpt.end_line}",
                content=excerpt.content,
                metadata={
                    "workspace": excerpt.workspace,
                    "revision": excerpt.revision,
                    "path": excerpt.path,
                    "start_line": excerpt.start_line,
                    "end_line": excerpt.end_line,
                },
            )
            return ToolExecutionResult(
                status=ToolExecutionStatus.SUCCESS,
                data=output,
                model_summary=summary,
                evidence_drafts=(evidence,),
                duration_ms=int((perf_counter() - started) * 1000),
            )
        except Exception as error:
            return ToolExecutionResult(
                status=ToolExecutionStatus.FAILED,
                data=None,
                model_summary='{"error":"code_read_failed"}',
                error_code=f"code_read_{type(error).__name__.lower()}",
                duration_ms=int((perf_counter() - started) * 1000),
            )
