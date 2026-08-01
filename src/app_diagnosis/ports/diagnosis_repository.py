from typing import Protocol
from uuid import UUID

from app_diagnosis.domain.diagnosis import DiagnosisCase


class DiagnosisRepositoryError(RuntimeError):
    """Base error exposed by the diagnosis repository port."""


class DiagnosisAlreadyExists(DiagnosisRepositoryError):
    def __init__(self, diagnosis_id: UUID) -> None:
        self.diagnosis_id = diagnosis_id
        super().__init__(f"diagnosis already exists: {diagnosis_id}")


class ConcurrentDiagnosisUpdate(DiagnosisRepositoryError):
    def __init__(self, diagnosis_id: UUID, expected_version: int) -> None:
        self.diagnosis_id = diagnosis_id
        self.expected_version = expected_version
        super().__init__(f"diagnosis {diagnosis_id} was not at expected version {expected_version}")


class DiagnosisRepository(Protocol):
    async def add(self, diagnosis: DiagnosisCase) -> None: ...

    async def get(self, diagnosis_id: UUID) -> DiagnosisCase | None: ...

    async def list_by_service(self, service_id: UUID) -> tuple[DiagnosisCase, ...]: ...

    async def save(self, diagnosis: DiagnosisCase, *, expected_version: int) -> None: ...
