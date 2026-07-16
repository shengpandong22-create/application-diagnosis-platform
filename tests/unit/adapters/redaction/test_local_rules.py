import pytest

from app_diagnosis.adapters.redaction import LocalRuleRedactor
from app_diagnosis.domain.evidence import RedactionStatus


@pytest.mark.parametrize(
    ("content", "secret"),
    [
        ("Authorization: Bearer top-secret-token", "top-secret-token"),
        ("api_key=abcdefghijklmnop", "abcdefghijklmnop"),
        ('{"api_key":"json-secret-value"}', "json-secret-value"),
        ("password: hunter2", "hunter2"),
        ('{"password":"json-password"}', "json-password"),
        ("token=sk-abcdefghijklmnop", "sk-abcdefghijklmnop"),
        ("postgresql://admin:db-secret@localhost/app", "db-secret"),
        ("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.signature", "eyJhbGci"),
    ],
)
def test_redacts_supported_secret_shapes(content: str, secret: str) -> None:
    result = LocalRuleRedactor().redact(content)
    assert secret not in result.content
    assert "[REDACTED]" in result.content
    assert result.status is RedactionStatus.REDACTED
    assert result.redaction_count >= 1


def test_is_deterministic_and_idempotent() -> None:
    redactor = LocalRuleRedactor()
    first = redactor.redact("password=secret")
    second = redactor.redact(first.content)
    assert second.content == first.content
    assert second.status is RedactionStatus.NOT_REQUIRED
    assert second.redaction_count == 0


def test_leaves_normal_diagnostic_text_unchanged() -> None:
    result = LocalRuleRedactor().redact("NullPointerException at PaymentService:42")
    assert result.content == "NullPointerException at PaymentService:42"
    assert result.status is RedactionStatus.NOT_REQUIRED
