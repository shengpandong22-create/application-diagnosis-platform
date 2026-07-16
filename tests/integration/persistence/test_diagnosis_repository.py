from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app_diagnosis.adapters.persistence.database import Database
from app_diagnosis.adapters.persistence.diagnosis_repository import (
    SqlAlchemyDiagnosisRepository,
)
from app_diagnosis.adapters.persistence.models import Base
from app_diagnosis.domain.diagnosis import DiagnosisCase, DiagnosisStatus
from app_diagnosis.ports.diagnosis_repository import (
    ConcurrentDiagnosisUpdate,
    DiagnosisAlreadyExists,
)

NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
DIAGNOSIS_ID = UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
async def database(tmp_path: object) -> Database:
    path = tmp_path / "repository.db"  # type: ignore[operator]
    database = Database(f"sqlite+aiosqlite:///{path.as_posix()}")
    await database.start()
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield database
    finally:
        await database.dispose()


def new_case() -> DiagnosisCase:
    return DiagnosisCase.create(
        diagnosis_id=DIAGNOSIS_ID,
        title="Payment API failure",
        symptom="HTTP 500",
        submitted_log="NullPointerException",
        now=NOW,
    )


async def add_case(database: Database, diagnosis: DiagnosisCase) -> None:
    async with database.session_factory.begin() as session:
        await SqlAlchemyDiagnosisRepository(session).add(diagnosis)


async def load_case(database: Database) -> DiagnosisCase:
    async with database.session_factory() as session:
        diagnosis = await SqlAlchemyDiagnosisRepository(session).get(DIAGNOSIS_ID)
    assert diagnosis is not None
    return diagnosis


async def test_add_and_get_round_trip(database: Database) -> None:
    await add_case(database, new_case())

    loaded = await load_case(database)

    assert loaded.id == DIAGNOSIS_ID
    assert loaded.status is DiagnosisStatus.CREATED
    assert loaded.submitted_log == "NullPointerException"
    assert loaded.created_at == NOW
    assert loaded.updated_at == NOW


async def test_get_returns_none_for_unknown_id(database: Database) -> None:
    async with database.session_factory() as session:
        result = await SqlAlchemyDiagnosisRepository(session).get(DIAGNOSIS_ID)

    assert result is None


async def test_add_translates_duplicate_key(database: Database) -> None:
    await add_case(database, new_case())

    async with database.session_factory.begin() as session:
        with pytest.raises(DiagnosisAlreadyExists):
            await SqlAlchemyDiagnosisRepository(session).add(new_case())


async def test_save_uses_optimistic_version(database: Database) -> None:
    await add_case(database, new_case())
    loaded = await load_case(database)
    loaded.start_investigation(at=NOW + timedelta(seconds=1))

    async with database.session_factory.begin() as session:
        await SqlAlchemyDiagnosisRepository(session).save(loaded, expected_version=0)

    updated = await load_case(database)
    assert updated.status is DiagnosisStatus.INVESTIGATING
    assert updated.version == 1


async def test_save_rejects_stale_writer(database: Database) -> None:
    await add_case(database, new_case())
    first = await load_case(database)
    stale = await load_case(database)
    first.start_investigation(at=NOW + timedelta(seconds=1))
    stale.cancel(at=NOW + timedelta(seconds=2))

    async with database.session_factory.begin() as session:
        await SqlAlchemyDiagnosisRepository(session).save(first, expected_version=0)

    async with database.session_factory.begin() as session:
        with pytest.raises(ConcurrentDiagnosisUpdate):
            await SqlAlchemyDiagnosisRepository(session).save(stale, expected_version=0)

    persisted = await load_case(database)
    assert persisted.status is DiagnosisStatus.INVESTIGATING
    assert persisted.version == 1


async def test_database_readiness(database: Database) -> None:
    assert await database.is_ready()
