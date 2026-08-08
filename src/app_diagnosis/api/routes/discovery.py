from fastapi import APIRouter, Request

from app_diagnosis.adapters.log_events import ReplayLogEventSource
from app_diagnosis.api.schemas.discovery import DiscoveryResponse
from app_diagnosis.api.schemas.incidents import IngestLogEventRequest
from app_diagnosis.application.discovery import ActiveDiscoveryApplicationService
from app_diagnosis.domain.incident import StackFrame
from app_diagnosis.ports.log_event_source import DiscoveredLogEvent

router = APIRouter(prefix="/api/v1/discovery", tags=["discovery"])


@router.post("/replay", response_model=list[DiscoveryResponse])
async def replay_event(
    payload: list[IngestLogEventRequest], request: Request
) -> list[DiscoveryResponse]:
    source = ReplayLogEventSource(
        tuple(
            DiscoveredLogEvent(
                service_id=item.service_id,
                environment=item.environment,
                occurred_at=item.occurred_at,
                severity=item.severity,
                message=item.message,
                exception_type=item.exception_type,
                stack_frames=tuple(
                    StackFrame(**frame.model_dump()) for frame in item.stack_frames
                ),
                source_event_id=item.source_event_id,
                source_reference=f"replay:{item.source_event_id or index}",
            )
            for index, item in enumerate(payload, 1)
        )
    )
    service: ActiveDiscoveryApplicationService = request.app.state.discovery_service
    return [DiscoveryResponse.from_domain(item) for item in await service.discover(source)]
