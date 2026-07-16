import argparse
import json
import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app_diagnosis.adapters.persistence import Database
from app_diagnosis.api.app import create_app
from app_diagnosis.bootstrap.container import build_diagnosis_service
from app_diagnosis.bootstrap.settings import Settings
from app_diagnosis.ports.llm import ChatMessage, FinishReason, LLMRequest, LLMResponse, ToolCall

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class OfflineDemoLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        if self.calls == 1:
            call = ToolCall(
                id="demo-knowledge-1",
                name="knowledge__search",
                arguments_json='{"query":"NullPointerException HTTP 500","limit":3}',
            )
            return LLMResponse(
                ChatMessage.assistant(None, tool_calls=(call,)),
                "offline-demo",
                FinishReason.TOOL_CALLS,
            )
        payload = json.loads(request.messages[-1].content or "{}")
        conclusion = {
            "symptom_summary": "订单接口因 NullPointerException 返回 HTTP 500",
            "facts": [],
            "root_causes": [
                {
                    "statement": "空对象解引用是候选根因",
                    "status": "possible",
                    "evidence_ids": [payload["evidence_ids"][0]],
                }
            ],
            "recommendations": ["检查第一个业务代码栈帧并验证对象初始化路径"],
            "missing_information": [],
        }
        return LLMResponse(
            ChatMessage.assistant(json.dumps(conclusion, ensure_ascii=False)),
            "offline-demo",
            FinishReason.STOP,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the complete Phase 0 demo offline")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "demo-output")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="app-diagnosis-demo-") as temporary:
        url = f"sqlite+aiosqlite:///{(Path(temporary) / 'demo.db').as_posix()}"
        config = Config(str(PROJECT_ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
        config.set_main_option("sqlalchemy.url", url)
        command.upgrade(config, "head")
        settings = Settings(
            _env_file=None,
            env="test",
            database_url=url,
            knowledge_directory=str(PROJECT_ROOT / "samples" / "knowledge"),
        )
        database = Database(url)
        service, _ = build_diagnosis_service(
            settings=settings,
            database=database,
            llm_client=OfflineDemoLLM(),
        )
        with TestClient(
            create_app(settings=settings, database=database, diagnosis_service=service)
        ) as api:
            created = api.post(
                "/api/v1/diagnoses",
                json={
                    "title": "订单接口 HTTP 500",
                    "symptom": "POST /orders 返回 500，api_key=demo-secret",
                    "submitted_log": "java.lang.NullPointerException at OrderService.create",
                },
            )
            created.raise_for_status()
            diagnosis_id = created.json()["id"]
            run = api.post(f"/api/v1/diagnoses/{diagnosis_id}/runs")
            run.raise_for_status()
            confirmation = api.post(
                f"/api/v1/diagnoses/{diagnosis_id}/confirmation",
                json={"action": "confirm", "comment": "已复核候选根因"},
            )
            confirmation.raise_for_status()
            evidence = api.get(f"/api/v1/diagnoses/{diagnosis_id}/evidence")
            report = api.get(f"/api/v1/diagnoses/{diagnosis_id}/report.md")
            evidence.raise_for_status()
            report.raise_for_status()
        args.output.mkdir(parents=True, exist_ok=True)
        report_path = args.output / "diagnosis-report.md"
        report_path.write_text(report.text, encoding="utf-8")
        summary = {
            "diagnosis_id": diagnosis_id,
            "termination_reason": run.json()["termination_reason"],
            "evidence_count": len(evidence.json()),
            "redaction_verified": "demo-secret" not in repr(evidence.json()),
            "human_action": confirmation.json()["confirmation"]["action"],
            "external_model_called": False,
            "report": str(report_path.resolve()),
        }
        (args.output / "demo-summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
