"""诊断用例的 HTTP 路由层。

路由层刻意保持很薄：只负责 API schema 与 ApplicationService 的转换，
不承载 Agent Loop、Evidence 创建或状态机逻辑。后续加接口时也应遵守这个边界。
"""

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
from app_diagnosis.api.schemas.knowledge import KnowledgeCandidateResponse
from app_diagnosis.application import DiagnosisApplicationService, KnowledgeApplicationService
from app_diagnosis.bootstrap.settings import Settings

router = APIRouter(prefix="/api/v1/diagnoses", tags=["diagnoses"])


def _service(request: Request) -> DiagnosisApplicationService:
    """从 FastAPI app.state 取出 bootstrap 装配好的应用服务。"""
    return request.app.state.diagnosis_service


def _knowledge_service(request: Request) -> KnowledgeApplicationService:
    """获取知识用例服务，用于显式生成诊断知识候选。"""
    return request.app.state.knowledge_service


@router.post("", response_model=DiagnosisResponse, status_code=status.HTTP_201_CREATED)
async def create_diagnosis(
    payload: CreateDiagnosisRequest,
    request: Request,
) -> DiagnosisResponse:
    """创建诊断；脱敏和初始 Evidence 创建由应用服务完成。"""
    diagnosis = await _service(request).create(
        title=payload.title,
        symptom=payload.symptom,
        submitted_log=payload.submitted_log,
    )
    return DiagnosisResponse.from_domain(diagnosis)


@router.get("/{diagnosis_id}", response_model=DiagnosisResponse)
async def get_diagnosis(diagnosis_id: UUID, request: Request) -> DiagnosisResponse:
    """返回当前持久化的诊断状态。"""
    diagnosis = await _service(request).get(diagnosis_id)
    return DiagnosisResponse.from_domain(diagnosis)


@router.post("/{diagnosis_id}/runs", response_model=RunResultResponse)
async def run_diagnosis(
    diagnosis_id: UUID,
    request: Request,
) -> RunResultResponse:
    """为已有诊断启动一次有界 Agent 运行。"""
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
    """返回该诊断的 AgentRun/ToolRun 持久化轨迹。"""
    details = await _service(request).list_runs(diagnosis_id)
    return [AgentRunResponse.from_details(item) for item in details]


@router.post("/{diagnosis_id}/cancel", response_model=DiagnosisResponse)
async def cancel_diagnosis(diagnosis_id: UUID, request: Request) -> DiagnosisResponse:
    """在当前状态允许时取消诊断运行。"""
    diagnosis = await _service(request).cancel(diagnosis_id)
    return DiagnosisResponse.from_domain(diagnosis)


@router.get("/{diagnosis_id}/evidence", response_model=list[EvidenceResponse])
async def list_evidence(diagnosis_id: UUID, request: Request) -> list[EvidenceResponse]:
    """返回当前诊断关联的全部 Evidence。"""
    evidence = await _service(request).list_evidence(diagnosis_id)
    return [EvidenceResponse.from_domain(item) for item in evidence]


@router.post("/{diagnosis_id}/supplements", response_model=SupplementResponse)
async def supplement_diagnosis(
    diagnosis_id: UUID,
    payload: SupplementRequest,
    request: Request,
) -> SupplementResponse:
    """接收用户补充事实或日志，并重新打开调查。"""
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
    """记录人工确认、驳回或继续调查动作，不覆盖模型原始结论。"""
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


@router.post(
    "/{diagnosis_id}/knowledge-candidates",
    response_model=KnowledgeCandidateResponse,
)
async def create_knowledge_candidate(
    diagnosis_id: UUID,
    request: Request,
) -> KnowledgeCandidateResponse:
    """从已人工确认的诊断显式生成 candidate 知识。"""
    result = await _knowledge_service(request).create_from_confirmed_diagnosis(
        diagnosis_id=diagnosis_id,
        actor="local-api-user",
        correlation_id=request.state.request_id,
    )
    return KnowledgeCandidateResponse.from_result(result)
