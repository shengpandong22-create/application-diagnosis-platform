from datetime import UTC, datetime

from app_diagnosis.agent.strategies.base import DiagnosisStrategyContext
from app_diagnosis.agent.strategies.generic_application_error import (
    GenericApplicationErrorStrategy,
)
from app_diagnosis.domain.diagnosis import DiagnosisCase


def _diagnosis() -> DiagnosisCase:
    return DiagnosisCase.create(
        title="HTTP 500",
        symptom="java.lang.NullPointerException",
        submitted_log=None,
        now=datetime(2026, 7, 29, tzinfo=UTC),
    )


def test_strategy_exposes_service_scoped_tools_only_when_available() -> None:
    strategy = GenericApplicationErrorStrategy()

    without_service_tools = strategy.allowed_tool_names(
        DiagnosisStrategyContext(diagnosis=_diagnosis())
    )
    with_service_tools = strategy.allowed_tool_names(
        DiagnosisStrategyContext(
            diagnosis=_diagnosis(),
            available_tool_names=frozenset(
                {
                    "knowledge__search",
                    "code__search",
                    "code__read",
                    "log__search",
                }
            ),
        )
    )

    assert without_service_tools == frozenset({"knowledge__search"})
    assert {"code__search", "code__read", "log__search"}.issubset(with_service_tools)
