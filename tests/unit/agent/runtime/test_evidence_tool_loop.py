from datetime import UTC, datetime
from uuid import UUID, uuid4

from tests.fakes.execution_repository import InMemoryAgentExecutionRepository
from tests.fakes.llm import FakeLLMClient

from app_diagnosis.agent.policies import EvidenceCitationPolicy
from app_diagnosis.agent.runtime import AgentBudget, ToolLoopContext, ToolLoopRunner
from app_diagnosis.agent.schemas import DiagnosisConclusion, DiagnosisFinding
from app_diagnosis.agent.strategies import GenericApplicationErrorStrategy
from app_diagnosis.domain.diagnosis import AgentTerminationReason, DiagnosisCase
from app_diagnosis.domain.evidence import (
    Evidence,
    EvidenceReliability,
    EvidenceSource,
    EvidenceType,
)
from app_diagnosis.ports.code_repository import CodeExcerpt, CodeMatch
from app_diagnosis.ports.evidence_store import EvidenceCandidate
from app_diagnosis.ports.knowledge_search import KnowledgeSearchMatch
from app_diagnosis.ports.llm import ChatMessage, FinishReason, LLMResponse, ToolCall
from app_diagnosis.tools import DiagnosticToolRegistry
from app_diagnosis.tools.code import CodeReadTool, CodeSearchTool
from app_diagnosis.tools.knowledge_search import KnowledgeSearchTool

NOW = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
DIAGNOSIS_ID = UUID("22222222-2222-2222-2222-222222222222")
EVIDENCE_ID = UUID("77777777-7777-7777-7777-777777777777")


class StubKnowledge:
    async def search(self, query: str, *, limit: int):
        return (
            KnowledgeSearchMatch(
                entry_id="npe",
                title="NPE",
                summary="Check first frame",
                matched_terms=("npe",),
                score=1.0,
                source="test",
            ),
        )


class StubCode:
    async def search(self, query: str, *, limit: int) -> tuple[CodeMatch, ...]:
        return (CodeMatch(path="OrderService.java", line=8, preview=query),)

    async def read(self, path: str, *, start_line: int, end_line: int) -> CodeExcerpt:
        return CodeExcerpt(
            workspace="test",
            revision="working-tree",
            path=path,
            start_line=start_line,
            end_line=end_line,
            content="return draft.getCustomer().trim();",
        )


class InMemoryEvidenceStore:
    def __init__(self, items: list[Evidence] | None = None) -> None:
        self.items: list[Evidence] = items or []

    async def add_candidates(
        self, diagnosis_id: UUID, candidates: tuple[EvidenceCandidate, ...]
    ) -> tuple[Evidence, ...]:
        created = tuple(
            Evidence.create(
                evidence_id=EVIDENCE_ID,
                diagnosis_id=diagnosis_id,
                type=EvidenceType(item.type),
                source=EvidenceSource(item.source),
                source_reference=item.source_reference,
                content=item.content,
                reliability=EvidenceReliability.MEDIUM,
                metadata=item.metadata,
                now=NOW,
            )
            for item in candidates
        )
        self.items.extend(created)
        return created

    async def list_by_diagnosis(self, diagnosis_id: UUID) -> tuple[Evidence, ...]:
        return tuple(item for item in self.items if item.diagnosis_id == diagnosis_id)


def response(
    *,
    content: str | None = None,
    tool_calls: tuple[ToolCall, ...] = (),
    finish_reason: FinishReason | None = None,
) -> LLMResponse:
    return LLMResponse(
        message=ChatMessage.assistant(content, tool_calls=tool_calls),
        model="fake",
        finish_reason=finish_reason
        or (FinishReason.TOOL_CALLS if tool_calls else FinishReason.STOP),
    )


def final(evidence_id: UUID) -> str:
    return DiagnosisConclusion(
        symptom_summary="HTTP 500",
        facts=[],
        root_causes=[
            DiagnosisFinding(
                statement="NPE is possible", status="possible", evidence_ids=[evidence_id]
            )
        ],
        recommendations=["Inspect the first application frame"],
        missing_information=[],
    ).model_dump_json()


