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
from app_diagnosis.ports.llm import ChatMessage, FinishReason, LLMResponse


def conclusion() -> LLMResponse:
    return LLMResponse(
        message=ChatMessage.assistant(
            '{"symptom_summary":"HTTP 500","facts":[],"root_causes":[],'
            '"recommendations":[],"missing_information":[]}'
        ),
        model="fake",
        finish_reason=FinishReason.STOP,
    )


def test_audit_records_actions_without_sensitive_payloads(tmp_path: Path) -> None:
    database_path = tmp_path / "audit-events.db"
    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    settings = Settings(
        _env_file=None,
        env="test",
        database_url=database_url,
        knowledge_directory=str(Path("samples/knowledge").resolve()),
    )
    database = Database(database_url)
    service, _ = build_diagnosis_service(
        settings=settings,
        database=database,
        llm_client=FakeLLMClient([conclusion()]),
    )
    secret = "never-store-this-secret"
    with TestClient(
        create_app(settings=settings, database=database, diagnosis_service=service)
    ) as api:
        created = api.post(
            "/api/v1/diagnoses",
            json={"title": "Failure", "symptom": f"HTTP 500 password={secret}"},
        )
        diagnosis_id = created.json()["id"]
        api.post(
            f"/api/v1/diagnoses/{diagnosis_id}/runs",
            headers={"X-Request-ID": "audit-run-1"},
        )
        api.post(
            f"/api/v1/diagnoses/{diagnosis_id}/confirmation",
            json={"action": "confirm", "comment": f"password={secret}"},
        )
        knowledge = api.post(
            "/api/v1/knowledge",
            json={
                "id": "audit-knowledge",
                "title": "Candidate",
                "summary": f"password={secret}",
            },
        )
        api.patch(
            f"/api/v1/knowledge/{knowledge.json()['id']}/status",
            json={"status": "confirmed"},
            headers={"X-Request-ID": "audit-knowledge-review-1"},
        )

    with sqlite3.connect(database_path) as connection:
        rows = list(
            connection.execute(
                "SELECT action, summary, correlation_id FROM audit_events ORDER BY created_at"
            )
        )
    actions = {row[0] for row in rows}
    assert {
        "evidence.created",
        "diagnosis.run_started",
        "diagnosis.confirmed",
        "knowledge.created",
        "knowledge.status_changed",
    } <= actions
    serialized = repr(rows)
    assert secret not in serialized
    assert "audit-run-1" in serialized
    assert "audit-knowledge-review-1" in serialized
