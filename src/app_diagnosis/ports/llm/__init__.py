"""Provider-neutral language model contracts."""

from app_diagnosis.ports.llm.client import LLMClient
from app_diagnosis.ports.llm.errors import (
    LLMError,
    LLMHTTPError,
    LLMProtocolError,
    LLMTimeoutError,
    LLMTransportError,
)
from app_diagnosis.ports.llm.types import (
    ChatMessage,
    ChatRole,
    FinishReason,
    LLMCallOptions,
    LLMRequest,
    LLMResponse,
    LLMUsage,
    ResponseFormat,
    ToolCall,
    ToolDefinition,
)

__all__ = [
    "ChatMessage",
    "ChatRole",
    "FinishReason",
    "LLMCallOptions",
    "LLMClient",
    "LLMError",
    "LLMHTTPError",
    "LLMProtocolError",
    "LLMRequest",
    "LLMResponse",
    "LLMTimeoutError",
    "LLMTransportError",
    "LLMUsage",
    "ResponseFormat",
    "ToolCall",
    "ToolDefinition",
]
