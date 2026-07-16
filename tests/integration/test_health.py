from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app_diagnosis.api.app import create_app
from app_diagnosis.bootstrap.settings import Settings


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'health.db').as_posix()}",
    )
    with TestClient(create_app(settings=settings)) as test_client:
        yield test_client


def test_liveness(client: TestClient) -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness(client: TestClient) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
