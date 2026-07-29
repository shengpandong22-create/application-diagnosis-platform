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


@contextmanager
def migrated_client(tmp_path: Path) -> Iterator[TestClient]:
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
    service, _ = build_diagnosis_service(
        settings=settings,
        database=database,
        llm_client=FakeLLMClient([]),
    )
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
