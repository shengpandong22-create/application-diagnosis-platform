from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app_diagnosis.api.app import create_app
from app_diagnosis.bootstrap.settings import Settings


def test_report_api_and_minimal_ui_do_not_require_model(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{(tmp_path / 'phase0c.db').as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    settings = Settings(
        _env_file=None,
        env="test",
        database_url=url,
        knowledge_directory=str(Path("samples/knowledge").resolve()),
    )
    with TestClient(create_app(settings=settings)) as api:
        created = api.post(
            "/api/v1/diagnoses", json={"title": "HTTP 500", "symptom": "password=secret"}
        )
        diagnosis_id = created.json()["id"]
        report = api.get(f"/api/v1/diagnoses/{diagnosis_id}/report")
        assert report.status_code == 200
        assert report.json()["evidence"][0]["content"] == "password=[REDACTED]"
        markdown = api.get(f"/api/v1/diagnoses/{diagnosis_id}/report.md")
        assert markdown.status_code == 200 and "## Evidence" in markdown.text
        ui = api.get("/ui")
        assert ui.status_code == 200
        assert "启动 Run" in ui.text and "/report.md" in ui.text
