from uuid import UUID

from fastapi import APIRouter, Request

from app_diagnosis.api.schemas.traces import DiagnosisTraceResponse
from app_diagnosis.application import DiagnosisTraceService

router = APIRouter(prefix="/api/v1/diagnoses", tags=["traces"])


@router.get("/{diagnosis_id}/trace", response_model=DiagnosisTraceResponse)
async def get_trace(diagnosis_id: UUID, request: Request) -> DiagnosisTraceResponse:
    service: DiagnosisTraceService = request.app.state.trace_service
    return DiagnosisTraceResponse.from_domain(await service.get(diagnosis_id))
