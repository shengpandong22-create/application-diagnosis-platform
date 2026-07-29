from datetime import UTC, datetime
from uuid import UUID

from app_diagnosis.agent.strategies import GenericApplicationErrorStrategy
from app_diagnosis.domain.diagnosis import DiagnosisCase
from app_diagnosis.domain.diagnosis_plan import DiagnosisPlanStatus
from app_diagnosis.domain.diagnosis_plan.models import DiagnosisPlan


def test_rule_based_plan_explains_allowed_tools_without_changing_execution() -> None:
    diagnosis = DiagnosisCase.create(
        diagnosis_id=UUID("11111111-1111-1111-1111-111111111111"),
        title="Checkout NPE",
        symptom="HTTP 500",
        submitted_log="NullPointerException",
        now=datetime(2026, 7, 29, 10, 0, tzinfo=UTC),
    )
    plan = DiagnosisPlan.create_rule_based(
        diagnosis=diagnosis,
        agent_run_id=UUID("22222222-2222-2222-2222-222222222222"),
        strategy=GenericApplicationErrorStrategy(),
        allowed_tools=frozenset({"knowledge__search", "code__search", "code__read"}),
        now=datetime(2026, 7, 29, 10, 1, tzinfo=UTC),
    )

    assert plan.status is DiagnosisPlanStatus.PLANNED
    assert plan.allowed_tools == ("code__read", "code__search", "knowledge__search")
    assert plan.steps[0].tool_name is None
    assert [item.tool_name for item in plan.steps if item.tool_name] == [
        "knowledge__search",
        "code__search",
        "code__read",
    ]
    assert "code_excerpt" in plan.expected_evidence
    assert any("知识库" in item for item in plan.hypotheses)
