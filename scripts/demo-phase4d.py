import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app_diagnosis.adapters.persistence import Database
from app_diagnosis.api.app import create_app
from app_diagnosis.bootstrap.container import build_diagnosis_service
from app_diagnosis.bootstrap.settings import Settings
from app_diagnosis.ports.llm import ChatMessage, FinishReason, LLMRequest, LLMResponse

ROOT = Path(__file__).resolve().parents[1]


class OfflineLLM:
    async def complete(self, request: LLMRequest) -> LLMResponse:
        conclusion = {
            "symptom_summary": "主动发现异常",
            "facts": [],
            "root_causes": [{
                "statement": "需要人工复核的候选根因", "status": "possible",
                "evidence_ids": [],
            }],
            "recommendations": ["复核业务栈帧"], "missing_information": [],
        }
        return LLMResponse(
            ChatMessage.assistant(json.dumps(conclusion, ensure_ascii=False)),
            "offline-phase4d", FinishReason.STOP,
        )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="phase4d-") as temporary:
        url = f"sqlite+aiosqlite:///{(Path(temporary) / 'demo.db').as_posix()}"
        config = Config(str(ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(ROOT / "migrations"))
        config.set_main_option("sqlalchemy.url", url)
        command.upgrade(config, "head")
        settings = Settings(
            _env_file=None, env="test", database_url=url,
            knowledge_directory=str(ROOT / "samples" / "knowledge"),
        )
        database = Database(url)
        diagnosis_service, _ = build_diagnosis_service(
            settings=settings, database=database, llm_client=OfflineLLM()
        )
        with TestClient(create_app(
            settings=settings, database=database, diagnosis_service=diagnosis_service
        )) as api:
            service = api.post(
                "/api/v1/services", json={"name": "phase4d-demo", "environment": "local"}
            ).json()
            event = {
                "service_id": service["id"], "environment": "local",
                "occurred_at": datetime.now(UTC).isoformat(), "severity": "ERROR",
                "message": "NullPointerException password=demo-secret",
                "exception_type": "java.lang.NullPointerException",
                "source_event_id": "phase4d-001", "stack_frames": [],
            }
            discovered = api.post("/api/v1/discovery/replay", json=[event]).json()[0]
            api.post(
                f"/api/v1/diagnoses/{discovered['diagnosis_id']}/confirmation",
                json={"action": "reject", "comment": "candidate needs correction"},
            ).raise_for_status()
            candidates = api.get("/api/v1/evaluation-candidates").json()
            day = datetime.now(UTC).date().isoformat()
            summary = api.get(
                f"/api/v1/services/{service['id']}/daily-summary?day={day}"
            ).json()
        print(json.dumps({
            "incident_id": discovered["incident"]["id"],
            "evaluation_candidate_status": candidates[0]["status"],
            "daily_incident_count": summary["incident_count"],
            "daily_rejected_count": summary["rejected"],
            "external_model_called": False,
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
