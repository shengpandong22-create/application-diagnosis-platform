from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ChatRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class FinishReason(StrEnum):
    STOP = "stop"
    LENGTH = "length"
    TOOL_CALLS = "tool_calls"
    CONTENT_FILTER = "content_filter"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments_json: str

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("tool call id must not be blank")
        if not self.name.strip():
            raise ValueError("tool call name must not be blank")


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: ChatRole
    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None

    def __post_init__(self) -> None:
        if self.role in {ChatRole.SYSTEM, ChatRole.USER}:
            if self.content is None:
                raise ValueError(f"{self.role.value} message requires content")
            if self.tool_calls or self.tool_call_id:
                raise ValueError(f"{self.role.value} message cannot contain tool metadata")
        elif self.role is ChatRole.ASSISTANT:
            if self.content is None and not self.tool_calls:
                raise ValueError("assistant message requires content or tool calls")
            if self.tool_call_id:
                raise ValueError("assistant message cannot contain tool_call_id")
        elif self.role is ChatRole.TOOL:
            if self.content is None:
                raise ValueError("tool message requires content")
            if not self.tool_call_id or not self.tool_call_id.strip():
                raise ValueError("tool message requires tool_call_id")
            if self.tool_calls:
                raise ValueError("tool message cannot contain tool_calls")

    @classmethod
    def system(cls, content: str) -> "ChatMessage":
        return cls(role=ChatRole.SYSTEM, content=content)

    @classmethod
    def user(cls, content: str) -> "ChatMessage":
        return cls(role=ChatRole.USER, content=content)

    @classmethod
    def assistant(
        cls,
        content: str | None,
        *,
        tool_calls: tuple[ToolCall, ...] = (),
    ) -> "ChatMessage":
        return cls(role=ChatRole.ASSISTANT, content=content, tool_calls=tool_calls)

    @classmethod
    def tool(cls, content: str, *, tool_call_id: str) -> "ChatMessage":
        return cls(role=ChatRole.TOOL, content=content, tool_call_id=tool_call_id)


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("tool name must not be blank")
        if not self.description.strip():
            raise ValueError("tool description must not be blank")
        if self.input_schema.get("type") != "object":
            raise ValueError("tool input schema root type must be object")


@dataclass(frozen=True, slots=True)
class ResponseFormat:
    name: str
    schema: dict[str, Any]
    strict: bool = True

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("response format name must not be blank")
        if self.schema.get("type") != "object":
            raise ValueError("response format schema root type must be object")


@dataclass(frozen=True, slots=True)
class LLMCallOptions:
    temperature: float | None = None
    max_completion_tokens: int | None = None
    parallel_tool_calls: bool | None = None

    def __post_init__(self) -> None:
        if self.temperature is not None and not 0 <= self.temperature <= 2:
            raise ValueError("temperature must be between 0 and 2")
        if self.max_completion_tokens is not None and self.max_completion_tokens <= 0:
            raise ValueError("max_completion_tokens must be positive")


@dataclass(frozen=True, slots=True)
class LLMRequest:
    messages: tuple[ChatMessage, ...]
    tools: tuple[ToolDefinition, ...] = ()
    response_format: ResponseFormat | None = None
    options: LLMCallOptions = field(default_factory=LLMCallOptions)

    def __post_init__(self) -> None:
        if not self.messages:
            raise ValueError("LLM request requires at least one message")


@dataclass(frozen=True, slots=True)
class LLMUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    def __post_init__(self) -> None:
        values = (self.input_tokens, self.output_tokens, self.total_tokens)
        if any(value is not None and value < 0 for value in values):
            raise ValueError("token usage must not be negative")


@dataclass(frozen=True, slots=True)
class LLMResponse:
    message: ChatMessage
    model: str
    finish_reason: FinishReason
    usage: LLMUsage = field(default_factory=LLMUsage)
    response_id: str | None = None

    def __post_init__(self) -> None:
        if self.message.role is not ChatRole.ASSISTANT:
            raise ValueError("LLM response message must have assistant role")
        if not self.model.strip():
            raise ValueError("LLM response model must not be blank")
