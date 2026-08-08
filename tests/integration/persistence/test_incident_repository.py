import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app_diagnosis.adapters.persistence.database import Database
from app_diagnosis.adapters.persistence.incident_repository import SqlAlchemyIncidentRepository
from app_diagnosis.adapters.persistence.models import Base
from app_diagnosis.adapters.persistence.service_profile_repository import (
    SqlAlchemyServiceProfileRepository,
)
from app_diagnosis.domain.incident import Incident, IncidentStatus
from app_diagnosis.domain.service_profile import ServiceProfile

NOW = datetime(2026, 8, 8, 10, 0, tzinfo=UTC)
SERVICE_ID = UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
async def database(tmp_path: object) -> Database:
    path = tmp_path / "incidents.db"  # type: ignore[operator]
    database = Database(f"sqlite+aiosqlite:///{path.as_posix()}")
    await database.start()
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await SqlAlchemyServiceProfileRepository(database.session_factory).add(
        ServiceProfile.create(
            service_id=SERVICE_ID, name="java-lab", environment="local", now=NOW
        )
    )
    try:
        yield database
    finally:
        await database.dispose()


def candidate(*, bucket: str = "10:00") -> Incident:
    start = NOW if bucket == "10:00" else NOW + timedelta(minutes=15)
    return Incident(
        id=uuid4(), service_id=SERVICE_ID, environment="local", fingerprint="a" * 64,
        fingerprint_version="v1", aggregation_key=f"key:{bucket}", diagnosis_id=None,
        status=IncidentStatus.OPEN,
        exception_type="NullPointerException", sample_message="safe message", occurrence_count=1,
        first_seen_at=start, last_seen_at=start, window_started_at=start,
        window_ends_at=start + timedelta(minutes=15), created_at=start, updated_at=start,
    )


async def test_repeated_event_increments_occurrence(database: Database) -> None:
    repository = SqlAlchemyIncidentRepository(database.session_factory)
    first = await repository.aggregate(candidate())
    second = await repository.aggregate(candidate())
    assert first.is_novel is True
    assert second.is_novel is False
    assert second.incident.occurrence_count == 2


async def test_new_window_creates_new_incident(database: Database) -> None:
    repository = SqlAlchemyIncidentRepository(database.session_factory)
    await repository.aggregate(candidate())
    result = await repository.aggregate(candidate(bucket="10:15"))
    assert result.is_novel is True
    assert len(await repository.list(service_id=SERVICE_ID)) == 2


async def test_out_of_order_event_does_not_move_seen_range_backwards(database: Database) -> None:
    repository = SqlAlchemyIncidentRepository(database.session_factory)
    later = candidate()
    earlier = replace(
        later,
        id=uuid4(),
        first_seen_at=NOW - timedelta(minutes=2),
        last_seen_at=NOW - timedelta(minutes=2),
    )
    await repository.aggregate(later)
    result = await repository.aggregate(earlier)
    assert result.incident.first_seen_at == NOW - timedelta(minutes=2)
    assert result.incident.last_seen_at == NOW


async def test_concurrent_events_create_one_incident(database: Database) -> None:
    repository = SqlAlchemyIncidentRepository(database.session_factory)
    results = await asyncio.gather(*(repository.aggregate(candidate()) for _ in range(8)))
    incidents = await repository.list(service_id=SERVICE_ID)
    assert sum(result.is_novel for result in results) == 1
    assert len(incidents) == 1
    assert incidents[0].occurrence_count == 8
