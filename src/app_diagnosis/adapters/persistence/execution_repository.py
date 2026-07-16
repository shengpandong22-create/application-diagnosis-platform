from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_diagnosis.adapters.persistence.models import AgentRunRecord, ToolRunRecord
from app_diagnosis.domain.diagnosis import AgentTerminationReason
from app_diagnosis.domain.execution import (
    AgentRun,
    AgentRunStatus,
    ToolRun,
    ToolRunStatus,
)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class SqlAlchemyAgentExecutionRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add_agent_run(self, run: AgentRun) -> None:
        async with self._session_factory.begin() as session:
            session.add(self._to_agent_record(run))

    async def update_agent_run(self, run: AgentRun) -> None:
        async with self._session_factory.begin() as session:
            await session.execute(
                update(AgentRunRecord)
                .where(AgentRunRecord.id == str(run.id))
                .values(**self._agent_values(run))
            )

    async def get_agent_run(self, run_id: UUID) -> AgentRun | None:
        async with self._session_factory() as session:
            record = await session.get(AgentRunRecord, str(run_id))
        return None if record is None else self._to_agent_domain(record)

    async def list_agent_runs(self, diagnosis_id: UUID) -> tuple[AgentRun, ...]:
        async with self._session_factory() as session:
            records = (
                await session.scalars(
                    select(AgentRunRecord)
                    .where(AgentRunRecord.diagnosis_id == str(diagnosis_id))
                    .order_by(AgentRunRecord.started_at.desc(), AgentRunRecord.id.desc())
                )
            ).all()
        return tuple(self._to_agent_domain(record) for record in records)

    async def add_tool_run(self, run: ToolRun) -> None:
        async with self._session_factory.begin() as session:
            session.add(
                ToolRunRecord(
                    id=str(run.id),
                    agent_run_id=str(run.agent_run_id),
                    tool_call_id=run.tool_call_id,
                    tool_name=run.tool_name,
                    arguments_json=run.arguments_json,
                    status=run.status.value,
                    result_json=run.result_json,
                    duration_ms=run.duration_ms,
                    error_code=run.error_code,
                    created_at=run.created_at,
                )
            )

    async def list_tool_runs(self, agent_run_id: UUID) -> tuple[ToolRun, ...]:
        async with self._session_factory() as session:
            records = (
                await session.scalars(
                    select(ToolRunRecord)
                    .where(ToolRunRecord.agent_run_id == str(agent_run_id))
                    .order_by(ToolRunRecord.created_at, ToolRunRecord.id)
                )
            ).all()
        return tuple(self._to_tool_domain(record) for record in records)

    @classmethod
    def _to_agent_record(cls, run: AgentRun) -> AgentRunRecord:
        return AgentRunRecord(
            id=str(run.id), diagnosis_id=str(run.diagnosis_id), **cls._agent_values(run)
        )

    @staticmethod
    def _agent_values(run: AgentRun) -> dict:
        return {
            "strategy": run.strategy,
            "status": run.status.value,
            "termination_reason": run.termination_reason.value if run.termination_reason else None,
            "model": run.model,
            "round_count": run.round_count,
            "tool_call_count": run.tool_call_count,
            "input_tokens": run.input_tokens,
            "output_tokens": run.output_tokens,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "error_code": run.error_code,
        }

    @staticmethod
    def _to_agent_domain(record: AgentRunRecord) -> AgentRun:
        return AgentRun(
            id=UUID(record.id),
            diagnosis_id=UUID(record.diagnosis_id),
            strategy=record.strategy,
            status=AgentRunStatus(record.status),
            termination_reason=(
                AgentTerminationReason(record.termination_reason)
                if record.termination_reason
                else None
            ),
            model=record.model,
            round_count=record.round_count,
            tool_call_count=record.tool_call_count,
            input_tokens=record.input_tokens,
            output_tokens=record.output_tokens,
            started_at=_as_utc(record.started_at),
            finished_at=_as_utc(record.finished_at) if record.finished_at else None,
            error_code=record.error_code,
        )

    @staticmethod
    def _to_tool_domain(record: ToolRunRecord) -> ToolRun:
        return ToolRun(
            id=UUID(record.id),
            agent_run_id=UUID(record.agent_run_id),
            tool_call_id=record.tool_call_id,
            tool_name=record.tool_name,
            arguments_json=record.arguments_json,
            status=ToolRunStatus(record.status),
            result_json=record.result_json,
            duration_ms=record.duration_ms,
            error_code=record.error_code,
            created_at=_as_utc(record.created_at),
        )
