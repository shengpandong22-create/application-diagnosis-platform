import pytest

from app_diagnosis.agent.strategies import (
    ApplicationErrorStrategy,
    ConfigurationStrategy,
    DiagnosisStrategyRouter,
    GenericApplicationErrorStrategy,
    NetworkStrategy,
)
from app_diagnosis.domain.diagnosis import DiagnosisCase


def _router() -> DiagnosisStrategyRouter:
    options = {
        "code_tools_enabled": True,
        "config_tools_enabled": True,
        "log_tools_enabled": True,
        "health_tools_enabled": True,
    }
    return DiagnosisStrategyRouter(
        application=ApplicationErrorStrategy(**options),
        network=NetworkStrategy(**options),
        configuration=ConfigurationStrategy(**options),
        fallback=GenericApplicationErrorStrategy(**options),
    )


@pytest.mark.parametrize(
    ("symptom", "expected"),
    [
        ("NullPointerException in OrderService", "application_error_v1"),
        ("downstream connection refused", "network_diagnosis_v1"),
        ("InventoryClient TimeoutException", "network_diagnosis_v1"),
        ("missing property database.url", "configuration_diagnosis_v1"),
        ("Missing required configuration: lab.required-region", "configuration_diagnosis_v1"),
        ("IllegalStateException: Missing required configuration", "configuration_diagnosis_v1"),
        ("generic IllegalStateException", "generic_application_error_v1"),
        ("plain HTTP 500", "generic_application_error_v1"),
        ("application behaves unexpectedly", "generic_application_error_v1"),
    ],
)
def test_routes_deterministically(symptom: str, expected: str) -> None:
    diagnosis = DiagnosisCase.create(title="failure", symptom=symptom)
    assert _router().select(diagnosis).name == expected


def test_tied_signals_fall_back_to_generic() -> None:
    diagnosis = DiagnosisCase.create(
        title="mixed", symptom="NPE and connection refused"
    )
    assert _router().select(diagnosis).name == "generic_application_error_v1"
