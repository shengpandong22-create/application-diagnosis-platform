import argparse
import json
import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app_diagnosis.adapters.logs import LocalLogFileReader
from app_diagnosis.adapters.persistence import Database
from app_diagnosis.api.app import create_app
from app_diagnosis.bootstrap.container import build_diagnosis_service
from app_diagnosis.bootstrap.settings import Settings
from app_diagnosis.ports.llm import ChatMessage, FinishReason, LLMRequest, LLMResponse, ToolCall

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JAVA_LAB = PROJECT_ROOT.parent / "diagnosis-java-lab"


class OfflineCodeDemoLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        if self.calls == 1:
            call = ToolCall(
                id="code-search-1",
                name="code__search",
                arguments_json='{"query":"createOrder","limit":5}',
            )
            return LLMResponse(
                ChatMessage.assistant(None, tool_calls=(call,)),
                "offline-code-demo",
                FinishReason.TOOL_CALLS,
            )
        if self.calls == 2:
            payload = json.loads(request.messages[-1].content or "{}")
            search_result = payload.get("tool_result", payload)
            path = next(
                item["path"]
                for item in search_result["matches"]
                if item["path"].endswith("/OrderService.java")
            )
            call = ToolCall(
                id="code-read-1",
                name="code__read",
                arguments_json=json.dumps(
                    {"path": path, "start_line": 1, "end_line": 30},
                    separators=(",", ":"),
                ),
            )
            return LLMResponse(
                ChatMessage.assistant(None, tool_calls=(call,)),
                "offline-code-demo",
                FinishReason.TOOL_CALLS,
            )
        payload = json.loads(request.messages[-1].content or "{}")
        conclusion = {
            "symptom_summary": "Order endpoint returns HTTP 500 with NullPointerException",
            "facts": [],
            "root_causes": [
                {
                    "statement": (
                        "OrderService.createOrder dereferences customer without a null check; "
                        "the runtime value still requires verification"
                    ),
                    "status": "possible",
                    "evidence_ids": [payload["evidence_ids"][0]],
                }
            ],
            "recommendations": [
                "Debug createOrder and verify that OrderDraft.customer is null at runtime"
            ],
            "missing_information": [],
        }
        return LLMResponse(
            ChatMessage.assistant(json.dumps(conclusion)),
            "offline-code-demo",
            FinishReason.STOP,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Phase 1 real-log-to-code demo offline")
    parser.add_argument("--java-lab", type=Path, default=DEFAULT_JAVA_LAB)
    parser.add_argument("--log", default="diagnosis-java-lab.log")
    parser.add_argument("--keyword", default="NullPointerException")
    parser.add_argument(
        "--output", type=Path, default=PROJECT_ROOT / "demo-output" / "phase1-log-code"
    )
    args = parser.parse_args()
    java_lab = args.java_lab.resolve(strict=True)
    log_root = (java_lab / "logs").resolve(strict=True)
    log_excerpt = LocalLogFileReader(log_root).read_latest(
        relative_path=args.log,
        keyword=args.keyword,
    )
    with tempfile.TemporaryDirectory(prefix="app-diagnosis-phase1-") as temporary:
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
            code_workspace_path=str(java_lab),
            code_workspace_name="diagnosis-java-lab",
        )
        database = Database(url)
        service, _ = build_diagnosis_service(
            settings=settings,
            database=database,
            llm_client=OfflineCodeDemoLLM(),
        )
        with TestClient(
            create_app(settings=settings, database=database, diagnosis_service=service)
        ) as api:
            created = api.post(
                "/api/v1/diagnoses",
                json={
                    "title": "Java Lab order endpoint HTTP 500",
                    "symptom": f"Java Lab failure contains {args.keyword}",
                    "submitted_log": log_excerpt.content,
                },
            )
            created.raise_for_status()
            diagnosis_id = created.json()["id"]
            run = api.post(f"/api/v1/diagnoses/{diagnosis_id}/runs")
            run.raise_for_status()
            evidence = api.get(f"/api/v1/diagnoses/{diagnosis_id}/evidence")
            runs = api.get(f"/api/v1/diagnoses/{diagnosis_id}/runs")
            report = api.get(f"/api/v1/diagnoses/{diagnosis_id}/report.md")
            evidence.raise_for_status()
            runs.raise_for_status()
            report.raise_for_status()
        code_evidence = [item for item in evidence.json() if item["type"] == "code_excerpt"]
        log_evidence = [item for item in evidence.json() if item["type"] == "log_excerpt"]
        if not code_evidence:
            raise RuntimeError(
                "code evidence was not created; "
                f"run={run.json()}, runs={runs.json()}, "
                f"evidence_types={[item['type'] for item in evidence.json()]}"
            )
        if not log_evidence:
            raise RuntimeError("real log evidence was not created")
        args.output.mkdir(parents=True, exist_ok=True)
        report_path = args.output / "diagnosis-report.md"
        report_path.write_text(report.text, encoding="utf-8")
        summary = {
            "diagnosis_id": diagnosis_id,
            "termination_reason": run.json()["termination_reason"],
            "code_evidence_count": len(code_evidence),
            "log_evidence_count": len(log_evidence),
            "log_source_reference": log_excerpt.source_reference,
            "log_redaction_status": log_evidence[0]["redaction_status"],
            "code_source_reference": code_evidence[0]["source_reference"],
            "workspace": str(java_lab),
            "external_model_called": False,
            "report": str(report_path.resolve()),
        }
        (args.output / "demo-summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
