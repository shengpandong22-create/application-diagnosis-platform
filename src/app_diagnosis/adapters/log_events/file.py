import asyncio
import json
from datetime import datetime
from pathlib import Path
from uuid import UUID

from app_diagnosis.domain.incident import StackFrame
from app_diagnosis.ports.log_event_source import DiscoveredLogEvent


class FileLogEventSource:
    """读取授权根目录内的 JSONL 事件文件，拒绝路径穿越和超大输入。"""

    def __init__(self, root: Path, relative_path: str, *, max_bytes: int = 1_048_576) -> None:
        self._root = root.resolve()
        candidate = (self._root / relative_path).resolve()
        if candidate != self._root and self._root not in candidate.parents:
            raise ValueError("log event file escapes configured root")
        self._path = candidate
        self._max_bytes = max_bytes

    async def collect(self) -> tuple[DiscoveredLogEvent, ...]:
        content = await asyncio.to_thread(self._read)
        events: list[DiscoveredLogEvent] = []
        for number, line in enumerate(content.splitlines(), 1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
                events.append(_parse(payload, f"{self._path.name}:{number}"))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                raise ValueError(f"invalid log event at line {number}") from error
        return tuple(events)

    def _read(self) -> str:
        if not self._path.is_file():
            raise FileNotFoundError(self._path)
        if self._path.stat().st_size > self._max_bytes:
            raise ValueError("log event file exceeds configured byte limit")
        return self._path.read_text(encoding="utf-8")


def _parse(payload: dict[str, object], reference: str) -> DiscoveredLogEvent:
    frames = tuple(StackFrame(**item) for item in payload.get("stack_frames", []))  # type: ignore[arg-type]
    return DiscoveredLogEvent(
        service_id=UUID(str(payload["service_id"])),
        environment=str(payload["environment"]),
        occurred_at=datetime.fromisoformat(str(payload["occurred_at"])),
        severity=str(payload.get("severity", "ERROR")),
        message=str(payload["message"]),
        exception_type=str(payload["exception_type"]),
        stack_frames=frames,
        source_event_id=str(payload["source_event_id"]) if payload.get("source_event_id") else None,
        source_reference=reference,
    )
