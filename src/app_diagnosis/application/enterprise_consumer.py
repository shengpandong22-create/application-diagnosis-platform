import asyncio
from dataclasses import dataclass

from app_diagnosis.adapters.enterprise.rabbitmq import RabbitMQLogEventConsumer
from app_diagnosis.application.discovery import ActiveDiscoveryApplicationService, DiscoveryResult
from app_diagnosis.ports.notification import Notification, NotificationClient


@dataclass(frozen=True, slots=True)
class EnterpriseConsumeResult:
    consumed: bool
    discovery: DiscoveryResult | None = None
    notification_error: str | None = None
    broker_error: str | None = None


class EnterpriseDiscoveryConsumer:
    def __init__(
        self,
        *,
        source: RabbitMQLogEventConsumer,
        discovery: ActiveDiscoveryApplicationService,
        notifier: NotificationClient | None = None,
    ) -> None:
        self._source = source
        self._discovery = discovery
        self._notifier = notifier

    async def consume_once(self) -> EnterpriseConsumeResult:
        try:
            received = await self._source.receive()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            return EnterpriseConsumeResult(
                consumed=False, broker_error=type(error).__name__
            )
        if received is None:
            return EnterpriseConsumeResult(consumed=False)
        message, event = received
        try:
            result = await self._discovery.process(event)
        except asyncio.CancelledError:
            await asyncio.shield(message.retry())
            raise
        except Exception:
            await message.retry()
            return EnterpriseConsumeResult(consumed=False)
        await message.ack()
        notification_error = None
        if self._notifier is not None and result.triggered:
            try:
                await self._notifier.send(
                    Notification(
                        title=f"Incident {result.incident.exception_type}",
                        summary="A bounded automatic diagnosis was triggered.",
                        incident_id=str(result.incident.id),
                        diagnosis_id=str(result.diagnosis_id) if result.diagnosis_id else None,
                    )
                )
            except Exception as error:
                notification_error = type(error).__name__
        return EnterpriseConsumeResult(True, result, notification_error)
