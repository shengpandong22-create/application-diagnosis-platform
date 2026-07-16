from typing import Annotated

from fastapi import APIRouter, Query, Request, status

from app_diagnosis.api.schemas.knowledge import (
    ChangeKnowledgeStatusRequest,
    CreateKnowledgeRequest,
    KnowledgeResponse,
)
from app_diagnosis.application import KnowledgeApplicationService
from app_diagnosis.domain.knowledge import KnowledgeStatus

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


def _service(request: Request) -> KnowledgeApplicationService:
    return request.app.state.knowledge_service


@router.get("", response_model=list[KnowledgeResponse])
async def list_knowledge(
    request: Request,
    status_filter: Annotated[KnowledgeStatus | None, Query(alias="status")] = None,
) -> list[KnowledgeResponse]:
    entries = await _service(request).list(status_filter)
    return [KnowledgeResponse.from_domain(item) for item in entries]


@router.post("", response_model=KnowledgeResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge(
    payload: CreateKnowledgeRequest,
    request: Request,
) -> KnowledgeResponse:
    entry = await _service(request).create(
        entry_id=payload.id,
        title=payload.title,
        summary=payload.summary,
        error_types=tuple(payload.error_types),
        tags=tuple(payload.tags),
        source=payload.source,
    )
    return KnowledgeResponse.from_domain(entry)


@router.patch("/{entry_id}/status", response_model=KnowledgeResponse)
async def change_knowledge_status(
    entry_id: str,
    payload: ChangeKnowledgeStatusRequest,
    request: Request,
) -> KnowledgeResponse:
    entry = await _service(request).change_status(
        entry_id=entry_id,
        status=payload.status,
        actor="local-api-user",
        correlation_id=request.state.request_id,
    )
    return KnowledgeResponse.from_domain(entry)
