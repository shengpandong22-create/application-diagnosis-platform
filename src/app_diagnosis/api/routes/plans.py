from uuid import UUID

from fastapi import APIRouter, Request

from app_diagnosis.api.schemas.plans import DiagnosisPlanResponse
from app_diagnosis.application.plans import DiagnosisPlanService

router = APIRouter(prefix="/api/v1/diagnoses", tags=["plans"])


@router.get("/{diagnosis_id}/plan", response_model=DiagnosisPlanResponse)
async def get_latest_plan(diagnosis_id: UUID, request: Request) -> DiagnosisPlanResponse:
    service: DiagnosisPlanService = request.app.state.plan_service
    return DiagnosisPlanResponse.from_domain(await service.get_latest(diagnosis_id))
