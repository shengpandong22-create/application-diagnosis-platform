from typing import Protocol
from uuid import UUID

from app_diagnosis.domain.diagnosis_plan import DiagnosisPlan


class DiagnosisPlanRepository(Protocol):
    async def add(self, plan: DiagnosisPlan) -> None: ...

    async def get_by_agent_run(self, agent_run_id: UUID) -> DiagnosisPlan | None: ...

    async def latest_by_diagnosis(self, diagnosis_id: UUID) -> DiagnosisPlan | None: ...

    async def list_by_diagnosis(self, diagnosis_id: UUID) -> tuple[DiagnosisPlan, ...]: ...
