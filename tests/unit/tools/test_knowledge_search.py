from datetime import UTC, datetime, timedelta
from uuid import UUID

from app_diagnosis.domain.diagnosis import ProblemType
from app_diagnosis.ports.knowledge_search import KnowledgeSearchMatch
from app_diagnosis.tools.contracts import ToolExecutionContext, ToolExecutionStatus
from app_diagnosis.tools.knowledge_search import KnowledgeSearchInput, KnowledgeSearchTool


class StubSearch:
    async def search(self, query: str, *, limit: int) -> tuple[KnowledgeSearchMatch, ...]:
        return tuple(
            KnowledgeSearchMatch(
                entry_id=f"entry-{index}",
                title=f"Match {index}",
                summary="A" * 200,
                matched_terms=(query.casefold(),),
                score=0.8,
                source="test",
            )
            for index in range(limit)
        )


def context(*, max_output_bytes: int = 4096) -> ToolExecutionContext:
    return ToolExecutionContext(
        diagnosis_id=UUID("33333333-3333-3333-3333-333333333333"),
        agent_run_id=UUID("44444444-4444-4444-4444-444444444444"),
        actor="local-user",
        environment="local",
        deadline=datetime.now(UTC) + timedelta(minutes=1),
        audit_correlation_id="audit-1",
        permissions=frozenset({"knowledge:read"}),
        problem_type=ProblemType.GENERIC_APPLICATION_ERROR,
        max_output_bytes=max_output_bytes,
    )


async def test_tool_returns_structured_matches_and_evidence_drafts() -> None:
    tool = KnowledgeSearchTool(StubSearch())

    result = await tool.execute(KnowledgeSearchInput(query="NPE", limit=2), context())

    assert result.status is ToolExecutionStatus.SUCCESS
    assert len(result.data.matches) == 2
    assert [draft.source_reference for draft in result.evidence_drafts] == [
        "entry-0",
        "entry-1",
    ]
    assert len(result.model_summary.encode("utf-8")) <= 4096


async def test_tool_drops_low_ranked_matches_to_fit_output_budget() -> None:
    tool = KnowledgeSearchTool(StubSearch())

    result = await tool.execute(
        KnowledgeSearchInput(query="NPE", limit=10),
        context(max_output_bytes=500),
    )

    assert result.status is ToolExecutionStatus.SUCCESS
    assert result.truncated
    assert len(result.data.matches) < 10
    assert len(result.model_summary.encode("utf-8")) <= 500


class FailingSearch:
    async def search(self, query: str, *, limit: int) -> tuple:
        raise OSError("secret filesystem details")


async def test_tool_failure_returns_safe_typed_result() -> None:
    result = await KnowledgeSearchTool(FailingSearch()).execute(
        KnowledgeSearchInput(query="NPE"),
        context(),
    )

    assert result.status is ToolExecutionStatus.FAILED
    assert result.error_code == "knowledge_search_oserror"
    assert "secret" not in result.model_summary
