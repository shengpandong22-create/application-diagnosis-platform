from typing import Protocol


class BrokerMessage(Protocol):
    body: bytes
    message_id: str | None

    async def ack(self) -> None: ...

    async def retry(self) -> None: ...

    async def dead_letter(self, *, reason: str) -> None: ...


class MessageBrokerConsumer(Protocol):
    async def receive(self) -> BrokerMessage | None: ...
