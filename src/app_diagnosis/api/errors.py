import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app_diagnosis.application import (
    DiagnosisNotFound,
    DiagnosisPlanNotFound,
    DiagnosisRunConflict,
    KnowledgeCandidateNotAllowed,
    KnowledgeConflict,
    KnowledgeNotFound,
    KnowledgeStatusConflict,
    ServiceProfileConflict,
    ServiceProfileNotFound,
)
from app_diagnosis.application.incidents import IncidentNotFound
from app_diagnosis.domain.diagnosis import InvalidDiagnosisValue

logger = logging.getLogger("app_diagnosis.api.errors")


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(IncidentNotFound)
    async def incident_not_found(request: Request, error: IncidentNotFound) -> JSONResponse:
        return _response(request, status.HTTP_404_NOT_FOUND, "incident_not_found", str(error))

    @app.exception_handler(DiagnosisNotFound)
    async def diagnosis_not_found(request: Request, error: DiagnosisNotFound) -> JSONResponse:
        return _response(
            request,
            status.HTTP_404_NOT_FOUND,
            "diagnosis_not_found",
            "Diagnosis not found",
        )

    @app.exception_handler(DiagnosisPlanNotFound)
    async def diagnosis_plan_not_found(
        request: Request, error: DiagnosisPlanNotFound
    ) -> JSONResponse:
        return _response(
            request,
            status.HTTP_404_NOT_FOUND,
            "diagnosis_plan_not_found",
            "Diagnosis plan not found",
        )

    @app.exception_handler(DiagnosisRunConflict)
    async def diagnosis_conflict(request: Request, error: DiagnosisRunConflict) -> JSONResponse:
        return _response(request, status.HTTP_409_CONFLICT, "diagnosis_run_conflict", str(error))

    @app.exception_handler(KnowledgeConflict)
    async def knowledge_conflict(request: Request, error: KnowledgeConflict) -> JSONResponse:
        return _response(request, status.HTTP_409_CONFLICT, "knowledge_conflict", str(error))

    @app.exception_handler(KnowledgeCandidateNotAllowed)
    async def knowledge_candidate_not_allowed(
        request: Request, error: KnowledgeCandidateNotAllowed
    ) -> JSONResponse:
        return _response(
            request,
            status.HTTP_409_CONFLICT,
            "knowledge_candidate_not_allowed",
            str(error),
        )

    @app.exception_handler(KnowledgeNotFound)
    async def knowledge_not_found(request: Request, error: KnowledgeNotFound) -> JSONResponse:
        return _response(
            request,
            status.HTTP_404_NOT_FOUND,
            "knowledge_not_found",
            "Knowledge entry not found",
        )

    @app.exception_handler(KnowledgeStatusConflict)
    async def knowledge_status_conflict(
        request: Request, error: KnowledgeStatusConflict
    ) -> JSONResponse:
        return _response(
            request,
            status.HTTP_409_CONFLICT,
            "knowledge_status_conflict",
            str(error),
        )

    @app.exception_handler(ServiceProfileNotFound)
    async def service_profile_not_found(
        request: Request, error: ServiceProfileNotFound
    ) -> JSONResponse:
        return _response(
            request,
            status.HTTP_404_NOT_FOUND,
            "service_profile_not_found",
            "Service profile not found",
        )

    @app.exception_handler(ServiceProfileConflict)
    async def service_profile_conflict(
        request: Request, error: ServiceProfileConflict
    ) -> JSONResponse:
        return _response(request, status.HTTP_409_CONFLICT, "service_profile_conflict", str(error))

    @app.exception_handler(InvalidDiagnosisValue)
    async def invalid_diagnosis(request: Request, error: InvalidDiagnosisValue) -> JSONResponse:
        return _response(
            request,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid_diagnosis",
            str(error),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        fields = sorted({".".join(str(part) for part in item["loc"]) for item in error.errors()})
        return _response(
            request,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "request_validation_error",
            "Request validation failed",
            details={"fields": fields},
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> JSONResponse:
        message = error.detail if isinstance(error.detail, str) else "Request failed"
        return _response(request, error.status_code, "http_error", message, headers=error.headers)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception) -> JSONResponse:
        logger.exception("unhandled_api_error", extra={"error_type": type(error).__name__})
        return _response(
            request,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_error",
            "An unexpected error occurred",
        )


def _response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": getattr(request.state, "request_id", None),
    }
    if details:
        error["details"] = details
    return JSONResponse(status_code=status_code, content={"error": error}, headers=headers)
