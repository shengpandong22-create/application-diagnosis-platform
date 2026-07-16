import json
from pathlib import Path

from app_diagnosis.adapters.knowledge import JsonKnowledgeSeedLoader, SqliteKnowledgeSearch
from app_diagnosis.adapters.persistence.database import Database
from app_diagnosis.adapters.persistence.knowledge_models import KnowledgeEntryRecord  # noqa: F401
from app_diagnosis.adapters.persistence.knowledge_repository import SqlAlchemyKnowledgeRepository
from app_diagnosis.adapters.persistence.models import Base
from app_diagnosis.domain.knowledge import KnowledgeStatus


async def test_imports_seeds_idempotently_and_only_searches_confirmed(tmp_path: Path) -> None:
    seed_directory = tmp_path / "seeds"
    seed_directory.mkdir()
    seeds = [
        {
            "id": "npe",
            "title": "NullPointerException",
            "summary": "Check first frame",
            "error_types": ["NPE"],
            "tags": ["java"],
            "source": "test",
            "status": "confirmed",
        },
        {
            "id": "draft",
            "title": "Draft NPE",
            "summary": "Unreviewed",
            "error_types": ["NPE"],
            "tags": [],
            "source": "test",
            "status": "candidate",
        },
        {
            "id": "retired",
            "title": "Old NPE",
            "summary": "Retired",
            "error_types": ["NPE"],
            "tags": [],
            "source": "test",
            "status": "retired",
        },
    ]
    (seed_directory / "entries.json").write_text(json.dumps(seeds), encoding="utf-8")
    database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'search.db').as_posix()}")
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        search = SqliteKnowledgeSearch(
            database.session_factory, JsonKnowledgeSeedLoader(seed_directory)
        )
        first = await search.search("java NullPointerException", limit=5)
        second = await search.search("NPE", limit=5)
        async with database.session_factory() as session:
            confirmed = await SqlAlchemyKnowledgeRepository(session).list_by_status(
                KnowledgeStatus.CONFIRMED
            )
        assert [item.entry_id for item in first] == ["npe"]
        assert first[0].matched_terms == ("java", "nullpointerexception")
        assert [item.entry_id for item in second] == ["npe"]
        assert [item.id for item in confirmed] == ["npe"]
    finally:
        await database.dispose()


async def test_second_adapter_does_not_duplicate_existing_seeds(tmp_path: Path) -> None:
    seed_directory = tmp_path / "seeds"
    seed_directory.mkdir()
    (seed_directory / "entries.json").write_text(
        json.dumps(
            [
                {
                    "id": "timeout",
                    "title": "Timeout",
                    "summary": "Check downstream latency",
                    "error_types": ["ReadTimeout"],
                    "tags": ["rpc"],
                    "source": "test",
                    "status": "confirmed",
                }
            ]
        ),
        encoding="utf-8",
    )
    database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'idempotent.db').as_posix()}")
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        loader = JsonKnowledgeSeedLoader(seed_directory)
        await SqliteKnowledgeSearch(database.session_factory, loader).search("timeout", limit=5)
        matches = await SqliteKnowledgeSearch(database.session_factory, loader).search(
            "timeout", limit=5
        )
        assert len(matches) == 1
    finally:
        await database.dispose()
