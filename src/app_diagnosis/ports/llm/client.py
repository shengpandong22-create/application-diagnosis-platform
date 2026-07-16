from typing import Protocol

from app_diagnosis.ports.llm.types import LLMRequest, LLMResponse


class LLMClient(Protocol):
    async def complete(self, request: LLMRequest) -> LLMResponse: ...
