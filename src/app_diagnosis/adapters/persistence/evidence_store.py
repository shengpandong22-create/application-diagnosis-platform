from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_diagnosis.adapters.persistence.evidence_repository import SqlAlchemyEvidenceRepository
from app_diagnosis.domain.evidence import (
    Evidence,
    EvidenceReliability,
    EvidenceSource,
    EvidenceType,
)
from app_diagnosis.ports.evidence_store import EvidenceCandidate
from app_diagnosis.ports.redaction import Redactor


class SqlAlchemyEvidenceStore:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        redactor: Redactor,
    ) -> None:
        self._sessions = session_factory
        self._redactor = redactor

    async def add_candidates(
        self, diagnosis_id: UUID, candidates: tuple[EvidenceCandidate, ...]
    ) -> tuple[Evidence, ...]:
        stored: list[Evidence] = []
        base_time = datetime.now(UTC)
        async with self._sessions.begin() as session:
            repository = SqlAlchemyEvidenceRepository(session)
            for index, candidate in enumerate(candidates):
                safe = self._redactor.redact(candidate.content)
                content_hash = Evidence.hash_content(safe.content.strip())
                existing = await repository.find_by_hash(diagnosis_id, content_hash)
                if existing is not None:
                    stored.append(existing)
                    continue
                evidence = Evidence.create(
                    diagnosis_id=diagnosis_id,
                    type=EvidenceType(candidate.type),
                    source=EvidenceSource(candidate.source),
                    source_reference=candidate.source_reference,
                    content=safe.content,
                    reliability=_reliability(EvidenceType(candidate.type)),
                    metadata={
                        **candidate.metadata,
                        "untrusted_input": True,
                        "redaction_count": safe.redaction_count,
                        "redaction_categories": list(safe.matched_categories),
                    },
                    redaction_status=safe.status,
                    now=base_time + timedelta(microseconds=index),
                )
                await repository.add(evidence)
                stored.append(evidence)
        return tuple(stored)

    async def list_by_diagnosis(self, diagnosis_id: UUID) -> tuple[Evidence, ...]:
        async with self._sessions() as session:
            items = await SqlAlchemyEvidenceRepository(session).list_by_diagnosis(diagnosis_id)
        return tuple(items)


def _reliability(evidence_type: EvidenceType) -> EvidenceReliability:
    if evidence_type is EvidenceType.LOG_EXCERPT:
        return EvidenceReliability.HIGH
    return EvidenceReliability.MEDIUM
