from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_diagnosis.adapters.persistence import SqlAlchemyDiagnosisRepository
from app_diagnosis.adapters.persistence.diagnosis_plan_repository import (
    SqlAlchemyDiagnosisPlanRepository,
)
from app_diagnosis.application.diagnoses import DiagnosisNotFound
from app_diagnosis.domain.diagnosis_plan import DiagnosisPlan


class DiagnosisPlanNotFound(LookupError):
    pass


class DiagnosisPlanService:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def get_latest(self, diagnosis_id: UUID) -> DiagnosisPlan:
        """查询某个诊断最新的规则版计划。

        先确认 Diagnosis 存在，再返回最新 Plan。没有运行过 Agent 的诊断可能还没有
        Plan，这时返回 PlanNotFound，API 会映射为 404。
        """
        async with self._sessions() as session:
            diagnosis = await SqlAlchemyDiagnosisRepository(session).get(diagnosis_id)
        if diagnosis is None:
            raise DiagnosisNotFound(str(diagnosis_id))
        plan = await SqlAlchemyDiagnosisPlanRepository(self._sessions).latest_by_diagnosis(
            diagnosis_id
        )
        if plan is None:
            raise DiagnosisPlanNotFound(str(diagnosis_id))
        return plan
