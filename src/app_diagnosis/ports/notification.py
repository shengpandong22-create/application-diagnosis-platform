from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Notification:
    title: str
    summary: str
    incident_id: str
    diagnosis_id: str | None


class NotificationClient(Protocol):
    async def send(self, notification: Notification) -> None: ...
