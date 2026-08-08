from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_diagnosis.adapters.persistence import SqlAlchemyDiagnosisRepository
from app_diagnosis.adapters.persistence.diagnosis_plan_repository import (
    SqlAlchemyDiagnosisPlanRepository,
)
from app_diagnosis.adapters.persistence.incident_repository import SqlAlchemyIncidentRepository
from app_diagnosis.application.diagnoses import DiagnosisNotFound
from app_diagnosis.domain.execution import AgentRun, ToolRun
from app_diagnosis.domain.trace import AgentRunTrace, DiagnosisTrace, TraceEvent
from app_diagnosis.domain.trace.models import TraceEventType
from app_diagnosis.ports.execution_repository import AgentExecutionRepository


class DiagnosisTraceService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        executions: AgentExecutionRepository,
    ) -> None:
        self._sessions = session_factory
        self._executions = executions

    async def get(self, diagnosis_id: UUID) -> DiagnosisTrace:
        async with self._sessions() as session:
            diagnosis = await SqlAlchemyDiagnosisRepository(session).get(diagnosis_id)
        if diagnosis is None:
            raise DiagnosisNotFound(str(diagnosis_id))
        incidents = await SqlAlchemyIncidentRepository(self._sessions).list(
            service_id=diagnosis.service_id
        )
        incident = next((item for item in incidents if item.diagnosis_id == diagnosis_id), None)
        runs = await self._executions.list_agent_runs(diagnosis_id)
        return DiagnosisTrace(
            diagnosis_id=diagnosis.id,
            diagnosis_status=diagnosis.status.value,
            incident_id=incident.id if incident else None,
            incident_fingerprint=incident.fingerprint if incident else None,
            runs=tuple([await self._run_trace(run) for run in runs]),
        )

    async def _run_trace(self, run: AgentRun) -> AgentRunTrace:
        tool_runs = await self._executions.list_tool_runs(run.id)
        events = _events(run, tool_runs)
        plan = await SqlAlchemyDiagnosisPlanRepository(self._sessions).get_by_agent_run(run.id)
        duration_ms = None
        if run.finished_at is not None:
            duration_ms = max(0, int((run.finished_at - run.started_at).total_seconds() * 1000))
        return AgentRunTrace(
            agent_run_id=run.id,
            strategy=run.strategy,
            status=run.status.value,
            termination_reason=run.termination_reason.value if run.termination_reason else None,
            model=run.model,
            round_count=run.round_count,
            tool_call_count=run.tool_call_count,
            input_tokens=run.input_tokens,
            output_tokens=run.output_tokens,
            started_at=run.started_at,
            finished_at=run.finished_at,
            duration_ms=duration_ms,
            plan=plan,
            events=events,
        )


def _events(run: AgentRun, tool_runs: tuple[ToolRun, ...]) -> tuple[TraceEvent, ...]:
    events = [
        TraceEvent(
            type=TraceEventType.RUN_STARTED,
            sequence=1,
            occurred_at=run.started_at,
            summary=f"Agent run started with strategy {run.strategy}",
            status="running",
        )
    ]
    for tool_run in tool_runs:
        events.append(
            TraceEvent(
                type=TraceEventType.TOOL_CALL,
                sequence=0,
                occurred_at=tool_run.created_at,
                summary=f"{tool_run.tool_name} {tool_run.status.value}",
                tool_name=tool_run.tool_name,
                status=tool_run.status.value,
                duration_ms=tool_run.duration_ms,
                error_code=tool_run.error_code,
                evidence_ids=_evidence_ids(tool_run.result_json),
            )
        )
    if run.finished_at is not None:
        reason = run.termination_reason.value if run.termination_reason else run.status.value
        events.append(
            TraceEvent(
                type=TraceEventType.RUN_FINISHED,
                sequence=0,
                occurred_at=run.finished_at,
                summary=f"Agent run finished: {reason}",
                status=run.status.value,
                error_code=run.error_code,
            )
        )
    ordered = sorted(events, key=lambda item: (item.occurred_at, _event_order(item.type)))
    return tuple(
        TraceEvent(
            type=item.type,
            sequence=index,
            occurred_at=item.occurred_at,
            summary=item.summary,
            tool_name=item.tool_name,
            status=item.status,
            duration_ms=item.duration_ms,
            error_code=item.error_code,
            evidence_ids=item.evidence_ids,
        )
        for index, item in enumerate(ordered, start=1)
    )


def _event_order(event_type: TraceEventType) -> int:
    return {
        TraceEventType.RUN_STARTED: 0,
        TraceEventType.TOOL_CALL: 1,
        TraceEventType.RUN_FINISHED: 2,
    }[event_type]


def _evidence_ids(result: dict | None) -> tuple[UUID, ...]:
    if not result:
        return ()
    values = result.get("evidence_ids")
    if not isinstance(values, list):
        return ()
    parsed: list[UUID] = []
    for value in values:
        try:
            parsed.append(UUID(str(value)))
        except ValueError:
            continue
    return tuple(parsed)
