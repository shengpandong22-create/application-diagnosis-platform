from uuid import UUID

from fastapi import APIRouter, Request, status

from app_diagnosis.api.schemas import (
    AgentRunResponse,
    ConfirmationRecordResponse,
    ConfirmationRequest,
    ConfirmationResponse,
    CreateDiagnosisRequest,
    DiagnosisResponse,
    EvidenceResponse,
    RunResultResponse,
    SupplementRequest,
    SupplementResponse,
)
from app_diagnosis.application import DiagnosisApplicationService
from app_diagnosis.bootstrap.settings import Settings

router = APIRouter(prefix="/api/v1/diagnoses", tags=["diagnoses"])


def _service(request: Request) -> DiagnosisApplicationService:
    return request.app.state.diagnosis_service


@router.post("", response_model=DiagnosisResponse, status_code=status.HTTP_201_CREATED)
async def create_diagnosis(
    payload: CreateDiagnosisRequest,
    request: Request,
) -> DiagnosisResponse:
    diagnosis = await _service(request).create(
        title=payload.title,
        symptom=payload.symptom,
        submitted_log=payload.submitted_log,
    )
    return DiagnosisResponse.from_domain(diagnosis)


@router.get("/{diagnosis_id}", response_model=DiagnosisResponse)
async def get_diagnosis(diagnosis_id: UUID, request: Request) -> DiagnosisResponse:
    diagnosis = await _service(request).get(diagnosis_id)
    return DiagnosisResponse.from_domain(diagnosis)


@router.post("/{diagnosis_id}/runs", response_model=RunResultResponse)
async def run_diagnosis(
    diagnosis_id: UUID,
    request: Request,
) -> RunResultResponse:
    settings: Settings = request.app.state.settings
    result = await _service(request).run(
        diagnosis_id,
        actor="local-api-user",
        environment=settings.env,
        correlation_id=request.state.request_id,
        max_tool_output_bytes=settings.tool_output_max_bytes,
    )
    return RunResultResponse.from_result(result)


@router.get("/{diagnosis_id}/runs", response_model=list[AgentRunResponse])
async def list_runs(diagnosis_id: UUID, request: Request) -> list[AgentRunResponse]:
    details = await _service(request).list_runs(diagnosis_id)
    return [AgentRunResponse.from_details(item) for item in details]


@router.post("/{diagnosis_id}/cancel", response_model=DiagnosisResponse)
async def cancel_diagnosis(diagnosis_id: UUID, request: Request) -> DiagnosisResponse:
    diagnosis = await _service(request).cancel(diagnosis_id)
    return DiagnosisResponse.from_domain(diagnosis)


@router.get("/{diagnosis_id}/evidence", response_model=list[EvidenceResponse])
async def list_evidence(diagnosis_id: UUID, request: Request) -> list[EvidenceResponse]:
    evidence = await _service(request).list_evidence(diagnosis_id)
    return [EvidenceResponse.from_domain(item) for item in evidence]


@router.post("/{diagnosis_id}/supplements", response_model=SupplementResponse)
async def supplement_diagnosis(
    diagnosis_id: UUID,
    payload: SupplementRequest,
    request: Request,
) -> SupplementResponse:
    diagnosis, evidence = await _service(request).supplement(
        diagnosis_id,
        content=payload.content,
        evidence_type=payload.type,
    )
    return SupplementResponse(
        diagnosis=DiagnosisResponse.from_domain(diagnosis),
        evidence=EvidenceResponse.from_domain(evidence),
    )


@router.post("/{diagnosis_id}/confirmation", response_model=ConfirmationResponse)
async def confirm_diagnosis(
    diagnosis_id: UUID,
    payload: ConfirmationRequest,
    request: Request,
) -> ConfirmationResponse:
    diagnosis, confirmation = await _service(request).confirm_action(
        diagnosis_id,
        action=payload.action,
        actor="local-api-user",
        comment=payload.comment,
    )
    return ConfirmationResponse(
        diagnosis=DiagnosisResponse.from_domain(diagnosis),
        confirmation=ConfirmationRecordResponse.from_domain(confirmation),
    )
