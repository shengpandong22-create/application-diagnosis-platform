from collections.abc import Callable

import pytest

from app_diagnosis.ports.llm import (
    ChatMessage,
    ChatRole,
    LLMCallOptions,
    LLMRequest,
    ToolCall,
    ToolDefinition,
)


def test_assistant_tool_calls_and_tool_result_preserve_protocol_ids() -> None:
    call = ToolCall(id="call-1", name="knowledge__search", arguments_json='{"q":"NPE"}')
    assistant = ChatMessage.assistant(None, tool_calls=(call,))
    result = ChatMessage.tool('{"matches":[]}', tool_call_id=call.id)

    assert assistant.role is ChatRole.ASSISTANT
    assert assistant.tool_calls == (call,)
    assert result.role is ChatRole.TOOL
    assert result.tool_call_id == "call-1"


@pytest.mark.parametrize(
    "message",
    [
        lambda: ChatMessage(role=ChatRole.USER),
        lambda: ChatMessage(role=ChatRole.ASSISTANT),
        lambda: ChatMessage(role=ChatRole.TOOL, content="result"),
        lambda: ChatMessage(
            role=ChatRole.SYSTEM,
            content="system",
            tool_call_id="invalid",
        ),
    ],
)
def test_message_role_invariants_are_enforced(message: Callable[[], ChatMessage]) -> None:
    with pytest.raises(ValueError):
        message()


def test_request_requires_messages() -> None:
    with pytest.raises(ValueError, match="at least one message"):
        LLMRequest(messages=())


def test_tool_schema_requires_object_root() -> None:
    with pytest.raises(ValueError, match="root type must be object"):
        ToolDefinition(name="tool", description="description", input_schema={"type": "string"})


@pytest.mark.parametrize(
    "arguments",
    [{"temperature": -0.1}, {"max_completion_tokens": 0}],
)
def test_call_options_are_bounded(arguments: dict) -> None:
    with pytest.raises(ValueError):
        LLMCallOptions(**arguments)
