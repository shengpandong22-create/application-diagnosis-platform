import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app_diagnosis.api.app import create_app
from app_diagnosis.bootstrap.settings import Settings


def test_create_list_filter_and_duplicate_candidate_knowledge(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'knowledge-api.db').as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    settings = Settings(
        _env_file=None,
        env="test",
        database_url=database_url,
        knowledge_directory=str(Path("samples/knowledge").resolve()),
    )
    with TestClient(create_app(settings=settings)) as api:
        created = api.post(
            "/api/v1/knowledge",
            json={
                "id": "custom-npe",
                "title": "NPE password=title-secret",
                "summary": "Inspect stack; api_key=summary-secret",
                "error_types": ["NullPointerException"],
                "tags": ["java"],
                "source": "local-user",
            },
        )
        assert created.status_code == 201
        assert created.json()["status"] == "candidate"
        assert "title-secret" not in created.json()["title"]
        assert "summary-secret" not in created.json()["summary"]

        candidates = api.get("/api/v1/knowledge", params={"status": "candidate"})
        assert candidates.status_code == 200
        assert [item["id"] for item in candidates.json()] == ["custom-npe"]
        assert api.get("/api/v1/knowledge", params={"status": "confirmed"}).json() == []

        duplicate = api.post(
            "/api/v1/knowledge",
            json={
                "id": "custom-npe",
                "title": "Duplicate",
                "summary": "Duplicate",
            },
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["error"]["code"] == "knowledge_conflict"

        confirmed = api.patch(
            "/api/v1/knowledge/custom-npe/status",
            json={"status": "confirmed"},
            headers={"X-Request-ID": "knowledge-review-1"},
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["status"] == "confirmed"
        assert (
            api.get("/api/v1/knowledge", params={"status": "confirmed"}).json()[0]["id"]
            == "custom-npe"
        )

        repeated = api.patch("/api/v1/knowledge/custom-npe/status", json={"status": "confirmed"})
        assert repeated.status_code == 200

        retired = api.patch("/api/v1/knowledge/custom-npe/status", json={"status": "retired"})
        assert retired.status_code == 200
        assert retired.json()["status"] == "retired"

        invalid = api.patch("/api/v1/knowledge/custom-npe/status", json={"status": "confirmed"})
        assert invalid.status_code == 409
        assert invalid.json()["error"]["code"] == "knowledge_status_conflict"

        missing = api.patch("/api/v1/knowledge/missing/status", json={"status": "confirmed"})
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "knowledge_not_found"

    with sqlite3.connect(tmp_path / "knowledge-api.db") as connection:
        status_events = list(
            connection.execute(
                "SELECT action, summary, correlation_id FROM audit_events "
                "WHERE target_id = ? ORDER BY created_at",
                ("custom-npe",),
            )
        )
    assert [item[0] for item in status_events].count("knowledge.status_changed") == 2
    assert any("candidate to confirmed" in item[1] for item in status_events)
    assert any(item[2] == "knowledge-review-1" for item in status_events)
