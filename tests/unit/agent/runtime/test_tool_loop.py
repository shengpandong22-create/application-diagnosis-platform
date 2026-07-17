import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from tests.fakes.execution_repository import InMemoryAgentExecutionRepository
from tests.fakes.llm import FakeLLMClient

from app_diagnosis.agent.runtime import AgentBudget, ToolLoopContext, ToolLoopRunner
from app_diagnosis.agent.schemas import DiagnosisConclusion
from app_diagnosis.agent.strategies import GenericApplicationErrorStrategy
from app_diagnosis.domain.diagnosis import AgentTerminationReason, DiagnosisCase
from app_diagnosis.domain.execution import AgentRunStatus, ToolRunStatus
from app_diagnosis.ports.knowledge_search import KnowledgeSearchMatch
from app_diagnosis.ports.llm import (
    ChatMessage,
    FinishReason,
    LLMProtocolError,
    LLMRequest,
    LLMResponse,
    LLMUsage,
    ToolCall,
)
from app_diagnosis.tools import DiagnosticToolRegistry
from app_diagnosis.tools.knowledge_search import KnowledgeSearchTool

NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
RUN_ID = UUID("55555555-5555-5555-5555-555555555555")


class StubKnowledge:
    async def search(self, query: str, *, limit: int) -> tuple[KnowledgeSearchMatch, ...]:
        return (
            KnowledgeSearchMatch(
                entry_id="generic-npe",
                title="NPE",
                summary="Check the first application stack frame.",
                matched_terms=("npe",),
                score=1.0,
                source="test",
            ),
        )


def ids() -> Iterator[UUID]:
    value = 0x55555555555555555555555555555555
    while True:
        yield UUID(int=value)
        value += 1


def diagnosis() -> DiagnosisCase:
    case = DiagnosisCase.create(
        diagnosis_id=UUID("22222222-2222-2222-2222-222222222222"),
        title="Payment API failure",
        symptom="HTTP 500",
        submitted_log="NullPointerException",
        now=NOW,
    )
    case.start_investigation(at=NOW)
    return case


def context() -> ToolLoopContext:
    return ToolLoopContext(
        actor="local-user",
        environment="local",
        audit_correlation_id="audit-1",
        permissions=frozenset({"knowledge:read"}),
        max_tool_output_bytes=4096,
    )


def conclusion_json() -> str:
    return DiagnosisConclusion(
        symptom_summary="Payment API returned HTTP 500.",
        facts=[],
        root_causes=[],
        recommendations=["Inspect the first application stack frame."],
        missing_information=[],
    ).model_dump_json()


def response(
    *,
    content: str | None = None,
    tool_calls: tuple[ToolCall, ...] = (),
) -> LLMResponse:
    return LLMResponse(
        message=ChatMessage.assistant(content, tool_calls=tool_calls),
        model="fake-model",
        finish_reason=FinishReason.TOOL_CALLS if tool_calls else FinishReason.STOP,
        usage=LLMUsage(input_tokens=10, output_tokens=5, total_tokens=15),
    )


def runner(
    llm: object,
    *,
    tool: KnowledgeSearchTool | None = None,
) -> tuple[ToolLoopRunner, InMemoryAgentExecutionRepository, FakeLLMClient | object]:
    registry = DiagnosticToolRegistry()
    registry.register(tool or KnowledgeSearchTool(StubKnowledge()))
    executions = InMemoryAgentExecutionRepository()
    sequence = ids()
    loop = ToolLoopRunner(
        llm_client=llm,  # type: ignore[arg-type]
        registry=registry,
        execution_repository=executions,
        id_factory=lambda: next(sequence),
        clock=lambda: NOW,
    )
    return loop, executions, llm


async def test_direct_structured_response_completes_without_tools() -> None:
    fake = FakeLLMClient([response(content=conclusion_json())])
    loop, executions, _ = runner(fake)

    result = await loop.run(
        diagnosis=diagnosis(),
        strategy=GenericApplicationErrorStrategy(),
        context=context(),
        budget=AgentBudget(),
    )

    run = executions.agent_runs[result.agent_run_id]
    assert result.termination_reason is AgentTerminationReason.COMPLETED
    assert result.conclusion is not None
    assert run.status is AgentRunStatus.COMPLETED
    assert run.round_count == 1
    assert run.tool_call_count == 0
    assert run.input_tokens == 10
    assert "symptom_summary" in fake.calls[0].request.messages[0].content
    assert "Final response must be one JSON object" in fake.calls[0].request.messages[0].content