def final_without_evidence() -> str:
    return DiagnosisConclusion(
        symptom_summary="HTTP 500",
        facts=[],
        root_causes=[
            DiagnosisFinding(
                statement="Runtime state still needs verification",
                status="possible",
                evidence_ids=[],
            )
        ],
        recommendations=["Capture the failing runtime value"],
        missing_information=[],
    ).model_dump_json()


def diagnosis() -> DiagnosisCase:
    item = DiagnosisCase.create(
        diagnosis_id=DIAGNOSIS_ID, title="Failure", symptom="HTTP 500", now=NOW
    )
    item.start_investigation(at=NOW)
    return item


async def test_tool_evidence_is_persisted_and_real_id_is_returned_to_model() -> None:
    call = ToolCall(id="call-1", name="knowledge__search", arguments_json='{"query":"NPE"}')
    fake = FakeLLMClient([response(tool_calls=(call,)), response(content=final(EVIDENCE_ID))])
    store = InMemoryEvidenceStore()
    registry = DiagnosticToolRegistry()
    registry.register(KnowledgeSearchTool(StubKnowledge()))
    runner = ToolLoopRunner(
        llm_client=fake,
        registry=registry,
        execution_repository=InMemoryAgentExecutionRepository(),
        evidence_store=store,
        citation_policy=EvidenceCitationPolicy(),
        clock=lambda: NOW,
    )
    result = await runner.run(
        diagnosis=diagnosis(),
        strategy=GenericApplicationErrorStrategy(),
        context=ToolLoopContext(
            actor="test",
            environment="test",
            audit_correlation_id="citation-1",
            permissions=frozenset({"knowledge:read"}),
            max_tool_output_bytes=4096,
        ),
        budget=AgentBudget(),
    )
    assert result.termination_reason is AgentTerminationReason.COMPLETED
    assert store.items[0].id == EVIDENCE_ID
    assert str(EVIDENCE_ID) in fake.calls[1].request.messages[-1].content


async def test_invalid_citation_gets_one_policy_correction() -> None:
    call = ToolCall(id="call-1", name="knowledge__search", arguments_json='{"query":"NPE"}')
    fake = FakeLLMClient(
        [
            response(tool_calls=(call,)),
            response(content=final(uuid4())),
            response(content=final(EVIDENCE_ID)),
        ]
    )
    store = InMemoryEvidenceStore()
    registry = DiagnosticToolRegistry()
    registry.register(KnowledgeSearchTool(StubKnowledge()))
    runner = ToolLoopRunner(
        llm_client=fake,
        registry=registry,
        execution_repository=InMemoryAgentExecutionRepository(),
        evidence_store=store,
        citation_policy=EvidenceCitationPolicy(),
        clock=lambda: NOW,
    )
    result = await runner.run(
        diagnosis=diagnosis(),
        strategy=GenericApplicationErrorStrategy(),
        context=ToolLoopContext(
            actor="test",
            environment="test",
            audit_correlation_id="citation-2",
            permissions=frozenset({"knowledge:read"}),
            max_tool_output_bytes=4096,
        ),
        budget=AgentBudget(),
    )
    assert result.termination_reason is AgentTerminationReason.COMPLETED
    assert "evidence citation rules" in fake.calls[2].request.messages[-1].content


async def test_existing_evidence_ids_are_available_on_first_model_call() -> None:
    existing_id = uuid4()
    existing = Evidence.create(
        evidence_id=existing_id,
        diagnosis_id=DIAGNOSIS_ID,
        type=EvidenceType.LOG_EXCERPT,
        source=EvidenceSource.USER_INPUT,
        source_reference="submitted_log:1/1",
        content="NullPointerException at OrderService.java:8",
        reliability=EvidenceReliability.HIGH,
        now=NOW,
    )
    fake = FakeLLMClient([response(content=final(existing_id))])
    registry = DiagnosticToolRegistry()
    registry.register(KnowledgeSearchTool(StubKnowledge()))
    runner = ToolLoopRunner(
        llm_client=fake,
        registry=registry,
        execution_repository=InMemoryAgentExecutionRepository(),
        evidence_store=InMemoryEvidenceStore([existing]),
        citation_policy=EvidenceCitationPolicy(),
        clock=lambda: NOW,
    )

    result = await runner.run(
        diagnosis=diagnosis(),
        strategy=GenericApplicationErrorStrategy(),
        context=ToolLoopContext(
            actor="test",
            environment="test",
            audit_correlation_id="existing-evidence",
            permissions=frozenset({"knowledge:read"}),
            max_tool_output_bytes=4096,
        ),
        budget=AgentBudget(),
    )

    assert result.termination_reason is AgentTerminationReason.COMPLETED
    first_user_message = fake.calls[0].request.messages[1].content or ""
    assert str(existing_id) in first_user_message
    assert '"type":"log_excerpt"' in first_user_message


