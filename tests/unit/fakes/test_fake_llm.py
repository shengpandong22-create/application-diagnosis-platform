import pytest
from tests.fakes.llm import FakeLLMClient

from app_diagnosis.ports.llm import (
    ChatMessage,
    FinishReason,
    LLMRequest,
    LLMResponse,
)


async def test_fake_returns_queued_responses_and_records_requests() -> None:
    response = LLMResponse(
        message=ChatMessage.assistant("done"),
        model="fake-model",
        finish_reason=FinishReason.STOP,
    )
    fake = FakeLLMClient([response])
    request = LLMRequest(messages=(ChatMessage.user("diagnose"),))

    assert await fake.complete(request) is response
    assert fake.calls[0].request is request

    with pytest.raises(AssertionError, match="no queued response"):
        await fake.complete(request)
