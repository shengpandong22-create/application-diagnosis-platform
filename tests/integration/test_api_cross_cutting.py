import json
import logging
from collections.abc import Iterator
from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app_diagnosis.api.app import create_app
from app_diagnosis.bootstrap.settings import Settings
from app_diagnosis.observability import JsonFormatter


def client(tmp_path: Path) -> Iterator[TestClient]:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'cross-cutting.db').as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    settings = Settings(
        _env_file=None,
        env="test",
        database_url=database_url,
        knowledge_directory=str(Path("samples/knowledge").resolve()),
    )
    with TestClient(create_app(settings=settings)) as test_client:
        yield test_client


def test_supplied_request_id_is_returned_and_logged(tmp_path: Path) -> None:
    iterator = client(tmp_path)
    test_client = next(iterator)
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    access_logger = logging.getLogger("app_diagnosis.http")
    access_logger.addHandler(handler)
    try:
        response = test_client.get("/health/live", headers={"X-Request-ID": "acceptance-123"})
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == "acceptance-123"
    finally:
        access_logger.removeHandler(handler)
        try:
            iterator.send(None)
        except StopIteration:
            pass
    records = [json.loads(line) for line in stream.getvalue().splitlines() if line]
    access = next(item for item in records if item.get("event") == "http_request_completed")
    assert access["request_id"] == "acceptance-123"
    assert access["method"] == "GET"
    assert access["path"] == "/health/live"
    assert access["status_code"] == 200
    assert "duration_ms" in access


def test_invalid_request_id_is_replaced(tmp_path: Path) -> None:
    iterator = client(tmp_path)
    test_client = next(iterator)
    try:
        response = test_client.get("/health/live", headers={"X-Request-ID": "unsafe value"})
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] != "unsafe value"
        assert len(response.headers["X-Request-ID"]) == 36
    finally:
        try:
            iterator.send(None)
        except StopIteration:
            pass


def test_validation_and_not_found_share_error_contract(tmp_path: Path) -> None:
    iterator = client(tmp_path)
    test_client = next(iterator)
    try:
        invalid = test_client.post(
            "/api/v1/diagnoses",
            headers={"X-Request-ID": "validation-1"},
            json={"title": "", "symptom": ""},
        )
        missing = test_client.get(
            "/api/v1/diagnoses/00000000-0000-0000-0000-000000000000",
            headers={"X-Request-ID": "missing-1"},
        )
    finally:
        try:
            iterator.send(None)
        except StopIteration:
            pass

    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "request_validation_error"
    assert invalid.json()["error"]["request_id"] == "validation-1"
    assert "body.title" in invalid.json()["error"]["details"]["fields"]
    assert missing.status_code == 404
    assert missing.json() == {
        "error": {
            "code": "diagnosis_not_found",
            "message": "Diagnosis not found",
            "request_id": "missing-1",
        }
    }
