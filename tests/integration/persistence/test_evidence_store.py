from datetime import UTC, datetime
from pathlib import Path

from app_diagnosis.adapters.persistence.database import Database
from app_diagnosis.adapters.persistence.diagnosis_repository import SqlAlchemyDiagnosisRepository
from app_diagnosis.adapters.persistence.evidence_models import EvidenceRecord  # noqa: F401
from app_diagnosis.adapters.persistence.evidence_store import SqlAlchemyEvidenceStore
from app_diagnosis.adapters.persistence.models import Base
from app_diagnosis.adapters.redaction import LocalRuleRedactor
from app_diagnosis.domain.diagnosis import DiagnosisCase
from app_diagnosis.domain.evidence import EvidenceType, RedactionStatus
from app_diagnosis.ports.evidence_store import EvidenceCandidate

NOW = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)


async def test_store_redacts_tool_draft_and_deduplicates_by_hash(tmp_path: Path) -> None:
    database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'evidence-store.db').as_posix()}")
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    diagnosis = DiagnosisCase.create(title="Failure", symptom="HTTP 500", now=NOW)
    async with database.session_factory.begin() as session:
        await SqlAlchemyDiagnosisRepository(session).add(diagnosis)
    store = SqlAlchemyEvidenceStore(database.session_factory, LocalRuleRedactor())
    candidate = EvidenceCandidate(
        type="knowledge_entry",
        source="local_knowledge",
        source_reference="npe",
        content="Check logs with password=tool-secret",
        metadata={"score": 1.0},
    )
    try:
        first = await store.add_candidates(diagnosis.id, (candidate,))
        second = await store.add_candidates(diagnosis.id, (candidate,))
        listed = await store.list_by_diagnosis(diagnosis.id)
        assert first[0].id == second[0].id
        assert listed == first
        assert listed[0].type is EvidenceType.KNOWLEDGE_ENTRY
        assert listed[0].redaction_status is RedactionStatus.REDACTED
        assert "tool-secret" not in listed[0].content
        assert listed[0].metadata["untrusted_input"] is True
    finally:
        await database.dispose()
