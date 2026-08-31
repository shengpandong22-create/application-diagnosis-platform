from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
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


def conclusion_without_citations() -> str:
    return (
        '{"symptom_summary":"Service scoped source was inspected.","facts":[],"root_causes":['
        '{"statement":"Source evidence was read from the registered service workspace.",'
        '"status":"possible","evidence_ids":[]}],'
        '"recommendations":["Ask a human to verify the final runtime value."],'
        '"missing_information":[]}'
    )


@contextmanager
def migrated_client(
    tmp_path: Path,
    fake: FakeLLMClient | None = None,
    *,
    clock: Callable[[], datetime] | None = None,
) -> Iterator[TestClient]:
    database_path = tmp_path / "services.db"
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
    build_kwargs = {
        "settings": settings,
        "database": database,
        "llm_client": fake or FakeLLMClient([]),
    }
    if clock is not None:
        build_kwargs["clock"] = clock
    service, _ = build_diagnosis_service(**build_kwargs)
    with TestClient(
        create_app(settings=settings, database=database, diagnosis_service=service)
    ) as client:
        yield client


def test_create_list_get_and_create_diagnosis_for_service(tmp_path: Path) -> None:
    with migrated_client(tmp_path) as client:
        created = client.post(
            "/api/v1/services",
            json={
                "name": "diagnosis-java-lab",
                "environment": "local",
                "description": "Local Java failure lab",
                "code_workspace_path": r"D:\AgentStudy\diagnosis-java-lab",
                "log_directory": r"D:\AgentStudy\diagnosis-java-lab\logs",
                "health_targets": ["http://localhost:18080/actuator/health"],
                "tags": ["java", "lab"],
            },
        )
        assert created.status_code == 201
        service = created.json()
        assert service["name"] == "diagnosis-java-lab"

        listed = client.get("/api/v1/services")
        assert listed.status_code == 200
        assert listed.json()[0]["id"] == service["id"]

        fetched = client.get(f"/api/v1/services/{service['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["environment"] == "local"

        diagnosis = client.post(
            f"/api/v1/services/{service['id']}/diagnoses",
            json={
                "title": "Service scoped NPE",
                "symptom": "NullPointerException",
            },
        )
        assert diagnosis.status_code == 201
        diagnosis_payload = diagnosis.json()
        assert diagnosis_payload["service_id"] == service["id"]

        report = client.get(f"/api/v1/diagnoses/{diagnosis_payload['id']}/report")
        assert report.status_code == 200
        assert report.json()["service"]["name"] == "diagnosis-java-lab"


def test_plain_diagnosis_still_has_no_service_id(tmp_path: Path) -> None:
    with migrated_client(tmp_path) as client:
        created = client.post(
            "/api/v1/diagnoses",
            json={"title": "Plain case", "symptom": "No service catalog"},
        )
        assert created.status_code == 201
        assert created.json()["service_id"] is None


def test_duplicate_service_name_environment_conflicts(tmp_path: Path) -> None:
    with migrated_client(tmp_path) as client:
        payload = {"name": "duplicate", "environment": "local"}
        assert client.post("/api/v1/services", json=payload).status_code == 201
        repeated = client.post("/api/v1/services", json=payload)
        assert repeated.status_code == 409
        assert repeated.json()["error"]["code"] == "service_profile_conflict"


def test_service_scoped_code_workspace_feeds_agent_tools(tmp_path: Path) -> None:
    code_root = tmp_path / "java-lab"
    code_root.mkdir()
    (code_root / "OrderService.java").write_text(
        "class OrderService {\n  String create() { return customer.trim(); }\n}\n",
        encoding="utf-8",
    )
    fake = FakeLLMClient(
        [
            response(
                tool_calls=(
                    ToolCall(
                        id="call-code-read",
                        name="code__read",
                        arguments_json=('{"path":"OrderService.java","start_line":1,"end_line":3}'),
                    ),
                )
            ),
            response(content=conclusion_without_citations()),
            response(content=conclusion_without_citations()),
            response(content=conclusion_without_citations()),
        ]
    )

    with migrated_client(tmp_path, fake) as client:
        service = client.post(
            "/api/v1/services",
            json={
                "name": "service-scoped-java-lab",
                "environment": "local",
                "code_workspace_path": str(code_root),
            },
        ).json()
        diagnosis = client.post(
            f"/api/v1/services/{service['id']}/diagnoses",
            json={"title": "Service scoped code", "symptom": "NullPointerException"},
        ).json()

        executed = client.post(f"/api/v1/diagnoses/{diagnosis['id']}/runs")
        assert executed.status_code == 200

        runs = client.get(f"/api/v1/diagnoses/{diagnosis['id']}/runs").json()
        tool_run = runs[0]["tool_runs"][0]
        assert tool_run["tool_name"] == "code__read"
        assert tool_run["status"] == "success"

        evidence = client.get(f"/api/v1/diagnoses/{diagnosis['id']}/evidence").json()
        code_evidence = [item for item in evidence if item["type"] == "code_excerpt"]
        assert code_evidence
        assert code_evidence[0]["metadata"]["workspace"] == "service-scoped-java-lab"


def test_service_diagnosis_history_and_summary(tmp_path: Path) -> None:
    with migrated_client(tmp_path) as client:
        service = client.post(
            "/api/v1/services",
            json={"name": "history-service", "environment": "test"},
        ).json()
        first = client.post(
            f"/api/v1/services/{service['id']}/diagnoses",
            json={"title": "First failure", "symptom": "HTTP 500"},
        ).json()
        second = client.post(
            f"/api/v1/services/{service['id']}/diagnoses",
            json={"title": "Second failure", "symptom": "Connection refused"},
        ).json()

        history = client.get(f"/api/v1/services/{service['id']}/diagnoses")
        assert history.status_code == 200
        assert [item["id"] for item in history.json()] == [second["id"], first["id"]]

        summary = client.get(f"/api/v1/services/{service['id']}/summary")
        assert summary.status_code == 200
        payload = summary.json()
        assert payload["service"]["id"] == service["id"]
        assert payload["total_diagnoses"] == 2
        assert payload["status_counts"] == {"created": 2}
        assert payload["latest_diagnosis"]["id"] == second["id"]


def test_empty_service_summary_and_unknown_service(tmp_path: Path) -> None:
    with migrated_client(tmp_path) as client:
        service = client.post(
            "/api/v1/services",
            json={"name": "empty-service", "environment": "test"},
        ).json()

        summary = client.get(f"/api/v1/services/{service['id']}/summary")
        assert summary.status_code == 200
        assert summary.json()["total_diagnoses"] == 0
        assert summary.json()["status_counts"] == {}
        assert summary.json()["latest_diagnosis"] is None

        missing = "00000000-0000-0000-0000-000000000099"
        assert client.get(f"/api/v1/services/{missing}/diagnoses").status_code == 404
        assert client.get(f"/api/v1/services/{missing}/summary").status_code == 404
