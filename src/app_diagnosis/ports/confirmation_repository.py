from typing import Protocol
from uuid import UUID

from app_diagnosis.domain.confirmation import Confirmation


class ConfirmationRepository(Protocol):
    async def add(self, confirmation: Confirmation) -> None: ...

    async def list_by_diagnosis(self, diagnosis_id: UUID) -> tuple[Confirmation, ...]: ...
