import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from app_diagnosis.adapters.log_events import FileLogEventSource, ReplayLogEventSource
from app_diagnosis.ports.log_event_source import DiscoveredLogEvent


async def test_replay_returns_fixed_events() -> None:
    event = DiscoveredLogEvent(
        service_id=UUID("11111111-1111-1111-1111-111111111111"),
        environment="local",
        occurred_at=datetime.now(UTC),
        severity="ERROR",
        message="failed",
        exception_type="RuntimeException",
        stack_frames=(),
    )
    assert await ReplayLogEventSource((event,)).collect() == (event,)


async def test_file_source_reads_jsonl_with_source_reference(tmp_path: Path) -> None:
    payload = {
        "service_id": "11111111-1111-1111-1111-111111111111",
        "environment": "local",
        "occurred_at": "2026-08-08T10:00:00+00:00",
        "message": "failed",
        "exception_type": "RuntimeException",
        "stack_frames": [],
    }
    (tmp_path / "events.jsonl").write_text(json.dumps(payload), encoding="utf-8")
    events = await FileLogEventSource(tmp_path, "events.jsonl").collect()
    assert events[0].source_reference == "events.jsonl:1"


def test_file_source_rejects_path_escape(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="escapes"):
        FileLogEventSource(tmp_path, "../secret.jsonl")
