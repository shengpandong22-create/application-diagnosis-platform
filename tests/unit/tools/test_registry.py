from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app_diagnosis.domain.diagnosis import ProblemType
from app_diagnosis.tools.contracts import ToolExecutionContext
from app_diagnosis.tools.errors import (
    DisabledTool,
    DuplicateToolName,
    ToolArgumentError,
    ToolNotAllowed,
    ToolPermissionDenied,
    UnknownTool,
)
from app_diagnosis.tools.knowledge_search import KnowledgeSearchTool
from app_diagnosis.tools.registry import DiagnosticToolRegistry


class EmptySearch:
    async def search(self, query: str, *, limit: int) -> tuple:
        return ()


def context(*, permissions: frozenset[str] = frozenset({"knowledge:read"})) -> ToolExecutionContext:
    return ToolExecutionContext(
        diagnosis_id=UUID("33333333-3333-3333-3333-333333333333"),
        agent_run_id=UUID("44444444-4444-4444-4444-444444444444"),
        actor="local-user",
        environment="local",
        deadline=datetime.now(UTC) + timedelta(minutes=1),
        audit_correlation_id="audit-1",
        permissions=permissions,
        problem_type=ProblemType.GENERIC_APPLICATION_ERROR,
        max_output_bytes=4096,
    )


def registry_with_tool() -> tuple[DiagnosticToolRegistry, KnowledgeSearchTool]:
    registry = DiagnosticToolRegistry()
    tool = KnowledgeSearchTool(EmptySearch())
    registry.register(tool)
    return registry, tool


def test_duplicate_registration_fails() -> None:
    registry, tool = registry_with_tool()

    with pytest.raises(DuplicateToolName):
        registry.register(tool)


def test_unknown_disabled_and_disallowed_tools_cannot_be_resolved() -> None:
    registry, _ = registry_with_tool()

    with pytest.raises(UnknownTool):
        registry.resolve("missing", allowed_names={"missing"}, context=context())
    with pytest.raises(ToolNotAllowed):
        registry.resolve("knowledge__search", allowed_names=set(), context=context())
    registry.disable("knowledge__search")
    with pytest.raises(DisabledTool):
        registry.resolve(
            "knowledge__search",
            allowed_names={"knowledge__search"},
            context=context(),
        )


def test_missing_permission_is_rejected() -> None:
    registry, _ = registry_with_tool()

    with pytest.raises(ToolPermissionDenied, match="knowledge:read"):
        registry.resolve(
            "knowledge__search",
            allowed_names={"knowledge__search"},
            context=context(permissions=frozenset()),
        )


def test_definitions_are_generated_from_pydantic_schema() -> None:
    registry, _ = registry_with_tool()

    definitions = registry.definitions(
        allowed_names={"knowledge__search"},
        context=context(),
    )

    assert definitions[0].name == "knowledge__search"
    assert definitions[0].input_schema["type"] == "object"
    assert definitions[0].input_schema["properties"]["limit"]["maximum"] == 10


@pytest.mark.parametrize(
    "raw",
    ["not-json", "[]", "{}", '{"query":"x","limit":99}'],
)
def test_invalid_arguments_are_rejected_without_echoing_values(raw: str) -> None:
    registry, tool = registry_with_tool()

    with pytest.raises(ToolArgumentError) as error:
        registry.parse_arguments(tool, raw)

    assert raw not in str(error.value)


def test_valid_arguments_are_typed() -> None:
    registry, tool = registry_with_tool()

    parsed = registry.parse_arguments(tool, '{"query":"NPE"}')

    assert parsed.query == "NPE"
    assert parsed.limit == 5
