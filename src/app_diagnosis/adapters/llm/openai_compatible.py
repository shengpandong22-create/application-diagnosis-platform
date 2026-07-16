"""OpenAI-compatible Chat Completions adapter.

Design references:
- ITOps Agent Platform: llmService/toolCalling.ts and providerAdapters.ts
- OpenAI Chat Completions API reference

Reimplemented around the standalone LLMClient port. This module does not read ITOps
settings, repositories, execution records, or global circuit-breaker state.
"""

from collections.abc import Mapping
from typing import Any, Literal

import httpx

from app_diagnosis.ports.llm import (
    ChatMessage,
    ChatRole,
    FinishReason,
    LLMClient,
    LLMHTTPError,
    LLMProtocolError,
    LLMRequest,
    LLMResponse,
    LLMTimeoutError,
    LLMTransportError,
    LLMUsage,
    ToolCall,
)


class OpenAICompatibleChatClient(LLMClient):
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
        response_format_mode: Literal["json_schema", "json_object", "none"] = "json_schema",
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not base_url.strip():
            raise ValueError("base_url must not be blank")
        if not model.strip():
            raise ValueError("model must not be blank")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self._model = model
        self._api_key = api_key
        self._response_format_mode = response_format_mode
        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds))

    async def complete(self, request: LLMRequest) -> LLMResponse:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            response = await self._http_client.post(
                self._endpoint,
                headers=headers,
                json=self._serialize_request(request),
            )
        except httpx.TimeoutException as error:
            raise LLMTimeoutError("model request timed out") from error
        except httpx.RequestError as error:
            raise LLMTransportError("model endpoint could not be reached") from error

        if response.is_error:
            raise self._to_http_error(response)
        try:
            payload = response.json()
        except ValueError as error:
            raise LLMProtocolError("model endpoint returned non-JSON content") from error
        return self._parse_response(payload)

    async def aclose(self) -> None:
        if self._owns_http_client:
            await self._http_client.aclose()

    def _serialize_request(self, request: LLMRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [self._serialize_message(message) for message in request.messages],
        }
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.input_schema,
                    },
                }
                for tool in request.tools
            ]
        if request.response_format and self._response_format_mode == "json_schema":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": request.response_format.name,
                    "schema": request.response_format.schema,
                    "strict": request.response_format.strict,
                },
            }
        elif request.response_format and self._response_format_mode == "json_object":
            payload["response_format"] = {"type": "json_object"}
        if request.options.temperature is not None:
            payload["temperature"] = request.options.temperature
        if request.options.max_completion_tokens is not None:
            payload["max_completion_tokens"] = request.options.max_completion_tokens
        return payload

    @staticmethod
    def _serialize_message(message: ChatMessage) -> dict[str, Any]:
        payload: dict[str, Any] = {"role": message.role.value, "content": message.content}
        if message.role is ChatRole.ASSISTANT and message.tool_calls:
            payload["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": call.arguments_json,
                    },
                }
                for call in message.tool_calls
            ]
        if message.role is ChatRole.TOOL:
            payload["tool_call_id"] = message.tool_call_id
        return payload

    def _parse_response(self, payload: object) -> LLMResponse:
        if not isinstance(payload, Mapping):
            raise LLMProtocolError("model response root must be an object")
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMProtocolError("model response choices must be a non-empty array")
        choice = choices[0]
        if not isinstance(choice, Mapping):
            raise LLMProtocolError("model response choice must be an object")
        raw_message = choice.get("message")
        if not isinstance(raw_message, Mapping):
            raise LLMProtocolError("model response message must be an object")

        tool_calls = self._parse_tool_calls(raw_message.get("tool_calls"))
        content = raw_message.get("content")
        if content is not None and not isinstance(content, str):
            raise LLMProtocolError("assistant content must be a string or null")
        try:
            message = ChatMessage.assistant(content, tool_calls=tool_calls)
        except ValueError as error:
            raise LLMProtocolError(str(error)) from error

        model = payload.get("model", self._model)
        if not isinstance(model, str) or not model.strip():
            raise LLMProtocolError("model response model must be a non-empty string")
        response_id = payload.get("id")
        if response_id is not None and not isinstance(response_id, str):
            raise LLMProtocolError("model response id must be a string")
        return LLMResponse(
            message=message,
            model=model,
            finish_reason=self._parse_finish_reason(choice.get("finish_reason")),
            usage=self._parse_usage(payload.get("usage")),
            response_id=response_id,
        )

    @staticmethod
    def _parse_tool_calls(value: object) -> tuple[ToolCall, ...]:
        if value is None:
            return ()
        if not isinstance(value, list):
            raise LLMProtocolError("assistant tool_calls must be an array")
        parsed: list[ToolCall] = []
        for item in value:
            if not isinstance(item, Mapping) or item.get("type") != "function":
                raise LLMProtocolError("only function tool calls are supported")
            function = item.get("function")
            if not isinstance(function, Mapping):
                raise LLMProtocolError("tool call function must be an object")
            call_id = item.get("id")
            name = function.get("name")
            arguments = function.get("arguments")
            if not all(isinstance(part, str) for part in (call_id, name, arguments)):
                raise LLMProtocolError("tool call id, name, and arguments must be strings")
            parsed.append(ToolCall(id=call_id, name=name, arguments_json=arguments))
        return tuple(parsed)

    @staticmethod
    def _parse_finish_reason(value: object) -> FinishReason:
        if not isinstance(value, str):
            return FinishReason.OTHER
        try:
            return FinishReason(value)
        except ValueError:
            return FinishReason.OTHER

    @staticmethod
    def _parse_usage(value: object) -> LLMUsage:
        if not isinstance(value, Mapping):
            return LLMUsage()

        def token(name: str) -> int | None:
            raw = value.get(name)
            return raw if isinstance(raw, int) and not isinstance(raw, bool) else None

        return LLMUsage(
            input_tokens=token("prompt_tokens"),
            output_tokens=token("completion_tokens"),
            total_tokens=token("total_tokens"),
        )

    @staticmethod
    def _to_http_error(response: httpx.Response) -> LLMHTTPError:
        message = "request failed"
        try:
            payload = response.json()
            if isinstance(payload, Mapping):
                error = payload.get("error")
                if isinstance(error, Mapping) and isinstance(error.get("message"), str):
                    message = error["message"]
        except ValueError:
            pass
        return LLMHTTPError(response.status_code, message[:500])