async def test_successful_code_read_switches_next_request_to_finalization_mode() -> None:
    call = ToolCall(
        id="read-1",
        name="code__read",
        arguments_json='{"path":"OrderService.java","start_line":1,"end_line":20}',
    )
    fake = FakeLLMClient([response(tool_calls=(call,)), response(content=final(EVIDENCE_ID))])
    registry = DiagnosticToolRegistry()
    registry.register(KnowledgeSearchTool(StubKnowledge()))
    registry.register(CodeSearchTool(StubCode()))
    registry.register(CodeReadTool(StubCode()))
    runner = ToolLoopRunner(
        llm_client=fake,
        registry=registry,
        execution_repository=InMemoryAgentExecutionRepository(),
        evidence_store=InMemoryEvidenceStore(),
        citation_policy=EvidenceCitationPolicy(),
        clock=lambda: NOW,
    )

    result = await runner.run(
        diagnosis=diagnosis(),
        strategy=GenericApplicationErrorStrategy(code_tools_enabled=True),
        context=ToolLoopContext(
            actor="test",
            environment="test",
            audit_correlation_id="finalization",
            permissions=frozenset({"knowledge:read", "code:read"}),
            max_tool_output_bytes=4096,
        ),
        budget=AgentBudget(),
    )

    assert result.termination_reason is AgentTerminationReason.COMPLETED
    assert fake.calls[1].request.tools == ()
    assert "Do not call more tools" in (fake.calls[1].request.messages[-1].content or "")


async def test_length_response_gets_one_concise_tool_free_retry() -> None:
    fake = FakeLLMClient(
        [
            response(content="{", finish_reason=FinishReason.LENGTH),
            response(content=final_without_evidence()),
        ]
    )
    registry = DiagnosticToolRegistry()
    registry.register(KnowledgeSearchTool(StubKnowledge()))
    runner = ToolLoopRunner(
        llm_client=fake,
        registry=registry,
        execution_repository=InMemoryAgentExecutionRepository(),
        evidence_store=InMemoryEvidenceStore(),
        citation_policy=EvidenceCitationPolicy(),
        clock=lambda: NOW,
    )

    result = await runner.run(
        diagnosis=diagnosis(),
        strategy=GenericApplicationErrorStrategy(),
        context=ToolLoopContext(
            actor="test",
            environment="test",
            audit_correlation_id="length-retry",
            permissions=frozenset({"knowledge:read"}),
            max_tool_output_bytes=4096,
        ),
        budget=AgentBudget(),
    )

    assert result.termination_reason is AgentTerminationReason.COMPLETED
    assert fake.calls[1].request.tools == ()
    assert "at most 2 facts" in (fake.calls[1].request.messages[-1].content or "")


async def test_content_filter_is_not_retried() -> None:
    fake = FakeLLMClient([response(content="filtered", finish_reason=FinishReason.CONTENT_FILTER)])
    registry = DiagnosticToolRegistry()
    registry.register(KnowledgeSearchTool(StubKnowledge()))
    runner = ToolLoopRunner(
        llm_client=fake,
        registry=registry,
        execution_repository=InMemoryAgentExecutionRepository(),
        evidence_store=InMemoryEvidenceStore(),
        citation_policy=EvidenceCitationPolicy(),
        clock=lambda: NOW,
    )

    result = await runner.run(
        diagnosis=diagnosis(),
        strategy=GenericApplicationErrorStrategy(),
        context=ToolLoopContext(
            actor="test",
            environment="test",
            audit_correlation_id="content-filter",
            permissions=frozenset({"knowledge:read"}),
            max_tool_output_bytes=4096,
        ),
        budget=AgentBudget(),
    )

    assert result.termination_reason is AgentTerminationReason.INCONCLUSIVE
    assert len(fake.calls) == 1
