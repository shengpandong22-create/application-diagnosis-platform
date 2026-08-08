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


class OfflineDiscoveryLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        conclusion = {
            "symptom_summary": "主动发现到应用异常日志",
            "facts": [],
            "root_causes": [
                {
                    "statement": "日志表明存在空对象访问，需要人工结合源码复核",
                    "status": "possible",
                    "evidence_ids": [],
                }
            ],
            "recommendations": ["检查首个业务栈帧中的空值来源"],
            "missing_information": [],
        }
        return LLMResponse(
            ChatMessage.assistant(json.dumps(conclusion, ensure_ascii=False)),
            "offline-discovery",
            FinishReason.STOP,
        )


def main() -> None:
    output = ROOT / "demo-output" / "phase4c"
    llm = OfflineDiscoveryLLM()
    with tempfile.TemporaryDirectory(prefix="phase4c-") as temporary:
        url = f"sqlite+aiosqlite:///{(Path(temporary) / 'phase4c.db').as_posix()}"
        config = Config(str(ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(ROOT / "migrations"))
        config.set_main_option("sqlalchemy.url", url)
        command.upgrade(config, "head")
        settings = Settings(
            _env_file=None,
            env="test",
            database_url=url,
            knowledge_directory=str(ROOT / "samples" / "knowledge"),
        )
        database = Database(url)
        diagnoses, _ = build_diagnosis_service(
            settings=settings, database=database, llm_client=llm
        )
        with TestClient(
            create_app(settings=settings, database=database, diagnosis_service=diagnoses)
        ) as api:
            service = api.post(
                "/api/v1/services",
                json={"name": "phase4c-demo", "environment": "local"},
            ).json()
            event = {
                "service_id": service["id"],
                "environment": "local",
                "occurred_at": datetime.now(UTC).isoformat(),
                "severity": "ERROR",
                "message": "NullPointerException password=demo-secret",
                "exception_type": "java.lang.NullPointerException",
                "source_event_id": "phase4c-demo-001",
                "stack_frames": [
                    {
                        "class_name": "dev.agentstudy.lab.OrderService",
                        "method_name": "submit",
                        "line_number": 42,
                    }
                ],
            }
            first = api.post("/api/v1/discovery/replay", json=[event]).json()[0]
            second = api.post("/api/v1/discovery/replay", json=[event]).json()[0]
            report = api.get(
                f"/api/v1/diagnoses/{first['diagnosis_id']}/report.md"
            ).text
        output.mkdir(parents=True, exist_ok=True)
        report_path = output / "diagnosis-report.md"
        report_path.write_text(report, encoding="utf-8")
        summary = {
            "incident_id": first["incident"]["id"],
            "diagnosis_id": first["diagnosis_id"],
            "first_triggered": first["triggered"],
            "replay_triggered": second["triggered"],
            "llm_calls": llm.calls,
            "redaction_verified": "demo-secret" not in report,
            "external_model_called": False,
            "report": str(report_path),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
