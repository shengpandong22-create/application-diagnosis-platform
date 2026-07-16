import asyncio
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_diagnosis.adapters.persistence import SqlAlchemyDiagnosisRepository
from app_diagnosis.adapters.persistence.audit_repository import SqlAlchemyAuditRepository
from app_diagnosis.agent.runtime import AgentBudget, ToolLoopContext, ToolLoopResult, ToolLoopRunner
from app_diagnosis.agent.strategies.base import DiagnosisStrategy
from app_diagnosis.domain.audit import AuditEvent
from app_diagnosis.domain.diagnosis import (
    AgentTerminationReason,
    DiagnosisCase,
    DiagnosisStatus,
    InvalidDiagnosisValue,
)
from app_diagnosis.domain.execution import AgentRun, ToolRun
from app_diagnosis.ports.execution_repository import AgentExecutionRepository


class DiagnosisNotFound(LookupError):
    pass


class DiagnosisRunConflict(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DiagnosisRunDetails:
    run: AgentRun
    tool_runs: tuple[ToolRun, ...]


class DiagnosisApplicationService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        runner: ToolLoopRunner,
        executions: AgentExecutionRepository,
        strategy: DiagnosisStrategy,
        budget: AgentBudget,
        max_input_log_bytes: int,
    ) -> None:
        self._sessions = session_factory
        self._runner = runner
        self._executions = executions
        self._strategy = strategy
        self._budget = budget
        self._max_input_log_bytes = max_input_log_bytes
        self._active_tasks: dict[UUID, asyncio.Task] = {}
        self._active_lock = asyncio.Lock()

    async def create(
        self,
        *,
        title: str,
        symptom: str,
        submitted_log: str | None,
    ) -> DiagnosisCase:
        if submitted_log and len(submitted_log.encode("utf-8")) > self._max_input_log_bytes:
            raise InvalidDiagnosisValue("submitted_log exceeds configured byte limit")
        diagnosis = DiagnosisCase.create(
            title=title,
            symptom=symptom,
            submitted_log=submitted_log,
        )
        async with self._sessions.begin() as session:
            await SqlAlchemyDiagnosisRepository(session).add(diagnosis)
        return diagnosis

    async def get(self, diagnosis_id: UUID) -> DiagnosisCase:
        async with self._sessions() as session:
            diagnosis = await SqlAlchemyDiagnosisRepository(session).get(diagnosis_id)
        if diagnosis is None:
            raise DiagnosisNotFound(str(diagnosis_id))
        return diagnosis

    async def run(
        self,
        diagnosis_id: UUID,
        *,
        actor: str,
        environment: str,
        correlation_id: str,
        max_tool_output_bytes: int,
    ) -> ToolLoopResult:
        task = asyncio.current_task()
        if task is None:
            raise RuntimeError("diagnosis run requires an asyncio task")
        async with self._active_lock:
            if diagnosis_id in self._active_tasks:
                raise DiagnosisRunConflict("diagnosis already has an active run")
            self._active_tasks[diagnosis_id] = task
        try:
            diagnosis = await self._start_investigation(
                diagnosis_id, actor=actor, correlation_id=correlation_id
            )
            result = await self._runner.run(
                diagnosis=diagnosis,
                strategy=self._strategy,
                context=ToolLoopContext(
                    actor=actor,
                    environment=environment,
                    audit_correlation_id=correlation_id,
                    permissions=frozenset({"knowledge:read"}),
                    max_tool_output_bytes=max_tool_output_bytes,
                ),
                budget=self._budget,
            )
            await self._apply_result(diagnosis_id, result)
            return result
        except asyncio.CancelledError:
            await asyncio.shield(self._mark_cancelled(diagnosis_id))
            raise
        finally:
            async with self._active_lock:
                self._active_tasks.pop(diagnosis_id, None)

    async def cancel(self, diagnosis_id: UUID) -> DiagnosisCase:
        async with self._active_lock:
            task = self._active_tasks.get(diagnosis_id)
            if task is not None:
                task.cancel()
        return await self._mark_cancelled(diagnosis_id)

    async def list_runs(self, diagnosis_id: UUID) -> tuple[DiagnosisRunDetails, ...]:
        await self.get(diagnosis_id)
        runs = await self._executions.list_agent_runs(diagnosis_id)
        details: list[DiagnosisRunDetails] = []
        for run in runs:
            details.append(
                DiagnosisRunDetails(
                    run=run,
                    tool_runs=await self._executions.list_tool_runs(run.id),
                )
            )
        return tuple(details)

    async def _start_investigation(
        self, diagnosis_id: UUID, *, actor: str, correlation_id: str
    ) -> DiagnosisCase:
        async with self._sessions.begin() as session:
            repository = SqlAlchemyDiagnosisRepository(session)
            diagnosis = await repository.get(diagnosis_id)
            if diagnosis is None:
                raise DiagnosisNotFound(str(diagnosis_id))
            if diagnosis.status not in {
                DiagnosisStatus.CREATED,
                DiagnosisStatus.INVESTIGATING,
            }:
                raise DiagnosisRunConflict(
                    f"diagnosis cannot run from status {diagnosis.status.value}"
                )
            if diagnosis.status is DiagnosisStatus.CREATED:
                expected_version = diagnosis.version
                diagnosis.start_investigation()
                await repository.save(diagnosis, expected_version=expected_version)
            await SqlAlchemyAuditRepository(session).add(
                AuditEvent.create(
                    actor=actor,
                    action="diagnosis.run_started",
                    target_type="diagnosis",
                    target_id=str(diagnosis.id),
                    summary="Diagnosis investigation run started",
                    correlation_id=correlation_id,
                )
            )
            return diagnosis

    async def _apply_result(self, diagnosis_id: UUID, result: ToolLoopResult) -> None:
        async with self._sessions.begin() as session:
            repository = SqlAlchemyDiagnosisRepository(session)
            diagnosis = await repository.get(diagnosis_id)
            if diagnosis is None:
                raise DiagnosisNotFound(str(diagnosis_id))
            if diagnosis.status is DiagnosisStatus.CANCELLED:
                return
            expected_version = diagnosis.version
            if (
                result.termination_reason is AgentTerminationReason.COMPLETED
                and result.conclusion is not None
            ):
                conclusion = result.conclusion.model_dump(mode="json")
                diagnosis.record_initial_conclusion(
                    conclusion,
                    needs_input=bool(result.conclusion.missing_information),
                )
            else:
                diagnosis.mark_inconclusive()
            await repository.save(diagnosis, expected_version=expected_version)

    async def _mark_cancelled(self, diagnosis_id: UUID) -> DiagnosisCase:
        async with self._sessions.begin() as session:
            repository = SqlAlchemyDiagnosisRepository(session)
            diagnosis = await repository.get(diagnosis_id)
            if diagnosis is None:
                raise DiagnosisNotFound(str(diagnosis_id))
            if diagnosis.status in {DiagnosisStatus.CREATED, DiagnosisStatus.INVESTIGATING}:
                expected_version = diagnosis.version
                diagnosis.cancel()
                await repository.save(diagnosis, expected_version=expected_version)
            elif diagnosis.status is not DiagnosisStatus.CANCELLED:
                raise DiagnosisRunConflict(
                    f"diagnosis cannot be cancelled from status {diagnosis.status.value}"
                )
            return diagnosis
