from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app_diagnosis.domain.incident import StackFrame


@dataclass(frozen=True, slots=True)
class DiscoveredLogEvent:
    service_id: UUID
    environment: str
    occurred_at: datetime
    severity: str
    message: str
    exception_type: str
    stack_frames: tuple[StackFrame, ...]
    source_event_id: str | None = None
    source_reference: str | None = None


class LogEventSource(Protocol):
    async def collect(self) -> tuple[DiscoveredLogEvent, ...]: ...
