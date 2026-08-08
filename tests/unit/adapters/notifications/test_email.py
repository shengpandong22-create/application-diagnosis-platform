from email.message import EmailMessage

import pytest

from app_diagnosis.adapters.notifications import EmailNotificationClient
from app_diagnosis.adapters.redaction import LocalRuleRedactor
from app_diagnosis.ports.notification import Notification


class FakeSMTP:
    def __init__(self, host: str, port: int, *, timeout: float) -> None:
        self.connection = (host, port, timeout)
        self.messages: list[EmailMessage] = []
        self.login_args: tuple[str, str] | None = None

    def __enter__(self) -> "FakeSMTP":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def starttls(self, **_: object) -> None:
        return None

    def login(self, user: str, password: str) -> None:
        self.login_args = (user, password)

    def send_message(self, message: EmailMessage) -> None:
        self.messages.append(message)


async def test_email_sends_redacted_minimal_notification() -> None:
    smtp = FakeSMTP("smtp.example.com", 465, timeout=10)
    notifier = EmailNotificationClient(
        host="smtp.example.com",
        port=465,
        username="sender@example.com",
        password="mail-secret",
        sender="sender@example.com",
        recipients={"receiver@example.com"},
        allowed_hosts={"smtp.example.com"},
        redactor=LocalRuleRedactor(),
        smtp_factory=lambda *_, **__: smtp,
    )
    await notifier.send(Notification("Failure", "password=secret", "i-1", "d-1"))
    assert smtp.login_args == ("sender@example.com", "mail-secret")
    assert smtp.connection == ("smtp.example.com", 465, 10)
    body = smtp.messages[0].get_content()
    assert "secret" not in body
    assert "[REDACTED]" in body
    assert "Incident: i-1" in body
    assert "Diagnosis: d-1" in body


def test_email_rejects_unlisted_host_and_invalid_recipient() -> None:
    values = {
        "host": "smtp.example.com",
        "port": 465,
        "username": "",
        "password": "",
        "sender": "sender@example.com",
        "recipients": {"receiver@example.com"},
        "allowed_hosts": {"smtp.example.com"},
        "redactor": LocalRuleRedactor(),
    }
    with pytest.raises(PermissionError):
        EmailNotificationClient(**{**values, "allowed_hosts": {"other.example.com"}})
    with pytest.raises(ValueError):
        EmailNotificationClient(**{**values, "recipients": {"not-an-email"}})
