"""主动发现的确定性领域核心，不依赖日志采集器或数据库实现。"""

import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from uuid import UUID, uuid4


class IncidentStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


@dataclass(frozen=True, slots=True)
class StackFrame:
    class_name: str
    method_name: str
    file_name: str | None = None
    line_number: int | None = None
    is_business_frame: bool = True

    def normalized(self) -> str:
        """返回与源码行号无关的稳定栈帧表示。"""
        return f"{self.class_name.strip().lower()}#{self.method_name.strip().lower()}"


@dataclass(frozen=True, slots=True)
class LogEvent:
    id: UUID
    service_id: UUID
    environment: str
    occurred_at: datetime
    received_at: datetime
    severity: str
    message: str
    exception_type: str
    stack_frames: tuple[StackFrame, ...]
    source_event_id: str | None = None

    def __post_init__(self) -> None:
        if not self.environment.strip() or not self.exception_type.strip():
            raise ValueError("environment and exception_type must not be blank")
        if not self.message.strip():
            raise ValueError("message must not be blank")
        for value in (self.occurred_at, self.received_at):
            if value.tzinfo is None:
                raise ValueError("event timestamps must be timezone-aware")

    @classmethod
    def create(cls, **values: object) -> "LogEvent":
        now = datetime.now(UTC)
        return cls(id=uuid4(), received_at=now, **values)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class ErrorFingerprint:
    value: str
    algorithm_version: str
    normalized_exception: str
    normalized_frames: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Incident:
    id: UUID
    service_id: UUID
    environment: str
    fingerprint: str
    fingerprint_version: str
    aggregation_key: str
    status: IncidentStatus
    exception_type: str
    sample_message: str
    occurrence_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    window_started_at: datetime
    window_ends_at: datetime
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if self.occurrence_count < 1:
            raise ValueError("occurrence_count must be positive")
        if self.last_seen_at < self.first_seen_at:
            raise ValueError("last_seen_at must not precede first_seen_at")
        if self.window_ends_at <= self.window_started_at:
            raise ValueError("incident window must be positive")

    def observe(self, event: LogEvent) -> "Incident":
        if event.service_id != self.service_id or event.environment != self.environment:
            raise ValueError("event does not belong to this incident scope")
        return replace(
            self,
            occurrence_count=self.occurrence_count + 1,
            last_seen_at=max(self.last_seen_at, event.occurred_at),
            updated_at=max(self.updated_at, event.received_at),
        )


@dataclass(frozen=True, slots=True)
class IncidentAggregation:
    incident: Incident
    is_novel: bool
    duplicate_event: bool = False


def build_error_fingerprint(
    event: LogEvent,
    *,
    algorithm_version: str = "v1",
    max_business_frames: int = 5,
) -> ErrorFingerprint:
    """生成版本化指纹；数字、UUID和行号变化不会造成指纹漂移。"""
    exception = _normalize_exception(event.exception_type)
    frames = tuple(
        frame.normalized()
        for frame in event.stack_frames
        if frame.is_business_frame
    )[:max_business_frames]
    canonical = "|".join(
        (
            algorithm_version,
            str(event.service_id),
            event.environment.strip().lower(),
            exception,
            *frames,
        )
    )
    return ErrorFingerprint(
        value=sha256(canonical.encode("utf-8")).hexdigest(),
        algorithm_version=algorithm_version,
        normalized_exception=exception,
        normalized_frames=frames,
    )


def build_window_key(
    event: LogEvent,
    fingerprint: ErrorFingerprint,
    *,
    window: timedelta,
) -> tuple[str, datetime, datetime]:
    """使用固定时间桶保证重放结果稳定，并使窗口边界规则清晰。"""
    seconds = int(window.total_seconds())
    if seconds <= 0:
        raise ValueError("aggregation window must be positive")
    timestamp = int(event.occurred_at.timestamp())
    start = datetime.fromtimestamp(timestamp - timestamp % seconds, tz=UTC)
    end = start + window
    key = f"{event.service_id}:{event.environment.lower()}:{fingerprint.value}:{start.isoformat()}"
    return key, start, end


def _normalize_exception(value: str) -> str:
    text = value.strip().lower()
    text = re.sub(r"[0-9a-f]{8}-[0-9a-f-]{27,}", "<uuid>", text)
    return re.sub(r"\d+", "<n>", text)
