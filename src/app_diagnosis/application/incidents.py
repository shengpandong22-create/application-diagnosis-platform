from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app_diagnosis.application.services import ServiceProfileNotFound
from app_diagnosis.domain.incident import (
    Incident,
    IncidentAggregation,
    IncidentStatus,
    LogEvent,
    StackFrame,
    build_error_fingerprint,
    build_window_key,
)
from app_diagnosis.ports.deduplication_store import DeduplicationStore
from app_diagnosis.ports.incident_repository import IncidentRepository
from app_diagnosis.ports.redaction import Redactor
from app_diagnosis.ports.service_profile_repository import ServiceProfileRepository


class IncidentNotFound(LookupError):
    pass


class IncidentApplicationService:
    """将不可信日志转为脱敏 LogEvent，并执行确定性指纹聚合。"""

    def __init__(
        self,
        *,
        incidents: IncidentRepository,
        deduplication: DeduplicationStore,
        services: ServiceProfileRepository,
        redactor: Redactor,
        window: timedelta = timedelta(minutes=15),
    ) -> None:
        self._incidents = incidents
        self._deduplication = deduplication
        self._services = services
        self._redactor = redactor
        self._window = window

    async def ingest(
        self,
        *,
        service_id: UUID,
        environment: str,
        occurred_at: datetime,
        severity: str,
        message: str,
        exception_type: str,
        stack_frames: tuple[StackFrame, ...],
        source_event_id: str | None = None,
    ) -> IncidentAggregation:
        service = await self._services.get(service_id)
        if service is None:
            raise ServiceProfileNotFound(str(service_id))
        if service.environment.casefold() != environment.strip().casefold():
            raise ValueError("event environment does not match service profile")

        redacted = self._redactor.redact(message)
        received_at = datetime.now(UTC)
        event = LogEvent(
            id=uuid4(), service_id=service_id, environment=environment.strip(),
            occurred_at=occurred_at, received_at=received_at, severity=severity.strip().upper(),
            message=redacted.content, exception_type=exception_type.strip(),
            stack_frames=stack_frames, source_event_id=source_event_id,
        )
        fingerprint = build_error_fingerprint(event)
        key, window_start, window_end = build_window_key(
            event, fingerprint, window=self._window
        )
        if source_event_id:
            claimed = await self._deduplication.claim(
                f"log-event:{service_id}:{source_event_id}",
                expires_at=received_at + self._window,
            )
            if not claimed:
                current = await self._incidents.get_by_aggregation_key(key)
                if current is not None:
                    return IncidentAggregation(current, is_novel=False, duplicate_event=True)

        candidate = Incident(
            id=uuid4(), service_id=service_id, environment=event.environment,
            fingerprint=fingerprint.value,
            fingerprint_version=fingerprint.algorithm_version,
            aggregation_key=key, diagnosis_id=None, status=IncidentStatus.OPEN,
            exception_type=event.exception_type, sample_message=event.message,
            occurrence_count=1, first_seen_at=event.occurred_at,
            last_seen_at=event.occurred_at, window_started_at=window_start,
            window_ends_at=window_end, created_at=received_at, updated_at=received_at,
        )
        return await self._incidents.aggregate(candidate)

    async def get(self, incident_id: UUID) -> Incident:
        incident = await self._incidents.get(incident_id)
        if incident is None:
            raise IncidentNotFound(str(incident_id))
        return incident

    async def list(self, *, service_id: UUID | None = None) -> tuple[Incident, ...]:
        return await self._incidents.list(service_id=service_id)
