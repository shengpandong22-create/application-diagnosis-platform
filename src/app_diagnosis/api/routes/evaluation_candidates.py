from uuid import UUID

from fastapi import APIRouter, Request

from app_diagnosis.api.schemas.evaluation_candidates import (
    EvaluationCandidateResponse,
    EvaluationCandidateTrendResponse,
    LabelEvaluationCandidateRequest,
)
from app_diagnosis.application.evaluation_candidates import EvaluationCandidateService

router = APIRouter(prefix="/api/v1/evaluation-candidates", tags=["evaluation"])


def _service(request: Request) -> EvaluationCandidateService:
    return request.app.state.evaluation_candidate_service


@router.get("", response_model=list[EvaluationCandidateResponse])
async def list_candidates(request: Request) -> list[EvaluationCandidateResponse]:
    return [
        EvaluationCandidateResponse.from_domain(item)
        for item in await _service(request).list()
    ]


@router.get("/trend", response_model=EvaluationCandidateTrendResponse)
async def candidate_trend(request: Request) -> EvaluationCandidateTrendResponse:
    return EvaluationCandidateTrendResponse.from_domain(await _service(request).trend())


@router.post("/{candidate_id}/label", response_model=EvaluationCandidateResponse)
async def label_candidate(
    candidate_id: UUID, payload: LabelEvaluationCandidateRequest, request: Request
) -> EvaluationCandidateResponse:
    return EvaluationCandidateResponse.from_domain(
        await _service(request).label(
            candidate_id,
            expected_category=payload.expected_category,
            expected_root_cause=payload.expected_root_cause,
            required_evidence_ids=tuple(payload.required_evidence_ids),
            prompt_version=payload.prompt_version,
        )
    )


@router.post("/{candidate_id}/promote", response_model=EvaluationCandidateResponse)
async def promote_candidate(candidate_id: UUID, request: Request) -> EvaluationCandidateResponse:
    return EvaluationCandidateResponse.from_domain(await _service(request).promote(candidate_id))
