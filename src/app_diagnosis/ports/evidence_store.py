from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from app_diagnosis.domain.evidence import Evidence


@dataclass(frozen=True, slots=True)
class EvidenceCandidate:
    type: str
    source: str
    source_reference: str | None
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class EvidenceStore(Protocol):
    async def add_candidates(
        self, diagnosis_id: UUID, candidates: tuple[EvidenceCandidate, ...]
    ) -> tuple[Evidence, ...]: ...

    async def list_by_diagnosis(self, diagnosis_id: UUID) -> tuple[Evidence, ...]: ...
