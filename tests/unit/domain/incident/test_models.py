from datetime import UTC, datetime, timedelta
from uuid import UUID

from app_diagnosis.domain.incident import (
    LogEvent,
    StackFrame,
    build_error_fingerprint,
    build_window_key,
)

SERVICE = UUID("11111111-1111-1111-1111-111111111111")
NOW = datetime(2026, 8, 8, 10, 7, tzinfo=UTC)


def event(*, line: int = 42, service_id: UUID = SERVICE, environment: str = "local") -> LogEvent:
    return LogEvent(
        id=UUID("22222222-2222-2222-2222-222222222222"),
        service_id=service_id,
        environment=environment,
        occurred_at=NOW,
        received_at=NOW,
        severity="ERROR",
        message="request failed",
        exception_type="java.lang.NullPointerException",
        stack_frames=(StackFrame("dev.lab.OrderService", "submit", "OrderService.java", line),),
    )


def test_line_number_does_not_change_fingerprint() -> None:
    assert build_error_fingerprint(event(line=42)).value == build_error_fingerprint(
        event(line=108)
    ).value


def test_service_and_environment_are_fingerprint_scope() -> None:
    base = build_error_fingerprint(event()).value
    assert base != build_error_fingerprint(
        event(service_id=UUID("33333333-3333-3333-3333-333333333333"))
    ).value
    assert base != build_error_fingerprint(event(environment="prod")).value


def test_window_key_uses_stable_tumbling_window() -> None:
    fingerprint = build_error_fingerprint(event())
    key, start, end = build_window_key(event(), fingerprint, window=timedelta(minutes=15))
    assert key.endswith(start.isoformat())
    assert start == datetime(2026, 8, 8, 10, 0, tzinfo=UTC)
    assert end == datetime(2026, 8, 8, 10, 15, tzinfo=UTC)
