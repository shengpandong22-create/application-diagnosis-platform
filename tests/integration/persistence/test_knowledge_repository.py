from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app_diagnosis.adapters.persistence.database import Database
from app_diagnosis.adapters.persistence.knowledge_models import KnowledgeEntryRecord  # noqa: F401
from app_diagnosis.adapters.persistence.knowledge_repository import SqlAlchemyKnowledgeRepository
from app_diagnosis.adapters.persistence.models import Base
from app_diagnosis.domain.knowledge import KnowledgeEntry, KnowledgeStatus
from app_diagnosis.ports.knowledge_repository import KnowledgeAlreadyExists

NOW = datetime(2026, 7, 16, 10, 0, tzinfo=UTC)


@pytest.fixture
async def database(tmp_path: Path) -> Database:
    database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'knowledge.db').as_posix()}")
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield database
    finally:
        await database.dispose()


def entry(
    entry_id: str = "npe", status: KnowledgeStatus = KnowledgeStatus.CONFIRMED
) -> KnowledgeEntry:
    return KnowledgeEntry.create(
        entry_id=entry_id,
        title="NullPointerException",
        summary="Check the first application frame",
        source="test",
        error_types=("NPE",),
        tags=("java",),
        status=status,
        now=NOW,
    )


async def test_round_trip_status_listing_and_save(database: Database) -> None:
    async with database.session_factory.begin() as session:
        repository = SqlAlchemyKnowledgeRepository(session)
        await repository.add(entry("confirmed"))
        await repository.add(entry("candidate", KnowledgeStatus.CANDIDATE))
    async with database.session_factory.begin() as session:
        repository = SqlAlchemyKnowledgeRepository(session)
        candidate = await repository.get("candidate")
        assert candidate is not None
        await repository.save(
            candidate.with_status(KnowledgeStatus.CONFIRMED, at=NOW + timedelta(seconds=1))
        )
    async with database.session_factory() as session:
        confirmed = await SqlAlchemyKnowledgeRepository(session).list_by_status(
            KnowledgeStatus.CONFIRMED
        )
    assert [item.id for item in confirmed] == ["candidate", "confirmed"]


async def test_duplicate_id_is_translated(database: Database) -> None:
    async with database.session_factory.begin() as session:
        await SqlAlchemyKnowledgeRepository(session).add(entry())
    async with database.session_factory.begin() as session:
        with pytest.raises(KnowledgeAlreadyExists):
            await SqlAlchemyKnowledgeRepository(session).add(entry())
