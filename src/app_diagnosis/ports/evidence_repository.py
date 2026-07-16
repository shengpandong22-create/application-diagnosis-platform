from typing import Protocol
from uuid import UUID

from app_diagnosis.domain.evidence import Evidence


class EvidenceRepositoryError(RuntimeError):
    """Base error exposed by the evidence repository port."""


class EvidenceAlreadyExists(EvidenceRepositoryError):
    def __init__(self, diagnosis_id: UUID, content_hash: str) -> None:
        self.diagnosis_id = diagnosis_id
        self.content_hash = content_hash
        super().__init__(f"evidence already exists for diagnosis {diagnosis_id}: {content_hash}")


class EvidenceDiagnosisNotFound(EvidenceRepositoryError):
    def __init__(self, diagnosis_id: UUID) -> None:
        self.diagnosis_id = diagnosis_id
        super().__init__(f"diagnosis does not exist: {diagnosis_id}")


class EvidenceRepository(Protocol):
    async def add(self, evidence: Evidence) -> None: ...

    async def get(self, evidence_id: UUID) -> Evidence | None: ...

    async def find_by_hash(self, diagnosis_id: UUID, content_hash: str) -> Evidence | None: ...

    async def list_by_diagnosis(self, diagnosis_id: UUID) -> list[Evidence]: ...
