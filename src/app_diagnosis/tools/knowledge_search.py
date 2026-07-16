from time import perf_counter

from pydantic import BaseModel, ConfigDict, Field

from app_diagnosis.domain.diagnosis import ProblemType
from app_diagnosis.ports.knowledge_search import KnowledgeSearchPort
from app_diagnosis.tools.contracts import (
    EvidenceDraft,
    ToolExecutionContext,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolRiskLevel,
)


class KnowledgeSearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=300)
    limit: int = Field(default=5, ge=1, le=10)


class KnowledgeMatchOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: str
    title: str
    summary: str
    matched_terms: list[str]
    score: float = Field(ge=0, le=1)
    source: str


class KnowledgeSearchOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    matches: list[KnowledgeMatchOutput]


class KnowledgeSearchTool:
    name = "knowledge__search"
    description = "Search confirmed local diagnostic knowledge and return explained matches."
    input_model = KnowledgeSearchInput
    output_model = KnowledgeSearchOutput
    risk_level = ToolRiskLevel.READ_ONLY
    timeout_seconds = 2.0
    required_permissions = frozenset({"knowledge:read"})
    supported_problem_types = frozenset({ProblemType.GENERIC_APPLICATION_ERROR})

    def __init__(self, search: KnowledgeSearchPort) -> None:
        self._search = search

    async def execute(
        self,
        arguments: BaseModel,
        context: ToolExecutionContext,
    ) -> ToolExecutionResult:
        if not isinstance(arguments, KnowledgeSearchInput):
            raise TypeError("knowledge__search requires KnowledgeSearchInput")
        started = perf_counter()
        try:
            found = await self._search.search(arguments.query, limit=arguments.limit)
            output = KnowledgeSearchOutput(
                matches=[
                    KnowledgeMatchOutput(
                        entry_id=match.entry_id,
                        title=match.title,
                        summary=match.summary,
                        matched_terms=list(match.matched_terms),
                        score=match.score,
                        source=match.source,
                    )
                    for match in found
                ]
            )
            output, summary, truncated = self._fit_output(output, context.max_output_bytes)
            evidence = tuple(
                EvidenceDraft(
                    type="knowledge_entry",
                    source="local_knowledge",
                    source_reference=match.entry_id,
                    content=match.summary,
                    metadata={"score": match.score, "matched_terms": match.matched_terms},
                )
                for match in output.matches
            )
            return ToolExecutionResult(
                status=ToolExecutionStatus.SUCCESS,
                data=output,
                model_summary=summary,
                evidence_drafts=evidence,
                duration_ms=int((perf_counter() - started) * 1000),
                truncated=truncated,
            )
        except Exception as error:
            return ToolExecutionResult(
                status=ToolExecutionStatus.FAILED,
                data=None,
                model_summary="Knowledge search failed.",
                error_code=f"knowledge_search_{type(error).__name__.lower()}",
                retryable=False,
                duration_ms=int((perf_counter() - started) * 1000),
            )

    @staticmethod
    def _fit_output(
        output: KnowledgeSearchOutput,
        max_bytes: int,
    ) -> tuple[KnowledgeSearchOutput, str, bool]:
        matches = list(output.matches)
        summary = output.model_dump_json()
        while matches and len(summary.encode("utf-8")) > max_bytes:
            matches.pop()
            summary = KnowledgeSearchOutput(matches=matches).model_dump_json()
        if len(summary.encode("utf-8")) > max_bytes:
            summary = '{"matches":[]}'
        fitted = KnowledgeSearchOutput(matches=matches)
        return fitted, summary, len(matches) != len(output.matches)
