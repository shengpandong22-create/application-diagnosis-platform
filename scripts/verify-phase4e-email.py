import asyncio
import json

from app_diagnosis.adapters.notifications import EmailNotificationClient
from app_diagnosis.adapters.redaction import LocalRuleRedactor
from app_diagnosis.bootstrap.settings import Settings
from app_diagnosis.ports.notification import Notification


async def main() -> None:
    settings = Settings()
    required = {
        "APP_SMTP_HOST": settings.smtp_host,
        "APP_SMTP_SENDER": settings.smtp_sender,
        "APP_SMTP_RECIPIENTS": settings.smtp_recipients,
        "APP_SMTP_ALLOWED_HOSTS": settings.smtp_allowed_hosts,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise SystemExit("Missing SMTP settings: " + ", ".join(missing))
    notifier = EmailNotificationClient(
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username,
        password=settings.smtp_password.get_secret_value(),
        sender=settings.smtp_sender,
        recipients=settings.smtp_recipients,
        allowed_hosts=settings.smtp_allowed_hosts,
        redactor=LocalRuleRedactor(),
        use_ssl=settings.smtp_use_ssl,
        starttls=settings.smtp_starttls,
    )
    await notifier.send(
        Notification(
            title="Phase 4E SMTP real integration passed",
            summary="This is a bounded verification message from Application Diagnosis Platform.",
            incident_id="phase4e-smtp-verification",
            diagnosis_id=None,
        )
    )
    print(json.dumps({"smtp_sent": True, "recipients": len(settings.smtp_recipients)}))


if __name__ == "__main__":
    asyncio.run(main())
