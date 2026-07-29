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
            "service_id": str(report.diagnosis.service_id) if report.diagnosis.service_id else None,
            "title": report.diagnosis.title,
            "status": report.diagnosis.status.value,
        },
        "service": (
            {
                "id": str(report.service.id),
                "name": report.service.name,
                "environment": report.service.environment,
                "code_workspace_path": report.service.code_workspace_path,
                "log_directory": report.service.log_directory,
                "config_workspace_path": report.service.config_workspace_path,
                "health_targets": list(report.service.health_targets),
                "tags": list(report.service.tags),
            }
            if report.service
            else None
        ),
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
        "plans": [
            {
                "id": str(x.id),
                "agent_run_id": str(x.agent_run_id),
                "summary": x.summary,
                "hypotheses": list(x.hypotheses),
                "steps": [
                    {
                        "order": step.order,
                        "title": step.title,
                        "description": step.description,
                        "tool_name": step.tool_name,
                        "expected_evidence": list(step.expected_evidence),
                    }
                    for step in x.steps
                ],
                "expected_evidence": list(x.expected_evidence),
                "allowed_tools": list(x.allowed_tools),
                "status": x.status.value,
                "created_at": x.created_at.isoformat(),
            }
            for x in report.plans
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
