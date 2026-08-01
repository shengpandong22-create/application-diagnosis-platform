from uuid import UUID

from fastapi import APIRouter, Request, status

from app_diagnosis.api.schemas import CreateDiagnosisRequest, DiagnosisResponse
from app_diagnosis.api.schemas.services import (
    CreateServiceProfileRequest,
    ServiceDiagnosisSummaryResponse,
    ServiceProfileResponse,
)
from app_diagnosis.application.services import ServiceCatalogApplicationService

router = APIRouter(prefix="/api/v1/services", tags=["services"])


def _service(request: Request) -> ServiceCatalogApplicationService:
    return request.app.state.service_catalog


@router.post("", response_model=ServiceProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_service(
    payload: CreateServiceProfileRequest,
    request: Request,
) -> ServiceProfileResponse:
    service = await _service(request).create(
        name=payload.name,
        environment=payload.environment,
        description=payload.description,
        code_workspace_path=payload.code_workspace_path,
        log_directory=payload.log_directory,
        config_workspace_path=payload.config_workspace_path,
        health_targets=tuple(payload.health_targets),
        tags=tuple(payload.tags),
    )
    return ServiceProfileResponse.from_domain(service)


@router.get("", response_model=list[ServiceProfileResponse])
async def list_services(request: Request) -> list[ServiceProfileResponse]:
    return [ServiceProfileResponse.from_domain(item) for item in await _service(request).list()]


@router.get("/{service_id}", response_model=ServiceProfileResponse)
async def get_service(service_id: UUID, request: Request) -> ServiceProfileResponse:
    return ServiceProfileResponse.from_domain(await _service(request).get(service_id))


@router.get("/{service_id}/diagnoses", response_model=list[DiagnosisResponse])
async def list_service_diagnoses(
    service_id: UUID,
    request: Request,
) -> list[DiagnosisResponse]:
    """按创建时间倒序返回服务的诊断历史。"""
    diagnoses = await _service(request).list_diagnoses(service_id)
    return [DiagnosisResponse.from_domain(item) for item in diagnoses]


@router.get("/{service_id}/summary", response_model=ServiceDiagnosisSummaryResponse)
async def get_service_summary(
    service_id: UUID,
    request: Request,
) -> ServiceDiagnosisSummaryResponse:
    """返回服务信息、状态分布和最近一次诊断。"""
    return ServiceDiagnosisSummaryResponse.from_summary(
        await _service(request).summarize(service_id)
    )


@router.post(
    "/{service_id}/diagnoses",
    response_model=DiagnosisResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_service_diagnosis(
    service_id: UUID,
    payload: CreateDiagnosisRequest,
    request: Request,
) -> DiagnosisResponse:
    diagnosis = await _service(request).create_diagnosis(
        service_id,
        title=payload.title,
        symptom=payload.symptom,
        submitted_log=payload.submitted_log,
    )
    return DiagnosisResponse.from_domain(diagnosis)
