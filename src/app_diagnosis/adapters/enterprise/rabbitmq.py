import json
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app_diagnosis.domain.incident import StackFrame
from app_diagnosis.ports.log_event_source import DiscoveredLogEvent
from app_diagnosis.ports.message_broker import BrokerMessage, MessageBrokerConsumer


class PoisonBrokerMessage(ValueError):
    pass


class AioPikaIncomingMessage(Protocol):
    body: bytes
    message_id: str | None

    async def ack(self) -> None: ...

    async def nack(self, *, requeue: bool) -> None: ...

    async def reject(self, *, requeue: bool) -> None: ...


class AioPikaQueue(Protocol):
    async def get(self, *, fail: bool) -> AioPikaIncomingMessage | None: ...


class AioPikaBrokerMessage:
    """兼容 aio-pika IncomingMessage；DLQ 由 RabbitMQ dead-letter exchange 配置承接。"""

    def __init__(self, incoming_message: AioPikaIncomingMessage) -> None:
        self._message = incoming_message
        self.body = bytes(incoming_message.body)
        self.message_id = incoming_message.message_id

    async def ack(self) -> None:
        await self._message.ack()

    async def retry(self) -> None:
        await self._message.nack(requeue=True)

    async def dead_letter(self, *, reason: str) -> None:
        # reason 写入应用日志即可；原消息 reject 后由 broker 的 DLX 路由。
        await self._message.reject(requeue=False)


class AioPikaQueueConsumer:
    """兼容 aio-pika RobustQueue.get；连接生命周期由 Worker bootstrap 管理。"""

    def __init__(self, queue: AioPikaQueue) -> None:
        self._queue = queue

    async def receive(self) -> AioPikaBrokerMessage | None:
        message = await self._queue.get(fail=False)
        return None if message is None else AioPikaBrokerMessage(message)


class RabbitMQLogEventConsumer:
    """RabbitMQ 消费语义层；具体 aio-pika channel 通过 MessageBrokerConsumer 注入。"""

    def __init__(
        self, consumer: MessageBrokerConsumer, *, max_message_bytes: int = 262_144
    ) -> None:
        self._consumer = consumer
        self._max_message_bytes = max_message_bytes

    async def receive(self) -> tuple[BrokerMessage, DiscoveredLogEvent] | None:
        message = await self._consumer.receive()
        if message is None:
            return None
        try:
            event = self._decode(message)
        except PoisonBrokerMessage as error:
            await message.dead_letter(reason=str(error))
            return None
        return message, event

    def _decode(self, message: BrokerMessage) -> DiscoveredLogEvent:
        if len(message.body) > self._max_message_bytes:
            raise PoisonBrokerMessage("message_too_large")
        try:
            payload = json.loads(message.body)
            frames = tuple(StackFrame(**item) for item in payload.get("stack_frames", []))
            return DiscoveredLogEvent(
                service_id=UUID(str(payload["service_id"])),
                environment=str(payload["environment"]),
                occurred_at=datetime.fromisoformat(str(payload["occurred_at"])),
                severity=str(payload.get("severity", "ERROR")),
                message=str(payload["message"]),
                exception_type=str(payload["exception_type"]),
                stack_frames=frames,
                source_event_id=message.message_id or payload.get("source_event_id"),
                source_reference=f"rabbitmq:{message.message_id or 'anonymous'}",
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise PoisonBrokerMessage("invalid_log_event_schema") from error
