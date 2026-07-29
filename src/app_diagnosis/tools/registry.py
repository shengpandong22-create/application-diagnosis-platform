"""模型请求工具前必须经过的确定性闸门。"""

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
        """注册一个工具定义，并决定是否默认启用。

        Registry 只保存工具元数据和实例，不决定某次诊断能否使用该工具。
        单次运行的可见性仍由 Strategy allowlist、ProblemType 和权限共同决定。
        """
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
        """临时禁用已注册工具，但不删除工具定义。"""
        self._require_registered(name)
        self._enabled.discard(name)

    def enable(self, name: str) -> None:
        """重新启用已注册工具，后续仍需通过 Strategy 和权限校验。"""
        self._require_registered(name)
        self._enabled.add(name)

    def list(self) -> tuple[DiagnosticTool, ...]:
        """按稳定名称顺序返回所有已注册工具，便于测试和调试。"""
        return tuple(self._tools[name] for name in sorted(self._tools))

    def definitions(
        self,
        *,
        allowed_names: Collection[str],
        context: ToolExecutionContext,
    ) -> tuple[ToolDefinition, ...]:
        """向 LLM 暴露本轮真正允许使用的工具定义。

        这里会复用 resolve 校验，确保模型看见的工具已经通过启用状态、
        Strategy 白名单、ProblemType 和权限检查。
        """
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
        """解析一次工具调用，只有注册、启用、允许且有权限时才返回工具。

        这是防止模型越权调用工具的关键方法。后续新增高风险工具时，
        应优先在这里复用权限和 ProblemType 约束，而不是只靠 prompt 约束模型。
        """
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
        """用工具自己的 Pydantic 输入模型解析 LLM 参数。

        模型输出的 arguments_json 被视为不可信输入。只有通过 schema 校验后，
        才能进入具体工具执行逻辑。
        """
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
        """返回已注册工具；不存在时抛出工具注册表领域错误。"""
        try:
            return self._tools[name]
        except KeyError as error:
            raise UnknownTool(f"unknown tool: {name}") from error
