import json

import httpx
import pytest

from app_diagnosis.adapters.llm import OpenAICompatibleChatClient
from app_diagnosis.ports.llm import (
    ChatMessage,
    FinishReason,
    LLMCallOptions,
    LLMHTTPError,
    LLMProtocolError,
    LLMRequest,
    LLMTimeoutError,
    ResponseFormat,
    ToolCall,
    ToolDefinition,
)


def response_payload(*, message: dict[str, object], finish_reason: str = "stop") -> dict:
    return {
        "id": "chatcmpl-1",
        "model": "test-model-2026",
        "choices": [{"index": 0, "finish_reason": finish_reason, "message": message}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


async def test_serializes_complete_tool_history_and_parses_multiple_calls() -> None:
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json=response_payload(
                finish_reason="tool_calls",
                message={
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call-2",
                            "type": "function",
                            "function": {
                                "name": "knowledge__search",
                                "arguments": '{"query":"timeout"}',
                            },
                        },
                        {
                            "id": "call-3",
                            "type": "function",
                            "function": {
                                "name": "knowledge__search",
                                "arguments": '{"query":"connection"}',
                            },
                        },
                    ],
                },
            ),
        )

    prior_call = ToolCall(
        id="call-1",
        name="knowledge__search",
        arguments_json='{"query":"NPE"}',
    )
    request = LLMRequest(
        messages=(
            ChatMessage.system("diagnose"),
            ChatMessage.user("HTTP 500"),
            ChatMessage.assistant(None, tool_calls=(prior_call,)),
            ChatMessage.tool('{"matches":[]}', tool_call_id="call-1"),
        ),
        tools=(
            ToolDefinition(
                name="knowledge__search",
                description="Search confirmed knowledge",
                input_schema={"type": "object", "properties": {}},
            ),
        ),
        response_format=ResponseFormat(
            name="diagnosis",
            schema={"type": "object", "properties": {}},
        ),
        options=LLMCallOptions(temperature=0.2, max_completion_tokens=500),
    )
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OpenAICompatibleChatClient(
        base_url="https://model.example/v1",
        api_key="secret-key",
        model="test-model",
        timeout_seconds=10,
        http_client=http_client,
    )

    result = await client.complete(request)
    await http_client.aclose()

    assert captured["messages"][2]["tool_calls"][0]["id"] == "call-1"
    assert captured["messages"][3]["tool_call_id"] == "call-1"
    assert captured["tools"][0]["function"]["name"] == "knowledge__search"
    assert captured["response_format"]["json_schema"]["strict"] is True
    assert captured["max_completion_tokens"] == 500
    assert result.finish_reason is FinishReason.TOOL_CALLS
    assert [call.id for call in result.message.tool_calls] == ["call-2", "call-3"]
    assert result.usage.total_tokens == 15


async def test_json_object_mode_downgrades_structured_response_format() -> None:
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json=response_payload(message={"role": "assistant", "content": "{}"}),
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OpenAICompatibleChatClient(
        base_url="https://api.deepseek.com",
        api_key="secret-key",
        model="deepseek-v4-pro",
        timeout_seconds=10,
        response_format_mode="json_object",
        http_client=http_client,
    )
    await client.complete(
        LLMRequest(
            messages=(ChatMessage.user("Return JSON"),),
            response_format=ResponseFormat(
                name="diagnosis",
                schema={"type": "object", "properties": {}},
            ),
        )
    )
    await http_client.aclose()

    assert captured["response_format"] == {"type": "json_object"}


async def test_parses_plain_assistant_response() -> None:
    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            200,
            json=response_payload(message={"role": "assistant", "content": "analysis"}),
        )
    )
    http_client = httpx.AsyncClient(transport=transport)
    client = OpenAICompatibleChatClient(
        base_url="https://model.example/v1",
        api_key="",
        model="test-model",
        timeout_seconds=10,
        http_client=http_client,
    )

    result = await client.complete(LLMRequest(messages=(ChatMessage.user("diagnose"),)))
    await http_client.aclose()

    assert result.message.content == "analysis"
    assert result.finish_reason is FinishReason.STOP


async def test_http_error_is_typed_and_does_not_include_api_key() -> None:
    transport = httpx.MockTransport(
        lambda _: httpx.Response(429, json={"error": {"message": "rate limited"}})
    )
    http_client = httpx.AsyncClient(transport=transport)
    client = OpenAICompatibleChatClient(
        base_url="https://model.example/v1",
        api_key="top-secret",
        model="test-model",
        timeout_seconds=10,
        http_client=http_client,
    )

    with pytest.raises(LLMHTTPError) as error:
        await client.complete(LLMRequest(messages=(ChatMessage.user("diagnose"),)))
    await http_client.aclose()

    assert error.value.status_code == 429
    assert error.value.retryable
    assert "top-secret" not in str(error.value)


async def test_timeout_is_translated() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(timeout))
    client = OpenAICompatibleChatClient(
        base_url="https://model.example/v1",
        api_key="",
        model="test-model",
        timeout_seconds=10,
        http_client=http_client,
    )

    with pytest.raises(LLMTimeoutError):
        await client.complete(LLMRequest(messages=(ChatMessage.user("diagnose"),)))
    await http_client.aclose()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"choices": []},
        {"choices": [{"message": {"role": "assistant", "content": None}}]},
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{"id": "call-1", "type": "custom"}],
                    }
                }
            ]
        },
    ],
)
async def test_invalid_response_is_rejected(payload: dict) -> None:
    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    )
    client = OpenAICompatibleChatClient(
        base_url="https://model.example/v1",
        api_key="",
        model="test-model",
        timeout_seconds=10,
        http_client=http_client,
    )

    with pytest.raises(LLMProtocolError):
        await client.complete(LLMRequest(messages=(ChatMessage.user("diagnose"),)))
    await http_client.aclose()
