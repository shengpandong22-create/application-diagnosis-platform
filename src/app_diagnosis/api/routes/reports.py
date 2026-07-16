from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from app_diagnosis.application.reports import DiagnosisReportService, render_markdown

router = APIRouter(prefix="/api/v1/diagnoses", tags=["reports"])


def _service(request: Request) -> DiagnosisReportService:
    return request.app.state.report_service


@router.get("/{diagnosis_id}/report")
async def get_report(diagnosis_id: UUID, request: Request) -> dict[str, Any]:
    report = await _service(request).generate(diagnosis_id)
    return {
        "diagnosis": {
            "id": str(report.diagnosis.id),
            "title": report.diagnosis.title,
            "status": report.diagnosis.status.value,
        },
        "conclusion": report.conclusion.model_dump(mode="json") if report.conclusion else None,
        "evidence": [
            {
                "id": str(x.id),
                "type": x.type.value,
                "content": x.content,
                "reliability": x.reliability.value,
            }
            for x in report.evidence
        ],
        "runs": [
            {
                "id": str(x.id),
                "status": x.status,
                "termination_reason": x.termination_reason,
                "round_count": x.round_count,
                "tool_call_count": x.tool_call_count,
            }
            for x in report.runs
        ],
        "confirmations": [
            {
                "id": str(x.id),
                "action": x.action.value,
                "actor": x.actor,
                "comment": x.comment,
                "created_at": x.created_at.isoformat(),
            }
            for x in report.confirmations
        ],
        "generated_at": report.generated_at.isoformat(),
    }


@router.get("/{diagnosis_id}/report.md", response_class=PlainTextResponse)
async def get_report_markdown(diagnosis_id: UUID, request: Request) -> str:
    return render_markdown(await _service(request).generate(diagnosis_id))
