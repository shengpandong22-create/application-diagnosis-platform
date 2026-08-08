from collections.abc import Collection
from urllib.parse import urlparse

import httpx

from app_diagnosis.ports.notification import Notification
from app_diagnosis.ports.redaction import Redactor


class WebhookNotificationClient:
    """钉钉/企微兼容 Webhook；主机必须显式列入白名单。"""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        webhook_url: str,
        allowed_hosts: Collection[str],
        provider: str,
        redactor: Redactor,
    ) -> None:
        host = urlparse(webhook_url).hostname
        if host is None or host not in set(allowed_hosts):
            raise PermissionError("notification webhook host is not allowlisted")
        if provider not in {"dingtalk", "wecom"}:
            raise ValueError("unsupported notification provider")
        self._client = client
        self._url = webhook_url
        self._provider = provider
        self._redactor = redactor

    async def send(self, notification: Notification) -> None:
        title = self._redactor.redact(notification.title).content
        summary = self._redactor.redact(notification.summary).content
        text = f"{title}\n{summary}\nIncident: {notification.incident_id}"
        if notification.diagnosis_id:
            text += f"\nDiagnosis: {notification.diagnosis_id}"
        payload = (
            {"msgtype": "text", "text": {"content": text}}
            if self._provider == "dingtalk"
            else {"msgtype": "text", "text": {"content": text}}
        )
        response = await self._client.post(self._url, json=payload)
        response.raise_for_status()
