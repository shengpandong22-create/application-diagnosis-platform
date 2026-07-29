from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_diagnosis.adapters.persistence.confirmation_repository import (
    SqlAlchemyConfirmationRepository,
)
from app_diagnosis.adapters.persistence.diagnosis_plan_repository import (
    SqlAlchemyDiagnosisPlanRepository,
)
from app_diagnosis.adapters.persistence.diagnosis_repository import SqlAlchemyDiagnosisRepository
from app_diagnosis.adapters.persistence.evidence_repository import SqlAlchemyEvidenceRepository
from app_diagnosis.adapters.persistence.service_profile_repository import (
    SqlAlchemyServiceProfileRepository,
)
from app_diagnosis.agent.schemas import DiagnosisConclusion
from app_diagnosis.application.diagnoses import DiagnosisNotFound
from app_diagnosis.domain.report import DiagnosisReport, ReportRun
from app_diagnosis.ports.execution_repository import AgentExecutionRepository


class DiagnosisReportService:
    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], executions: AgentExecutionRepository
    ) -> None:
        self._sessions = sessions
        self._executions = executions

    async def generate(self, diagnosis_id: UUID) -> DiagnosisReport:
        async with self._sessions() as session:
            diagnosis = await SqlAlchemyDiagnosisRepository(session).get(diagnosis_id)
            if diagnosis is None:
                raise DiagnosisNotFound(str(diagnosis_id))
            service = (
                await SqlAlchemyServiceProfileRepository(self._sessions).get(diagnosis.service_id)
                if diagnosis.service_id
                else None
            )
            evidence = await SqlAlchemyEvidenceRepository(session).list_by_diagnosis(diagnosis_id)
            confirmations = await SqlAlchemyConfirmationRepository(session).list_by_diagnosis(
                diagnosis_id
            )
        plans = await SqlAlchemyDiagnosisPlanRepository(self._sessions).list_by_diagnosis(
            diagnosis_id
        )
        conclusion = None
        if diagnosis.conclusion:
            try:
                conclusion = DiagnosisConclusion.model_validate(diagnosis.conclusion)
            except ValidationError as error:
                raise ValueError("stored diagnosis conclusion is invalid") from error
        runs = await self._executions.list_agent_runs(diagnosis_id)
        return DiagnosisReport(
            diagnosis=diagnosis,
            service=service,
            conclusion=conclusion,
            evidence=evidence,
            plans=plans,
            runs=tuple(
                ReportRun(
                    id=item.id,
                    status=item.status.value,
                    termination_reason=item.termination_reason.value
                    if item.termination_reason
                    else None,
                    model=item.model,
                    round_count=item.round_count,
                    tool_call_count=item.tool_call_count,
                    started_at=item.started_at,
                    finished_at=item.finished_at,
                )
                for item in runs
            ),
            confirmations=confirmations,
            generated_at=datetime.now(UTC),
        )


def render_markdown(report: DiagnosisReport) -> str:
    d = report.diagnosis
    lines = [
        f"# 诊断报告：{d.title}",
        "",
        f"- Diagnosis ID: `{d.id}`",
        f"- Service ID: `{d.service_id}`" if d.service_id else "- Service ID: 无",
        f"- 状态: `{d.status.value}`",
        f"- 生成时间: `{report.generated_at.isoformat()}`",
        "",
        "## 症状",
        "",
        d.symptom,
    ]
    if report.service:
        lines += [
            "",
            "## 服务",
            "",
            f"- 名称: `{report.service.name}`",
            f"- 环境: `{report.service.environment}`",
            f"- 源码路径: `{report.service.code_workspace_path or '未配置'}`",
            f"- 日志目录: `{report.service.log_directory or '未配置'}`",
        ]
    if report.conclusion:
        c = report.conclusion
        lines += ["", "## 事实", ""]
        lines += _findings(c.facts) or ["- 无"]
        lines += ["", "## 候选根因", ""]
        lines += _findings(c.root_causes) or ["- 无"]
        lines += ["", "## 验证与处置建议", ""] + ([f"- {x}" for x in c.recommendations] or ["- 无"])
        lines += ["", "## 缺失信息", ""] + ([f"- {x}" for x in c.missing_information] or ["- 无"])
    lines += ["", "## Evidence", ""]
    lines += [
        f"- `{x.id}` · {x.type.value} · reliability={x.reliability.value}: {x.content}"
        for x in report.evidence
    ] or ["- 无"]
    lines += ["", "## 诊断计划", ""]
    if report.plans:
        latest = report.plans[-1]
        lines += [
            f"- Plan ID: `{latest.id}`",
            f"- AgentRun ID: `{latest.agent_run_id}`",
            f"- 状态: `{latest.status.value}`",
            f"- 摘要: {latest.summary}",
            f"- 允许工具: {', '.join(f'`{x}`' for x in latest.allowed_tools) or '无'}",
            "",
            "### 计划步骤",
            "",
        ]
        lines += [
            f"{step.order}. {step.title}：{step.description}"
            + (f"（工具: `{step.tool_name}`）" if step.tool_name else "")
            for step in latest.steps
        ]
    else:
        lines += ["- 尚无 DiagnosisPlan"]
    lines += ["", "## 人工决定", ""]
    lines += [
        f"- {x.created_at.isoformat()} · {x.actor} · `{x.action.value}`"
        for x in report.confirmations
    ] or ["- 尚无人工决定"]
    lines += ["", "## 运行摘要", ""]
    lines += [
        f"- `{x.id}` · {x.status} · termination={x.termination_reason or 'n/a'} "
        f"· rounds={x.round_count} · tools={x.tool_call_count}"
        for x in report.runs
    ] or ["- 尚无 AgentRun"]
    return "\n".join(lines) + "\n"


def _findings(items) -> list[str]:
    return [
        f"- **{x.status}** {x.statement}"
        f"（Evidence: {', '.join(f'`{i}`' for i in x.evidence_ids) or '无'}）"
        for x in items
    ]
