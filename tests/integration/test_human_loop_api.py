from collections.abc import Iterator
from contextlib import contextmanager
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


def response(*, missing: bool) -> LLMResponse:
    missing_information = '["Provide a stack trace"]' if missing else "[]"
    return LLMResponse(
        message=ChatMessage.assistant(
            '{"symptom_summary":"HTTP 500","facts":[],"root_causes":[],'
            '"recommendations":[],"missing_information":' + missing_information + "}"
        ),
        model="fake",
        finish_reason=FinishReason.STOP,
    )


@contextmanager
def client(tmp_path: Path, fake: FakeLLMClient) -> Iterator[TestClient]:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'human-loop.db').as_posix()}"
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
    service, _ = build_diagnosis_service(settings=settings, database=database, llm_client=fake)
    with TestClient(
        create_app(settings=settings, database=database, diagnosis_service=service)
    ) as value:
        yield value


def create_and_run(client: TestClient) -> str:
    created = client.post("/api/v1/diagnoses", json={"title": "Failure", "symptom": "HTTP 500"})
    diagnosis_id = created.json()["id"]
    executed = client.post(f"/api/v1/diagnoses/{diagnosis_id}/runs")
    assert executed.status_code == 200
    return diagnosis_id


def test_supplement_is_redacted_persisted_and_allows_new_run(tmp_path: Path) -> None:
    with client(tmp_path, FakeLLMClient([response(missing=True), response(missing=False)])) as api:
        diagnosis_id = create_and_run(api)
        supplement = api.post(
            f"/api/v1/diagnoses/{diagnosis_id}/supplements",
            json={"type": "log_excerpt", "content": "password=secret-value NullPointerException"},
        )
        assert supplement.status_code == 200
        assert supplement.json()["diagnosis"]["status"] == "investigating"
        assert "secret-value" not in supplement.json()["evidence"]["content"]
        evidence = api.get(f"/api/v1/diagnoses/{diagnosis_id}/evidence")
        assert evidence.status_code == 200
        assert any(item["type"] == "log_excerpt" for item in evidence.json())
        rerun = api.post(f"/api/v1/diagnoses/{diagnosis_id}/runs")
        assert rerun.status_code == 200
        runs = api.get(f"/api/v1/diagnoses/{diagnosis_id}/runs").json()
        assert len(runs) == 2


def test_confirmation_appends_record_without_overwriting_model_conclusion(tmp_path: Path) -> None:
    with client(tmp_path, FakeLLMClient([response(missing=False)])) as api:
        diagnosis_id = create_and_run(api)
        before = api.get(f"/api/v1/diagnoses/{diagnosis_id}").json()["conclusion"]
        confirmed = api.post(
            f"/api/v1/diagnoses/{diagnosis_id}/confirmation",
            json={"action": "confirm", "comment": "password=review-secret Looks correct"},
        )
        assert confirmed.status_code == 200
        payload = confirmed.json()
        assert payload["diagnosis"]["status"] == "confirmed"
        assert payload["diagnosis"]["conclusion"] == before
        assert "review-secret" not in payload["confirmation"]["comment"]
        repeated = api.post(
            f"/api/v1/diagnoses/{diagnosis_id}/confirmation",
            json={"action": "reject"},
        )
        assert repeated.status_code == 409


def test_continue_investigation_requires_explicit_new_run(tmp_path: Path) -> None:
    with client(tmp_path, FakeLLMClient([response(missing=False), response(missing=False)])) as api:
        diagnosis_id = create_and_run(api)
        continued = api.post(
            f"/api/v1/diagnoses/{diagnosis_id}/confirmation",
            json={"action": "continue_investigation", "comment": "Check another hypothesis"},
        )
        assert continued.status_code == 200
        assert continued.json()["diagnosis"]["status"] == "investigating"
        assert len(api.get(f"/api/v1/diagnoses/{diagnosis_id}/runs").json()) == 1
        assert api.post(f"/api/v1/diagnoses/{diagnosis_id}/runs").status_code == 200
        assert len(api.get(f"/api/v1/diagnoses/{diagnosis_id}/runs").json()) == 2
