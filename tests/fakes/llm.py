from collections import deque
from dataclasses import dataclass

from app_diagnosis.ports.llm import LLMClient, LLMRequest, LLMResponse


@dataclass(frozen=True, slots=True)
class RecordedLLMCall:
    request: LLMRequest


class FakeLLMClient(LLMClient):
    def __init__(self, responses: list[LLMResponse | Exception]) -> None:
        self._responses = deque(responses)
        self.calls: list[RecordedLLMCall] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(RecordedLLMCall(request=request))
        if not self._responses:
            raise AssertionError("FakeLLMClient has no queued response")
        result = self._responses.popleft()
        if isinstance(result, Exception):
            raise result
        return result
