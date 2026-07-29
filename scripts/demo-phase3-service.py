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


class OfflineServiceDemoLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        visible_tools = {item.name for item in request.tools}
        if self.calls == 1:
            if not {"code__search", "code__read"}.issubset(visible_tools):
                raise AssertionError(f"service-scoped code tools are not visible: {visible_tools}")
            return LLMResponse(
                ChatMessage.assistant(
                    None,
                    tool_calls=(
                        ToolCall(
                            id="service-code-search-1",
                            name="code__search",
                            arguments_json='{"query":"createOrder","limit":5}',
                        ),
                    ),
                ),
                "offline-service-demo",
                FinishReason.TOOL_CALLS,
            )
        if self.calls == 2:
            payload = _latest_tool_payload(request)
            search_result = payload.get("tool_result", payload)
            path = next(
                item["path"]
                for item in search_result["matches"]
                if item["path"].endswith("OrderService.java")
            )
            return LLMResponse(
                ChatMessage.assistant(
                    None,
                    tool_calls=(
                        ToolCall(
                            id="service-code-read-1",
                            name="code__read",
                            arguments_json=json.dumps(
                                {"path": path, "start_line": 1, "end_line": 12},
                                separators=(",", ":"),
                            ),
                        ),
                    ),
                ),
                "offline-service-demo",
                FinishReason.TOOL_CALLS,
            )
        payload = _latest_tool_payload(request)
        evidence_id = payload["evidence_ids"][0]
        conclusion = {
            "symptom_summary": "服务目录绑定的订单服务出现 NullPointerException",
            "facts": [],
            "root_causes": [
                {
                    "statement": (
                        "OrderService.createOrder 对 customer 执行 trim，"
                        "当入参缺少 customer 时可能触发空指针"
                    ),
                    "status": "possible",
                    "evidence_ids": [evidence_id],
                }
            ],
            "recommendations": [
                "补充 customer 字段校验，并用真实失败请求复核运行时入参"
            ],
            "missing_information": [],
        }
        return LLMResponse(
            ChatMessage.assistant(json.dumps(conclusion, ensure_ascii=False)),
            "offline-service-demo",
            FinishReason.STOP,
        )


def _latest_tool_payload(request: LLMRequest) -> dict:
    for message in reversed(request.messages):
        content = message.content or ""
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and (
            "tool_result" in payload or "matches" in payload or "evidence_ids" in payload
        ):
            return payload
    raise ValueError("no tool payload found in model request")


def _create_demo_service_files(root: Path) -> tuple[Path, Path, Path]:
    code_root = root / "service" / "src"
    log_root = root / "service" / "logs"
    config_root = root / "service" / "config"
    code_root.mkdir(parents=True)
    log_root.mkdir(parents=True)
    config_root.mkdir(parents=True)
    (code_root / "OrderService.java").write_text(
        "\n".join(
            [
                "package dev.agentstudy.lab;",
                "",
                "class OrderService {",
                "  Order createOrder(OrderDraft draft) {",
                "    String customer = draft.customer();",
                "    return new Order(customer.trim());",
                "  }",
                "}",
                "",
                "record OrderDraft(String customer) {}",
                "record Order(String customer) {}",
            ]
        ),
        encoding="utf-8",
    )
    (log_root / "diagnosis-java-lab.log").write_text(
        "2026-07-30 09:30:00 ERROR HTTP 500 NullPointerException\n"
        "java.lang.NullPointerException: Cannot invoke trim() because customer is null\n"
        " at dev.agentstudy.lab.OrderService.createOrder(OrderService.java:6)\n",
        encoding="utf-8",
    )
    (config_root / "application.properties").write_text(
        "server.port=18080\nmanagement.endpoint.health.enabled=true\n",
        encoding="utf-8",
    )
    return code_root, log_root, config_root


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the Phase 3C service-scoped diagnosis demo offline"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "demo-output" / "phase3-service",
    )
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="app-diagnosis-phase3-service-") as temporary:
        root = Path(temporary)
        code_root, log_root, config_root = _create_demo_service_files(root)
        url = f"sqlite+aiosqlite:///{(root / 'demo.db').as_posix()}"
        alembic = Config(str(PROJECT_ROOT / "alembic.ini"))
        alembic.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
        alembic.set_main_option("sqlalchemy.url", url)
        command.upgrade(alembic, "head")
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
            llm_client=OfflineServiceDemoLLM(),
        )
        with TestClient(
            create_app(settings=settings, database=database, diagnosis_service=service)
        ) as api:
            created_service = api.post(
                "/api/v1/services",
                json={
                    "name": "phase3-service-demo",
                    "environment": "local-demo",
                    "description": "Phase 3C demo service with explicit tool scopes",
                    "code_workspace_path": str(code_root),
                    "log_directory": str(log_root),
                    "config_workspace_path": str(config_root),
                    "health_targets": ["app=http://localhost:18080/actuator/health"],
                    "tags": ["phase3", "service-context"],
                },
            )
            created_service.raise_for_status()
            service_payload = created_service.json()
            created_diagnosis = api.post(
                f"/api/v1/services/{service_payload['id']}/diagnoses",
                json={
                    "title": "服务目录驱动的订单故障诊断",
                    "symptom": "POST /orders 返回 500，日志显示 NullPointerException",
                    "submitted_log": (
                        "java.lang.NullPointerException\n"
                        " at dev.agentstudy.lab.OrderService.createOrder(OrderService.java:6)"
                    ),
                },
            )
            created_diagnosis.raise_for_status()
            diagnosis_id = created_diagnosis.json()["id"]
            run = api.post(f"/api/v1/diagnoses/{diagnosis_id}/runs")
            trace = api.get(f"/api/v1/diagnoses/{diagnosis_id}/trace")
            plan = api.get(f"/api/v1/diagnoses/{diagnosis_id}/plan")
            evidence = api.get(f"/api/v1/diagnoses/{diagnosis_id}/evidence")
            report = api.get(f"/api/v1/diagnoses/{diagnosis_id}/report.md")
            for response in (run, trace, plan, evidence, report):
                response.raise_for_status()

        args.output.mkdir(parents=True, exist_ok=True)
        report_path = args.output / "diagnosis-report.md"
        trace_path = args.output / "trace.json"
        summary_path = args.output / "demo-summary.json"
        report_path.write_text(report.text, encoding="utf-8")
        trace_path.write_text(
            json.dumps(trace.json(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        evidence_items = evidence.json()
        code_evidence = [item for item in evidence_items if item["type"] == "code_excerpt"]
        trace_runs = trace.json()["runs"]
        tool_events = [
            event
            for item in trace_runs
            for event in item["events"]
            if event["type"] == "tool_call"
        ]
        if not code_evidence:
            raise RuntimeError("Phase 3C demo expected code_excerpt evidence")
        summary = {
            "service_id": service_payload["id"],
            "service_name": service_payload["name"],
            "diagnosis_id": diagnosis_id,
            "strategy": trace_runs[0]["strategy"],
            "termination_reason": run.json()["termination_reason"],
            "allowed_tools": plan.json()["allowed_tools"],
            "tool_events": [
                {
                    "tool_name": event["tool_name"],
                    "status": event["status"],
                    "evidence_ids": event["evidence_ids"],
                }
                for event in tool_events
            ],
            "evidence_count": len(evidence_items),
            "code_evidence_count": len(code_evidence),
            "code_source_reference": code_evidence[0]["source_reference"],
            "external_model_called": False,
            "report": str(report_path.resolve()),
            "trace": str(trace_path.resolve()),
        }
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