async def test_tool_call_history_and_validated_arguments_are_recorded() -> None:
    call = ToolCall(
        id="call-1",
        name="knowledge__search",
        arguments_json='{"query":"NPE","limit":1}',
    )
    fake = FakeLLMClient([response(tool_calls=(call,)), response(content=conclusion_json())])
    loop, executions, _ = runner(fake)

    result = await loop.run(
        diagnosis=diagnosis(),
        strategy=GenericApplicationErrorStrategy(),
        context=context(),
        budget=AgentBudget(),
    )

    second_messages = fake.calls[1].request.messages
    assert second_messages[-2].tool_calls == (call,)
    assert second_messages[-1].tool_call_id == "call-1"
    assert executions.tool_runs[0].arguments_json == {"query": "NPE", "limit": 1}
    assert executions.tool_runs[0].status is ToolRunStatus.SUCCESS
    assert result.termination_reason is AgentTerminationReason.COMPLETED


async def test_same_round_multiple_tool_calls_are_all_executed() -> None:
    calls = (
        ToolCall(id="call-1", name="knowledge__search", arguments_json='{"query":"NPE"}'),
        ToolCall(
            id="call-2",
            name="knowledge__search",
            arguments_json='{"query":"HTTP 500"}',
        ),
    )
    fake = FakeLLMClient([response(tool_calls=calls), response(content=conclusion_json())])
    loop, executions, _ = runner(fake)

    result = await loop.run(
        diagnosis=diagnosis(),
        strategy=GenericApplicationErrorStrategy(),
        context=context(),
        budget=AgentBudget(),
    )

    assert [item.tool_call_id for item in executions.tool_runs] == ["call-1", "call-2"]
    assert executions.agent_runs[result.agent_run_id].tool_call_count == 2


async def test_invalid_arguments_are_not_persisted_and_all_failures_are_inconclusive() -> None:
    call = ToolCall(
        id="call-1",
        name="knowledge__search",
        arguments_json='{"limit":999}',
    )
    fake = FakeLLMClient([response(tool_calls=(call,)), response(content=conclusion_json())])
    loop, executions, _ = runner(fake)

    result = await loop.run(
        diagnosis=diagnosis(),
        strategy=GenericApplicationErrorStrategy(),
        context=context(),
        budget=AgentBudget(),
    )

    assert result.termination_reason is AgentTerminationReason.INCONCLUSIVE
    assert executions.tool_runs[0].arguments_json is None
    assert executions.tool_runs[0].status is ToolRunStatus.FAILED
    assert executions.agent_runs[result.agent_run_id].error_code == "all_tools_failed"


async def test_tool_budget_is_checked_before_execution() -> None:
    calls = (
        ToolCall(id="call-1", name="knowledge__search", arguments_json='{"query":"NPE"}'),
        ToolCall(id="call-2", name="knowledge__search", arguments_json='{"query":"500"}'),
    )
    fake = FakeLLMClient([response(tool_calls=calls)])
    loop, executions, _ = runner(fake)

    result = await loop.run(
        diagnosis=diagnosis(),
        strategy=GenericApplicationErrorStrategy(),
        context=context(),
        budget=AgentBudget(max_tool_calls=1),
    )

    assert result.termination_reason is AgentTerminationReason.TOOL_BUDGET_EXHAUSTED
    assert not executions.tool_runs


async def test_max_rounds_stops_after_a_completed_tool_round() -> None:
    call = ToolCall(
        id="call-1",
        name="knowledge__search",
        arguments_json='{"query":"NPE"}',
    )
    fake = FakeLLMClient([response(tool_calls=(call,))])
    loop, executions, _ = runner(fake)

    result = await loop.run(
        diagnosis=diagnosis(),
        strategy=GenericApplicationErrorStrategy(),
        context=context(),
        budget=AgentBudget(max_rounds=1),
    )

    assert result.termination_reason is AgentTerminationReason.MAX_ROUNDS_REACHED
    assert len(executions.tool_runs) == 1


async def test_partial_tool_failure_does_not_discard_successful_call() -> None:
    calls = (
        ToolCall(
            id="call-invalid",
            name="knowledge__search",
            arguments_json='{"limit":999}',
        ),
        ToolCall(
            id="call-valid",
            name="knowledge__search",
            arguments_json='{"query":"NPE"}',
        ),
    )
    fake = FakeLLMClient([response(tool_calls=calls), response(content=conclusion_json())])
    loop, executions, _ = runner(fake)

    result = await loop.run(
        diagnosis=diagnosis(),
        strategy=GenericApplicationErrorStrategy(),
        context=context(),
        budget=AgentBudget(),
    )

    assert result.termination_reason is AgentTerminationReason.COMPLETED
    assert [item.status for item in executions.tool_runs] == [
        ToolRunStatus.FAILED,
        ToolRunStatus.SUCCESS,
    ]


class SlowKnowledge:
    async def search(self, query: str, *, limit: int) -> tuple[KnowledgeSearchMatch, ...]:
        await asyncio.Event().wait()
        return ()


class FastTimeoutKnowledgeTool(KnowledgeSearchTool):
    timeout_seconds = 0.01


