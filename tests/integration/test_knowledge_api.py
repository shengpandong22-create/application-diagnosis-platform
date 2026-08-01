import json
import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from tests.fakes.llm import FakeLLMClient

from app_diagnosis.adapters.persistence import Database
from app_diagnosis.api.app import create_app
from app_diagnosis.bootstrap.container import build_diagnosis_service
from app_diagnosis.bootstrap.settings import Settings
from app_diagnosis.ports.llm import ChatMessage, FinishReason, LLMResponse, LLMUsage


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


def test_confirmed_diagnosis_creates_idempotent_candidate_knowledge(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'diagnosis-knowledge.db').as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    settings = Settings(
        _env_file=None,
        env="test",
        database_url=database_url,
        knowledge_directory=str(Path("samples/knowledge").resolve()),
    )
    conclusion = json.dumps(
        {
            "symptom_summary": "Order lookup raises NullPointerException.",
            "facts": [],
            "root_causes": [
                {
                    "statement": "customerName is null before trim().",
                    "status": "possible",
                    "evidence_ids": [],
                }
            ],
            "recommendations": ["Add a null guard and regression test."],
            "missing_information": [],
        }
    )
    fake = FakeLLMClient(
        [
            LLMResponse(
                message=ChatMessage.assistant(conclusion),
                model="fake-model",
                finish_reason=FinishReason.STOP,
                usage=LLMUsage(input_tokens=10, output_tokens=5, total_tokens=15),
            )
        ]
    )
    database = Database(database_url)
    diagnosis_service, _ = build_diagnosis_service(
        settings=settings,
        database=database,
        llm_client=fake,
    )
    with TestClient(
        create_app(settings=settings, database=database, diagnosis_service=diagnosis_service)
    ) as api:
        diagnosis = api.post(
            "/api/v1/diagnoses",
            json={"title": "NPE in order lookup", "symptom": "NullPointerException"},
        ).json()

        too_early = api.post(f"/api/v1/diagnoses/{diagnosis['id']}/knowledge-candidates")
        assert too_early.status_code == 409
        assert too_early.json()["error"]["code"] == "knowledge_candidate_not_allowed"

        assert api.post(f"/api/v1/diagnoses/{diagnosis['id']}/runs").status_code == 200
        confirmed = api.post(
            f"/api/v1/diagnoses/{diagnosis['id']}/confirmation",
            json={"action": "confirm", "comment": "Reproduced and verified."},
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["diagnosis"]["status"] == "confirmed"

        created = api.post(
            f"/api/v1/diagnoses/{diagnosis['id']}/knowledge-candidates",
            headers={"X-Request-ID": "knowledge-from-diagnosis-1"},
        )
        assert created.status_code == 200
        payload = created.json()
        assert payload["created"] is True
        assert payload["knowledge"]["status"] == "candidate"
        assert payload["knowledge"]["source"] == f"diagnosis:{diagnosis['id']}"
        assert "customerName is null" in payload["knowledge"]["summary"]
        assert payload["knowledge"]["tags"] == ["diagnosis-derived", "human-confirmed"]
        assert len(payload["knowledge"]["title"]) <= 200

        repeated = api.post(f"/api/v1/diagnoses/{diagnosis['id']}/knowledge-candidates")
        assert repeated.status_code == 200
        assert repeated.json()["created"] is False
        assert repeated.json()["knowledge"]["id"] == payload["knowledge"]["id"]

        candidates = api.get("/api/v1/knowledge", params={"status": "candidate"}).json()
        assert [item["id"] for item in candidates] == [payload["knowledge"]["id"]]

    with sqlite3.connect(tmp_path / "diagnosis-knowledge.db") as connection:
        events = list(
            connection.execute(
                "SELECT action, correlation_id FROM audit_events WHERE target_id = ?",
                (f"diagnosis-{diagnosis['id']}",),
            )
        )
    assert events == [("knowledge.created_from_diagnosis", "knowledge-from-diagnosis-1")]
