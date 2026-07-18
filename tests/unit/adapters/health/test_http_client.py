import pytest

from app_diagnosis.adapters.health import HttpHealthCheckClient
from app_diagnosis.adapters.redaction import LocalRuleRedactor


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1/health",
        "http://example.com/health",
        "http://user:password@localhost/health",
    ],
)
def test_rejects_non_loopback_or_unsafe_health_targets(url: str) -> None:
    with pytest.raises(ValueError):
        HttpHealthCheckClient({"target": url}, LocalRuleRedactor())


def test_accepts_loopback_http_target() -> None:
    client = HttpHealthCheckClient(
        {"java-lab": "http://127.0.0.1:18080/actuator/health"},
        LocalRuleRedactor(),
    )
    assert client is not None
