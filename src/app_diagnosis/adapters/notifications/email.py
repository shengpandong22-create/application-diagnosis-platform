import asyncio
import smtplib
import ssl
from collections.abc import Collection
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Protocol

from app_diagnosis.ports.notification import Notification
from app_diagnosis.ports.redaction import Redactor


class SMTPConnection(Protocol):
    def __enter__(self) -> "SMTPConnection": ...
    def __exit__(self, *args: object) -> None: ...
    def starttls(self, *, context: ssl.SSLContext) -> object: ...
    def login(self, user: str, password: str) -> object: ...
    def send_message(self, message: EmailMessage) -> object: ...


class SMTPFactory(Protocol):
    def __call__(self, host: str, port: int, *, timeout: float) -> SMTPConnection: ...


class EmailNotificationClient:
    """通过受限 SMTP 发送脱敏后的最小事件通知。"""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        sender: str,
        recipients: Collection[str],
        allowed_hosts: Collection[str],
        redactor: Redactor,
        use_ssl: bool = True,
        starttls: bool = False,
        timeout_seconds: float = 10,
        smtp_factory: SMTPFactory | None = None,
    ) -> None:
        if host not in set(allowed_hosts):
            raise PermissionError("SMTP host is not allowlisted")
        if port < 1 or port > 65_535 or timeout_seconds <= 0 or timeout_seconds > 60:
            raise ValueError("invalid SMTP connection settings")
        if use_ssl and starttls:
            raise ValueError("SMTP SSL and STARTTLS are mutually exclusive")
        safe_recipients = tuple(dict.fromkeys(recipients))
        if not safe_recipients or len(safe_recipients) > 20:
            raise ValueError("SMTP recipients must contain between 1 and 20 addresses")
        if not _is_email(sender) or any(not _is_email(value) for value in safe_recipients):
            raise ValueError("invalid SMTP sender or recipient")
        self._host, self._port = host, port
        self._username, self._password = username, password
        self._sender, self._recipients = sender, safe_recipients
        self._redactor = redactor
        self._use_ssl, self._starttls = use_ssl, starttls
        self._timeout_seconds, self._smtp_factory = timeout_seconds, smtp_factory

    async def send(self, notification: Notification) -> None:
        await asyncio.to_thread(self._send_sync, self._message(notification))

    def _message(self, notification: Notification) -> EmailMessage:
        title = self._redactor.redact(notification.title).content[:200]
        summary = self._redactor.redact(notification.summary).content[:4000]
        message = EmailMessage()
        message["Subject"] = f"[Application Diagnosis] {title}"
        message["From"], message["To"] = self._sender, ", ".join(self._recipients)
        lines = [summary, "", f"Incident: {notification.incident_id}"]
        if notification.diagnosis_id:
            lines.append(f"Diagnosis: {notification.diagnosis_id}")
        message.set_content("\n".join(lines))
        return message

    def _send_sync(self, message: EmailMessage) -> None:
        factory = self._smtp_factory or (smtplib.SMTP_SSL if self._use_ssl else smtplib.SMTP)
        with factory(self._host, self._port, timeout=self._timeout_seconds) as smtp:
            if self._starttls:
                smtp.starttls(context=ssl.create_default_context())
            if self._username:
                smtp.login(self._username, self._password)
            smtp.send_message(message)


def _is_email(value: str) -> bool:
    _, address = parseaddr(value)
    return address == value and "@" in address and not any(char.isspace() for char in address)