async def test_tool_timeout_is_recorded_and_returned_to_model() -> None:
    call = ToolCall(
        id="call-timeout",
        name="knowledge__search",
        arguments_json='{"query":"NPE"}',
    )
    fake = FakeLLMClient([response(tool_calls=(call,)), response(content=conclusion_json())])
    loop, executions, _ = runner(
        fake,
        tool=FastTimeoutKnowledgeTool(SlowKnowledge()),
    )

    result = await loop.run(
        diagnosis=diagnosis(),
        strategy=GenericApplicationErrorStrategy(),
        context=context(),
        budget=AgentBudget(),
    )

    assert result.termination_reason is AgentTerminationReason.INCONCLUSIVE
    assert executions.tool_runs[0].status is ToolRunStatus.TIMEOUT
    assert executions.tool_runs[0].error_code == "tool_timeout"
    assert "tool_timeout" in fake.calls[1].request.messages[-1].content


async def test_invalid_structured_output_gets_one_correction_attempt() -> None:
    fake = FakeLLMClient([response(content="not json"), response(content=conclusion_json())])
    loop, executions, _ = runner(fake)

    result = await loop.run(
        diagnosis=diagnosis(),
        strategy=GenericApplicationErrorStrategy(),
        context=context(),
        budget=AgentBudget(),
    )

    assert result.termination_reason is AgentTerminationReason.COMPLETED
    assert "required JSON schema" in fake.calls[1].request.messages[-1].content
    assert executions.agent_runs[result.agent_run_id].round_count == 2


async def test_second_invalid_structured_output_is_inconclusive() -> None:
    fake = FakeLLMClient([response(content="bad"), response(content="still bad")])
    loop, executions, _ = runner(fake)

    result = await loop.run(
        diagnosis=diagnosis(),
        strategy=GenericApplicationErrorStrategy(),
        context=context(),
        budget=AgentBudget(),
    )

    assert result.termination_reason is AgentTerminationReason.INCONCLUSIVE
    assert executions.agent_runs[result.agent_run_id].error_code == "invalid_structured_output"


@pytest.mark.parametrize("finish_reason", [FinishReason.LENGTH, FinishReason.CONTENT_FILTER])
async def test_incomplete_model_finish_reason_cannot_complete_diagnosis(
    finish_reason: FinishReason,
) -> None:
    incomplete = LLMResponse(
        message=ChatMessage.assistant(conclusion_json()),
        model="fake-model",
        finish_reason=finish_reason,
    )
    responses = [incomplete, incomplete] if finish_reason is FinishReason.LENGTH else [incomplete]
    fake = FakeLLMClient(responses)
    loop, executions, _ = runner(fake)

    result = await loop.run(
        diagnosis=diagnosis(),
        strategy=GenericApplicationErrorStrategy(),
        context=context(),
        budget=AgentBudget(),
    )

    assert result.termination_reason is AgentTerminationReason.INCONCLUSIVE
    assert executions.agent_runs[result.agent_run_id].error_code == (
        f"model_finish_{finish_reason.value}"
    )


async def test_model_error_has_typed_termination() -> None:
    fake = FakeLLMClient([LLMProtocolError("invalid")])
    loop, executions, _ = runner(fake)

    result = await loop.run(
        diagnosis=diagnosis(),
        strategy=GenericApplicationErrorStrategy(),
        context=context(),
        budget=AgentBudget(),
    )

    assert result.termination_reason is AgentTerminationReason.MODEL_ERROR
    assert executions.agent_runs[result.agent_run_id].status is AgentRunStatus.FAILED
    assert executions.agent_runs[result.agent_run_id].error_code == "LLMProtocolError"


class HangingLLM:
    async def complete(self, request: LLMRequest) -> LLMResponse:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


async def test_total_timeout_stops_hanging_model_call() -> None:
    loop, executions, _ = runner(HangingLLM())

    result = await loop.run(
        diagnosis=diagnosis(),
        strategy=GenericApplicationErrorStrategy(),
        context=context(),
        budget=AgentBudget(total_timeout_seconds=0.01),
    )

    assert result.termination_reason is AgentTerminationReason.TIME_BUDGET_EXHAUSTED
    assert executions.agent_runs[result.agent_run_id].status is AgentRunStatus.COMPLETED


async def test_cancellation_is_persisted_and_propagated() -> None:
    loop, executions, _ = runner(HangingLLM())
    task = asyncio.create_task(
        loop.run(
            diagnosis=diagnosis(),
            strategy=GenericApplicationErrorStrategy(),
            context=context(),
            budget=AgentBudget(),
        )
    )
    await asyncio.sleep(0)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    stored = next(iter(executions.agent_runs.values()))
    assert stored.status is AgentRunStatus.CANCELLED
    assert stored.termination_reason is AgentTerminationReason.CANCELLED
