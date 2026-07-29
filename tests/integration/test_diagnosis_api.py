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
from app_diagnosis.ports.llm import (
    ChatMessage,
    FinishReason,
    LLMResponse,
    LLMUsage,
    ToolCall,
)


def response(*, content: str | None = None, tool_calls: tuple[ToolCall, ...] = ()) -> LLMResponse:
    return LLMResponse(
        message=ChatMessage.assistant(content, tool_calls=tool_calls),
        model="fake-model",
        finish_reason=FinishReason.TOOL_CALLS if tool_calls else FinishReason.STOP,
        usage=LLMUsage(input_tokens=12, output_tokens=6, total_tokens=18),
    )


def conclusion_json() -> str:
    return (
        '{"symptom_summary":"Checkout returned HTTP 500.","facts":[],"root_causes":['
        '{"statement":"A null value was dereferenced.","status":"possible",'
        '"evidence_ids":[]}],"recommendations":["Inspect the first application frame."],'
        '"missing_information":[]}'
    )


@contextmanager
def migrated_client(tmp_path: Path, fake: FakeLLMClient) -> Iterator[TestClient]:
    database_path = tmp_path / "api.db"
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
        llm_client=fake,
    )
    with TestClient(
        create_app(settings=settings, database=database, diagnosis_service=service)
    ) as client:
        yield client


def test_create_run_query_and_audit_tool_call(tmp_path: Path) -> None:
    fake = FakeLLMClient(
        [
            response(
                tool_calls=(
                    ToolCall(
                        id="call-knowledge",
                        name="knowledge__search",
                        arguments_json='{"query":"NullPointerException","limit":2}',
                    ),
                )
            ),
            response(content=conclusion_json()),
        ]
    )
    with migrated_client(tmp_path, fake) as client:
        created = client.post(
            "/api/v1/diagnoses",
            json={
                "title": "Checkout failure",
                "symptom": "Checkout API returned HTTP 500",
                "submitted_log": "java.lang.NullPointerException",
            },
        )
        assert created.status_code == 201
        diagnosis_id = created.json()["id"]

        executed = client.post(
            f"/api/v1/diagnoses/{diagnosis_id}/runs",
            headers={"X-Request-ID": "api-e2e-1"},
        )
        assert executed.status_code == 200
        assert executed.json()["termination_reason"] == "completed"

        diagnosis = client.get(f"/api/v1/diagnoses/{diagnosis_id}").json()
        assert diagnosis["status"] == "waiting_for_confirmation"
        assert diagnosis["conclusion"]["symptom_summary"] == "Checkout returned HTTP 500."

        runs = client.get(f"/api/v1/diagnoses/{diagnosis_id}/runs")
        assert runs.status_code == 200
        payload = runs.json()
        assert payload[0]["round_count"] == 2
        assert payload[0]["tool_call_count"] == 1
        assert payload[0]["tool_runs"][0]["tool_name"] == "knowledge__search"
        assert payload[0]["tool_runs"][0]["arguments"] == {
            "query": "NullPointerException",
            "limit": 2,
        }

        plan = client.get(f"/api/v1/diagnoses/{diagnosis_id}/plan")
        assert plan.status_code == 200
        plan_payload = plan.json()
        assert plan_payload["agent_run_id"] == payload[0]["id"]
        assert "knowledge__search" in plan_payload["allowed_tools"]
        assert plan_payload["steps"][0]["title"] == "整理用户事实与初始日志"

        report = client.get(f"/api/v1/diagnoses/{diagnosis_id}/report")
        assert report.status_code == 200
        assert report.json()["plans"][0]["id"] == plan_payload["id"]

        trace = client.get(f"/api/v1/diagnoses/{diagnosis_id}/trace")
        assert trace.status_code == 200
        assert trace.json()["runs"][0]["plan"]["id"] == plan_payload["id"]

        repeated = client.post(f"/api/v1/diagnoses/{diagnosis_id}/runs")
        assert repeated.status_code == 409


def test_cancel_created_diagnosis_and_missing_case(tmp_path: Path) -> None:
    with migrated_client(tmp_path, FakeLLMClient([])) as client:
        created = client.post(
            "/api/v1/diagnoses",
            json={"title": "Cancel me", "symptom": "No longer relevant"},
        )
        diagnosis_id = created.json()["id"]
        cancelled = client.post(f"/api/v1/diagnoses/{diagnosis_id}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"
        missing = client.get("/api/v1/diagnoses/00000000-0000-0000-0000-000000000000")
        assert missing.status_code == 404


def test_plan_endpoint_returns_404_before_first_run(tmp_path: Path) -> None:
    with migrated_client(tmp_path, FakeLLMClient([])) as client:
        created = client.post(
            "/api/v1/diagnoses",
            json={"title": "No plan yet", "symptom": "Created only"},
        )
        diagnosis_id = created.json()["id"]
        plan = client.get(f"/api/v1/diagnoses/{diagnosis_id}/plan")
        assert plan.status_code == 404
        assert plan.json()["error"]["code"] == "diagnosis_plan_not_found"
