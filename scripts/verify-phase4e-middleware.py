import asyncio
import json
from datetime import UTC, datetime, timedelta

import aio_pika
from redis.asyncio import Redis

from app_diagnosis.adapters.enterprise import (
    AioPikaQueueConsumer,
    RabbitMQLogEventConsumer,
    RedisDeduplicationStore,
)

RABBIT_URL = "amqp://appdiag:appdiag-local@127.0.0.1:5672/"
REDIS_URL = "redis://127.0.0.1:6379/15"


async def verify_redis() -> dict[str, object]:
    client = Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        await client.flushdb()
        store = RedisDeduplicationStore(client, key_prefix="appdiag:acceptance:")
        expires = datetime.now(UTC) + timedelta(seconds=2)
        claims = await asyncio.gather(
            *(store.claim("same-event", expires_at=expires) for _ in range(50))
        )
        ttl_ms = await client.pttl("appdiag:acceptance:same-event")
        if sum(claims) != 1 or ttl_ms <= 0:
            raise AssertionError(
                f"redis atomic claim failed: successes={sum(claims)}, ttl={ttl_ms}"
            )
        await asyncio.sleep(2.1)
        reclaimed = await store.claim(
            "same-event", expires_at=datetime.now(UTC) + timedelta(seconds=2)
        )
        if not reclaimed:
            raise AssertionError("redis key was not reclaimable after TTL")
        return {
            "concurrent_claims": 50,
            "successful_claims": 1,
            "ttl_ms": ttl_ms,
            "reclaimed": True,
        }
    finally:
        await client.aclose()


def event_body() -> bytes:
    return json.dumps(
        {
            "service_id": "11111111-1111-1111-1111-111111111111",
            "environment": "local",
            "occurred_at": datetime.now(UTC).isoformat(),
            "severity": "ERROR",
            "message": "RuntimeException",
            "exception_type": "java.lang.RuntimeException",
            "stack_frames": [],
        }
    ).encode()


async def verify_rabbitmq() -> dict[str, object]:
    connection = await aio_pika.connect_robust(RABBIT_URL)
    try:
        channel = await connection.channel()
        exchange = await channel.declare_exchange("appdiag.acceptance.events", auto_delete=True)
        dlx = await channel.declare_exchange("appdiag.acceptance.dlx", auto_delete=True)
        queue = await channel.declare_queue(
            "appdiag.acceptance.events",
            auto_delete=True,
            arguments={
                "x-dead-letter-exchange": dlx.name,
                "x-dead-letter-routing-key": "poison",
            },
        )
        dlq = await channel.declare_queue("appdiag.acceptance.dlq", auto_delete=True)
        await queue.bind(exchange, routing_key="event")
        await dlq.bind(dlx, routing_key="poison")
        await queue.purge()
        await dlq.purge()

        await exchange.publish(
            aio_pika.Message(event_body(), message_id="ack-001"), routing_key="event"
        )
        source = RabbitMQLogEventConsumer(AioPikaQueueConsumer(queue))
        received = await source.receive()
        if received is None:
            raise AssertionError("valid RabbitMQ message was not received")
        message, event = received
        await message.ack()
        if event.source_event_id != "ack-001":
            raise AssertionError("RabbitMQ message_id was not mapped to source_event_id")

        await exchange.publish(
            aio_pika.Message(event_body(), message_id="retry-001"), routing_key="event"
        )
        retried = await source.receive()
        if retried is None:
            raise AssertionError("retry test message was not received")
        await retried[0].retry()
        redelivered = await source.receive()
        if redelivered is None or redelivered[1].source_event_id != "retry-001":
            raise AssertionError("RabbitMQ message was not redelivered")
        await redelivered[0].ack()

        await exchange.publish(
            aio_pika.Message(b"not-json", message_id="poison-001"), routing_key="event"
        )
        if await source.receive() is not None:
            raise AssertionError("poison message should not become LogEvent")
        dead = None
        for _ in range(50):
            dead = await dlq.get(fail=False)
            if dead is not None:
                break
            await asyncio.sleep(0.1)
        if dead is None or dead.message_id != "poison-001":
            raise AssertionError("poison message did not arrive in DLQ")
        await dead.ack()
        return {"ack": True, "redelivery": True, "dlq": True}
    finally:
        await connection.close()


async def main() -> None:
    result = {"redis": await verify_redis(), "rabbitmq": await verify_rabbitmq()}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
