import json
import re
from collections.abc import Collection

from pydantic import BaseModel, ValidationError

from app_diagnosis.ports.llm import ToolDefinition
from app_diagnosis.tools.contracts import DiagnosticTool, ToolExecutionContext
from app_diagnosis.tools.errors import (
    DisabledTool,
    DuplicateToolName,
    ToolArgumentError,
    ToolNotAllowed,
    ToolPermissionDenied,
    UnknownTool,
)

_TOOL_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class DiagnosticToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, DiagnosticTool] = {}
        self._enabled: set[str] = set()

    def register(self, tool: DiagnosticTool, *, enabled: bool = True) -> None:
        if not _TOOL_NAME.fullmatch(tool.name):
            raise ValueError(f"invalid tool name: {tool.name!r}")
        if tool.name in self._tools:
            raise DuplicateToolName(f"tool is already registered: {tool.name}")
        if tool.timeout_seconds <= 0:
            raise ValueError("tool timeout must be positive")
        self._tools[tool.name] = tool
        if enabled:
            self._enabled.add(tool.name)

    def disable(self, name: str) -> None:
        self._require_registered(name)
        self._enabled.discard(name)

    def enable(self, name: str) -> None:
        self._require_registered(name)
        self._enabled.add(name)

    def list(self) -> tuple[DiagnosticTool, ...]:
        return tuple(self._tools[name] for name in sorted(self._tools))

    def definitions(
        self,
        *,
        allowed_names: Collection[str],
        context: ToolExecutionContext,
    ) -> tuple[ToolDefinition, ...]:
        return tuple(
            ToolDefinition(
                name=tool.name,
                description=tool.description,
                input_schema=tool.input_model.model_json_schema(),
            )
            for name in sorted(set(allowed_names))
            for tool in (self.resolve(name, allowed_names=allowed_names, context=context),)
        )

    def resolve(
        self,
        name: str,
        *,
        allowed_names: Collection[str],
        context: ToolExecutionContext,
    ) -> DiagnosticTool:
        tool = self._require_registered(name)
        if name not in self._enabled:
            raise DisabledTool(f"tool is disabled: {name}")
        if name not in allowed_names:
            raise ToolNotAllowed(f"tool is not allowed by the diagnosis strategy: {name}")
        if context.problem_type not in tool.supported_problem_types:
            raise ToolNotAllowed(f"tool does not support problem type: {name}")
        missing = tool.required_permissions - context.permissions
        if missing:
            raise ToolPermissionDenied(
                f"tool permission denied: {name}; missing={','.join(sorted(missing))}"
            )
        return tool

    @staticmethod
    def parse_arguments(tool: DiagnosticTool, arguments_json: str) -> BaseModel:
        try:
            value = json.loads(arguments_json)
        except json.JSONDecodeError as error:
            raise ToolArgumentError("tool arguments are not valid JSON") from error
        if not isinstance(value, dict):
            raise ToolArgumentError("tool arguments must be a JSON object")
        try:
            return tool.input_model.model_validate(value)
        except ValidationError as error:
            fields = sorted(
                {".".join(str(part) for part in item["loc"]) for item in error.errors()}
            )
            detail = ",".join(fields) or "root"
            raise ToolArgumentError(f"tool arguments failed schema validation: {detail}") from error

    def _require_registered(self, name: str) -> DiagnosticTool:
        try:
            return self._tools[name]
        except KeyError as error:
            raise UnknownTool(f"unknown tool: {name}") from error
