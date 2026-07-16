import pytest
from pydantic import ValidationError

from app_diagnosis.agent.schemas import DiagnosisConclusion
from app_diagnosis.tools.errors import ToolArgumentError
from app_diagnosis.tools.knowledge_search import KnowledgeSearchTool
from app_diagnosis.tools.registry import DiagnosticToolRegistry


class EmptySearch:
    async def search(self, query: str, *, limit: int) -> tuple:
        return ()


def test_tool_arguments_reject_hallucinated_fields() -> None:
    tool = KnowledgeSearchTool(EmptySearch())

    with pytest.raises(ToolArgumentError):
        DiagnosticToolRegistry.parse_arguments(
            tool,
            '{"query":"NPE","unexpected":"must not be ignored"}',
        )


def test_conclusion_rejects_fields_outside_contract() -> None:
    with pytest.raises(ValidationError):
        DiagnosisConclusion.model_validate(
            {
                "symptom_summary": "HTTP 500",
                "facts": [],
                "root_causes": [],
                "recommendations": [],
                "missing_information": [],
                "unexpected": "must not be ignored",
            }
        )
