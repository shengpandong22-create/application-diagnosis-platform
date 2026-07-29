from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_diagnosis.adapters.persistence.models import DiagnosisPlanRecord
from app_diagnosis.domain.diagnosis_plan import DiagnosisPlan, DiagnosisPlanStatus, PlanStep


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class SqlAlchemyDiagnosisPlanRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add(self, plan: DiagnosisPlan) -> None:
        async with self._session_factory.begin() as session:
            session.add(self._to_record(plan))

    async def get_by_agent_run(self, agent_run_id: UUID) -> DiagnosisPlan | None:
        async with self._session_factory() as session:
            record = (
                await session.scalars(
                    select(DiagnosisPlanRecord).where(
                        DiagnosisPlanRecord.agent_run_id == str(agent_run_id)
                    )
                )
            ).first()
        return None if record is None else self._to_domain(record)

    async def latest_by_diagnosis(self, diagnosis_id: UUID) -> DiagnosisPlan | None:
        async with self._session_factory() as session:
            record = (
                await session.scalars(
                    select(DiagnosisPlanRecord)
                    .where(DiagnosisPlanRecord.diagnosis_id == str(diagnosis_id))
                    .order_by(
                        DiagnosisPlanRecord.created_at.desc(),
                        DiagnosisPlanRecord.id.desc(),
                    )
                    .limit(1)
                )
            ).first()
        return None if record is None else self._to_domain(record)

    async def list_by_diagnosis(self, diagnosis_id: UUID) -> tuple[DiagnosisPlan, ...]:
        async with self._session_factory() as session:
            records = (
                await session.scalars(
                    select(DiagnosisPlanRecord)
                    .where(DiagnosisPlanRecord.diagnosis_id == str(diagnosis_id))
                    .order_by(DiagnosisPlanRecord.created_at, DiagnosisPlanRecord.id)
                )
            ).all()
        return tuple(self._to_domain(record) for record in records)

    @staticmethod
    def _to_record(plan: DiagnosisPlan) -> DiagnosisPlanRecord:
        return DiagnosisPlanRecord(
            id=str(plan.id),
            diagnosis_id=str(plan.diagnosis_id),
            agent_run_id=str(plan.agent_run_id),
            summary=plan.summary,
            hypotheses_json=list(plan.hypotheses),
            steps_json=[
                {
                    "order": item.order,
                    "title": item.title,
                    "description": item.description,
                    "tool_name": item.tool_name,
                    "expected_evidence": list(item.expected_evidence),
                }
                for item in plan.steps
            ],
            expected_evidence_json=list(plan.expected_evidence),
            allowed_tools_json=list(plan.allowed_tools),
            status=plan.status.value,
            created_at=plan.created_at,
        )

    @staticmethod
    def _to_domain(record: DiagnosisPlanRecord) -> DiagnosisPlan:
        return DiagnosisPlan(
            id=UUID(record.id),
            diagnosis_id=UUID(record.diagnosis_id),
            agent_run_id=UUID(record.agent_run_id),
            summary=record.summary,
            hypotheses=tuple(record.hypotheses_json),
            steps=tuple(
                PlanStep(
                    order=int(item["order"]),
                    title=str(item["title"]),
                    description=str(item["description"]),
                    tool_name=item["tool_name"] if item.get("tool_name") else None,
                    expected_evidence=tuple(str(value) for value in item["expected_evidence"]),
                )
                for item in record.steps_json
            ),
            expected_evidence=tuple(record.expected_evidence_json),
            allowed_tools=tuple(record.allowed_tools_json),
            status=DiagnosisPlanStatus(record.status),
            created_at=_as_utc(record.created_at),
        )
