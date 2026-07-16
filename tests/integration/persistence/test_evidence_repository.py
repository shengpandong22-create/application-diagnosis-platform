from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event

from app_diagnosis.adapters.persistence.database import Database
from app_diagnosis.adapters.persistence.diagnosis_repository import SqlAlchemyDiagnosisRepository
from app_diagnosis.adapters.persistence.evidence_models import EvidenceRecord  # noqa: F401
from app_diagnosis.adapters.persistence.evidence_repository import SqlAlchemyEvidenceRepository
from app_diagnosis.adapters.persistence.models import Base
from app_diagnosis.domain.diagnosis import DiagnosisCase
from app_diagnosis.domain.evidence import (
    Evidence,
    EvidenceReliability,
    EvidenceSource,
    EvidenceType,
    RedactionStatus,
)
from app_diagnosis.ports.evidence_repository import (
    EvidenceAlreadyExists,
    EvidenceDiagnosisNotFound,
)

NOW = datetime(2026, 7, 16, 9, 0, tzinfo=UTC)
DIAGNOSIS_ID = UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
async def database(tmp_path: object) -> Database:
    path = tmp_path / "evidence.db"  # type: ignore[operator]
    database = Database(f"sqlite+aiosqlite:///{path.as_posix()}")
    await database.start()
    event.listen(
        database.engine.sync_engine,
        "connect",
        lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"),
    )
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with database.session_factory.begin() as session:
        await SqlAlchemyDiagnosisRepository(session).add(
            DiagnosisCase.create(
                diagnosis_id=DIAGNOSIS_ID, title="Payment failure", symptom="HTTP 500", now=NOW
            )
        )
    try:
        yield database
    finally:
        await database.dispose()


def new_evidence(
    content: str = "NullPointerException at PaymentService:42",
    *,
    diagnosis_id: UUID = DIAGNOSIS_ID,
    at: datetime = NOW,
) -> Evidence:
    return Evidence.create(
        diagnosis_id=diagnosis_id,
        type=EvidenceType.LOG_EXCERPT,
        source=EvidenceSource.USER_INPUT,
        source_reference="submitted_log:1",
        content=content,
        reliability=EvidenceReliability.HIGH,
        metadata={"line": 1},
        redaction_status=RedactionStatus.NOT_REQUIRED,
        now=at,
    )


async def test_add_get_and_list_round_trip(database: Database) -> None:
    first = new_evidence()
    second = new_evidence("Caused by missing order", at=NOW + timedelta(seconds=1))
    async with database.session_factory.begin() as session:
        repository = SqlAlchemyEvidenceRepository(session)
        await repository.add(second)
        await repository.add(first)
    async with database.session_factory() as session:
        repository = SqlAlchemyEvidenceRepository(session)
        loaded = await repository.get(first.id)
        listed = await repository.list_by_diagnosis(DIAGNOSIS_ID)
    assert loaded == first
    assert listed == [first, second]


async def test_find_by_hash_is_scoped_to_diagnosis(database: Database) -> None:
    evidence = new_evidence()
    async with database.session_factory.begin() as session:
        await SqlAlchemyEvidenceRepository(session).add(evidence)
    async with database.session_factory() as session:
        repository = SqlAlchemyEvidenceRepository(session)
        found = await repository.find_by_hash(DIAGNOSIS_ID, evidence.content_hash)
        absent = await repository.find_by_hash(uuid4(), evidence.content_hash)
    assert found == evidence
    assert absent is None


async def test_duplicate_hash_in_same_diagnosis_is_translated(database: Database) -> None:
    async with database.session_factory.begin() as session:
        await SqlAlchemyEvidenceRepository(session).add(new_evidence())
    async with database.session_factory.begin() as session:
        with pytest.raises(EvidenceAlreadyExists):
            await SqlAlchemyEvidenceRepository(session).add(new_evidence())


async def test_evidence_requires_existing_diagnosis(database: Database) -> None:
    async with database.session_factory.begin() as session:
        with pytest.raises(EvidenceDiagnosisNotFound):
            await SqlAlchemyEvidenceRepository(session).add(new_evidence(diagnosis_id=uuid4()))
