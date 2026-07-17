import argparse
import json
import tempfile
from pathlib import Path
from time import perf_counter

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app_diagnosis.adapters.logs import LocalLogFileReader
from app_diagnosis.adapters.persistence import Database
from app_diagnosis.api.app import create_app
from app_diagnosis.bootstrap.container import build_diagnosis_service
from app_diagnosis.bootstrap.settings import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JAVA_LAB = PROJECT_ROOT.parent / "diagnosis-java-lab"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diagnose a bounded real Java log with the configured external model"
    )
    parser.add_argument("--java-lab", type=Path, default=DEFAULT_JAVA_LAB)
    parser.add_argument("--log", default="diagnosis-java-lab.log")
    parser.add_argument("--keyword", default="NullPointerException")
    parser.add_argument(
        "--output", type=Path, default=PROJECT_ROOT / "demo-output" / "phase1-real-model"
    )
    args = parser.parse_args()

    java_lab = args.java_lab.resolve(strict=True)
    excerpt = LocalLogFileReader(java_lab / "logs").read_latest(
        relative_path=args.log,
        keyword=args.keyword,
    )
    with tempfile.TemporaryDirectory(prefix="app-diagnosis-real-model-") as temporary:
        database_url = f"sqlite+aiosqlite:///{(Path(temporary) / 'demo.db').as_posix()}"
        config = Config(str(PROJECT_ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
        config.set_main_option("sqlalchemy.url", database_url)
        command.upgrade(config, "head")
        settings = Settings(
            database_url=database_url,
            knowledge_directory=str(PROJECT_ROOT / "samples" / "knowledge"),
            code_workspace_path=str(java_lab),
            code_workspace_name="diagnosis-java-lab",
            agent_max_rounds=6,
            agent_max_tool_calls=8,
            agent_total_timeout_seconds=120,
            llm_timeout_seconds=30,
        )
        if not settings.llm_model.strip() or not settings.llm_api_key.get_secret_value():
            raise RuntimeError("APP_LLM_MODEL and APP_LLM_API_KEY must be configured in .env")

        database = Database(database_url)
        service, _ = build_diagnosis_service(settings=settings, database=database)
        started = perf_counter()
        with TestClient(
            create_app(settings=settings, database=database, diagnosis_service=service)
        ) as api:
            created = api.post(
                "/api/v1/diagnoses",
                json={
                    "title": f"Java Lab real-log diagnosis: {args.keyword}",
                    "symptom": f"Java Lab HTTP 500 contains {args.keyword}",
                    "submitted_log": excerpt.content,
                },
            )
            created.raise_for_status()
            diagnosis_id = created.json()["id"]
            run_response = api.post(f"/api/v1/diagnoses/{diagnosis_id}/runs")
            run_response.raise_for_status()
            evidence_response = api.get(f"/api/v1/diagnoses/{diagnosis_id}/evidence")
            runs_response = api.get(f"/api/v1/diagnoses/{diagnosis_id}/runs")
            report_response = api.get(f"/api/v1/diagnoses/{diagnosis_id}/report.md")
            evidence_response.raise_for_status()
            runs_response.raise_for_status()
            report_response.raise_for_status()
        elapsed_ms = int((perf_counter() - started) * 1000)
        result = run_response.json()
        evidence = evidence_response.json()
        run = runs_response.json()[0]
        by_id = {item["id"]: item for item in evidence}
        cited_ids = {
            evidence_id
            for section in ("facts", "root_causes")
            for finding in (result.get("conclusion") or {}).get(section, [])
            for evidence_id in finding.get("evidence_ids", [])
        }
        cited_types = {by_id[item]["type"] for item in cited_ids if item in by_id}
        tools = [item for item in run["tool_runs"]]
        successful_tools = {item["tool_name"] for item in tools if item["status"] == "success"}
        failures: list[str] = []
        if result["termination_reason"] != "completed":
            failures.append(f"termination={result['termination_reason']}")
        if not {"code__search", "code__read"}.issubset(successful_tools):
            failures.append("model did not successfully search and read code")
        if not {"log_excerpt", "code_excerpt"}.issubset(cited_types):
            failures.append("conclusion did not cite both log and code evidence")

        args.output.mkdir(parents=True, exist_ok=True)
        report_path = args.output / "diagnosis-report.md"
        report_path.write_text(report_response.text, encoding="utf-8")
        summary = {
            "diagnosis_id": diagnosis_id,
            "termination_reason": result["termination_reason"],
            "run_error_code": run["error_code"],
            "model": run["model"],
            "round_count": run["round_count"],
            "tool_call_count": run["tool_call_count"],
            "input_tokens": run["input_tokens"],
            "output_tokens": run["output_tokens"],
            "elapsed_ms": elapsed_ms,
            "tool_trace": [
                {
                    "name": item["tool_name"],
                    "status": item["status"],
                    "duration_ms": item["duration_ms"],
                    "arguments": item["arguments"],
                    "error_code": item["error_code"],
                }
                for item in tools
            ],
            "cited_evidence_types": sorted(cited_types),
            "log_source_reference": excerpt.source_reference,
            "external_model_called": True,
            "report": str(report_path.resolve()),
            "acceptance_failures": failures,
        }
        (args.output / "demo-summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        if failures:
            raise RuntimeError("real-model acceptance failed: " + "; ".join(failures))


if __name__ == "__main__":
    main()
