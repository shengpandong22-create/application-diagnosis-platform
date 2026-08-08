import json
from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace

from app_diagnosis.adapters.enterprise import RabbitMQLogEventConsumer
from app_diagnosis.application.enterprise_consumer import EnterpriseDiscoveryConsumer


@dataclass
class FakeMessage:
    body: bytes
    message_id: str | None = "message-1"
    acked: bool = False
    retried: bool = False
    dead_letter_reason: str | None = None

    async def ack(self) -> None:
        self.acked = True

    async def retry(self) -> None:
        self.retried = True

    async def dead_letter(self, *, reason: str) -> None:
        self.dead_letter_reason = reason


class FakeBroker:
    def __init__(self, message: FakeMessage | Exception | None) -> None:
        self.message = message

    async def receive(self):
        if isinstance(self.message, Exception):
            raise self.message
        return self.message


class FailingDiscovery:
    async def process(self, event):
        raise RuntimeError("temporary failure")


class SuccessfulDiscovery:
    async def process(self, event):
        return SimpleNamespace(
            triggered=True,
            incident=SimpleNamespace(
                id="incident-1", exception_type="RuntimeException"
            ),
            diagnosis_id="diagnosis-1",
        )


class FailingNotifier:
    async def send(self, notification) -> None:
        raise TimeoutError("notification offline")


def payload() -> bytes:
    return json.dumps(
        {
            "service_id": "11111111-1111-1111-1111-111111111111",
            "environment": "prod",
            "occurred_at": datetime.now(UTC).isoformat(),
            "message": "failed",
            "exception_type": "RuntimeException",
            "stack_frames": [],
        }
    ).encode()


async def test_poison_message_goes_to_dlq() -> None:
    message = FakeMessage(b"not-json")
    source = RabbitMQLogEventConsumer(FakeBroker(message))
    assert await source.receive() is None
    assert message.dead_letter_reason == "invalid_log_event_schema"
    assert not message.acked and not message.retried


async def test_processing_failure_requeues_without_ack() -> None:
    message = FakeMessage(payload())
    worker = EnterpriseDiscoveryConsumer(
        source=RabbitMQLogEventConsumer(FakeBroker(message)),
        discovery=FailingDiscovery(),  # type: ignore[arg-type]
    )
    result = await worker.consume_once()
    assert result.consumed is False
    assert message.retried and not message.acked


async def test_broker_unavailable_is_safe_worker_result() -> None:
    worker = EnterpriseDiscoveryConsumer(
        source=RabbitMQLogEventConsumer(FakeBroker(ConnectionError("offline"))),
        discovery=FailingDiscovery(),  # type: ignore[arg-type]
    )
    result = await worker.consume_once()
    assert result.consumed is False
    assert result.broker_error == "ConnectionError"


async def test_success_is_acked_even_when_optional_notification_fails() -> None:
    message = FakeMessage(payload())
    worker = EnterpriseDiscoveryConsumer(
        source=RabbitMQLogEventConsumer(FakeBroker(message)),
        discovery=SuccessfulDiscovery(),  # type: ignore[arg-type]
        notifier=FailingNotifier(),  # type: ignore[arg-type]
    )
    result = await worker.consume_once()
    assert result.consumed is True
    assert message.acked and not message.retried
    assert result.notification_error == "TimeoutError"
