from uuid import UUID

from fastapi import APIRouter, Request, status

from app_diagnosis.api.schemas.incidents import (
    IncidentAggregationResponse,
    IncidentResponse,
    IngestLogEventRequest,
)
from app_diagnosis.application.incidents import IncidentApplicationService
from app_diagnosis.domain.incident import StackFrame

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])


def _service(request: Request) -> IncidentApplicationService:
    return request.app.state.incident_service


@router.post(
    "/events", response_model=IncidentAggregationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_event(
    payload: IngestLogEventRequest, request: Request
) -> IncidentAggregationResponse:
    result = await _service(request).ingest(
        service_id=payload.service_id, environment=payload.environment,
        occurred_at=payload.occurred_at, severity=payload.severity, message=payload.message,
        exception_type=payload.exception_type,
        stack_frames=tuple(StackFrame(**item.model_dump()) for item in payload.stack_frames),
        source_event_id=payload.source_event_id,
    )
    return IncidentAggregationResponse.from_domain(result)


@router.get("", response_model=list[IncidentResponse])
async def list_incidents(
    request: Request, service_id: UUID | None = None
) -> list[IncidentResponse]:
    return [
        IncidentResponse.from_domain(item)
        for item in await _service(request).list(service_id=service_id)
    ]


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(incident_id: UUID, request: Request) -> IncidentResponse:
    return IncidentResponse.from_domain(await _service(request).get(incident_id))
