import httpx
import pytest

from app_diagnosis.adapters.notifications import WebhookNotificationClient
from app_diagnosis.adapters.redaction import LocalRuleRedactor
from app_diagnosis.ports.notification import Notification


async def test_webhook_is_allowlisted_and_redacted() -> None:
    bodies: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(request.content.decode())
        return httpx.Response(200)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        notifier = WebhookNotificationClient(
            client=client,
            webhook_url="https://notify.example.com/hook",
            allowed_hosts={"notify.example.com"},
            provider="wecom",
            redactor=LocalRuleRedactor(),
        )
        await notifier.send(Notification("Failure", "password=secret", "i-1", "d-1"))
    assert "secret" not in bodies[0]
    assert "[REDACTED]" in bodies[0]


async def test_webhook_rejects_unlisted_host() -> None:
    async with httpx.AsyncClient() as client:
        with pytest.raises(PermissionError):
            WebhookNotificationClient(
                client=client,
                webhook_url="https://evil.example/hook",
                allowed_hosts={"notify.example.com"},
                provider="dingtalk",
                redactor=LocalRuleRedactor(),
            )
