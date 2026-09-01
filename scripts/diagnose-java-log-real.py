import argparse
import json
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any

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
DEFAULT_CASES = PROJECT_ROOT / "evals" / "cases" / "phase1-java-lab-cases.json"


def load_case(path: Path, case_id: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases") or payload.get("scenarios")
    if not isinstance(cases, list):
        raise ValueError("case file must contain a cases array")
    for item in cases:
        if isinstance(item, dict) and item.get("id") == case_id:
            return item
    raise ValueError(f"unknown evaluation case: {case_id}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diagnose a bounded real Java log with the configured external model"
    )
    parser.add_argument("--java-lab", type=Path, default=DEFAULT_JAVA_LAB)
    parser.add_argument("--log", default="diagnosis-java-lab.log")
    parser.add_argument("--keyword")
    parser.add_argument("--case")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument(
        "--output", type=Path, default=PROJECT_ROOT / "demo-output" / "phase1-real-model"
    )
    parser.add_argument("--llm-timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()
    if args.llm_timeout_seconds <= 0:
        raise ValueError("--llm-timeout-seconds must be positive")

    case = load_case(args.cases, args.case) if args.case else None
    keyword = args.keyword or (case or {}).get("keyword")
    if not isinstance(keyword, str) or not keyword.strip():
        raise ValueError("provide --keyword or --case")
    expected_paths = tuple((case or {}).get("expected_code_paths", ()))
    expected_terms = tuple((case or {}).get("allowed_root_cause_keywords", ()))
    expected_tools = set(
        (case or {}).get("expected_tools")
        or (case or {}).get("expected_tool_names", ())
    )
    expected_evidence_types = set(
        (case or {}).get("expected_evidence_types")
        or (case or {}).get("required_evidence_types", ())
    )

    java_lab = args.java_lab.resolve(strict=True)
    excerpt = LocalLogFileReader(java_lab / "logs").read_latest(
        relative_path=args.log,
        keyword=keyword,
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
            config_workspace_path=str(java_lab),
            agent_max_rounds=6,
            agent_max_tool_calls=8,
            agent_total_timeout_seconds=120,
            llm_timeout_seconds=args.llm_timeout_seconds,
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
                    "title": f"Java Lab real-log diagnosis: {case['title'] if case else keyword}",
                    "symptom": (case or {}).get(
                        "symptom", f"Java Lab failure contains {keyword}"
                    ),
                    "submitted_log": excerpt.content,
                },
            )
            created.raise_for_status()
            diagnosis_id = created.json()["id"]
            run_response = api.post(f"/api/v1/diagnoses/{diagnosis_id}/runs")
            run_response.raise_for_status()
            evidence_response = api.get(f"/api/v1/diagnoses/{diagnosis_id}/evidence")
            runs_response = api.get(f"/api/v1/diagnoses/{diagnosis_id}/runs")
            plan_response = api.get(f"/api/v1/diagnoses/{diagnosis_id}/plan")
            report_response = api.get(f"/api/v1/diagnoses/{diagnosis_id}/report.md")
            evidence_response.raise_for_status()
            runs_response.raise_for_status()
            plan_response.raise_for_status()
            report_response.raise_for_status()
        elapsed_ms = int((perf_counter() - started) * 1000)
        result = run_response.json()
        evidence = evidence_response.json()
        run = runs_response.json()[0]
        plan = plan_response.json()
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
        if plan["agent_run_id"] != run["id"]:
            failures.append("diagnosis plan is not linked to the agent run")
        if "## 诊断计划" not in report_response.text:
            failures.append("markdown report does not include diagnosis plan")
        required_tools = expected_tools or {"code__search", "code__read"}
        if not required_tools.issubset(successful_tools):
            failures.append(
                "missing expected successful tools: "
                + ", ".join(sorted(required_tools - successful_tools))
            )
        required_evidence = expected_evidence_types or {"log_excerpt", "code_excerpt"}
        if not required_evidence.issubset(cited_types):
            failures.append(
                "missing expected cited evidence: "
                + ", ".join(sorted(required_evidence - cited_types))
            )
        code_references = [
            item["source_reference"] or "" for item in evidence if item["type"] == "code_excerpt"
        ]
        evidence_references = [item["source_reference"] or "" for item in evidence]
        if expected_paths and not any(
            reference.endswith(path) or f"{path}:" in reference
            for reference in evidence_references
            for path in expected_paths
        ):
            failures.append("expected source file was not captured as evidence")
        root_cause_text = " ".join(
            item["statement"] for item in (result.get("conclusion") or {}).get("root_causes", [])
        ).casefold()
        if expected_terms and not any(
            term.casefold() in root_cause_text for term in expected_terms
        ):
            failures.append("root cause does not match case vocabulary")

        output = args.output / (case["id"] if case else keyword.casefold().replace(" ", "-"))
        output.mkdir(parents=True, exist_ok=True)
        report_path = output / "diagnosis-report.md"
        report_path.write_text(report_response.text, encoding="utf-8")
        summary = {
            "diagnosis_id": diagnosis_id,
            "case_id": case["id"] if case else None,
            "keyword": keyword,
            "termination_reason": result["termination_reason"],
            "run_error_code": run["error_code"],
            "model": run["model"],
            "round_count": run["round_count"],
            "tool_call_count": run["tool_call_count"],
            "plan_id": plan["id"],
            "plan_steps": [item["title"] for item in plan["steps"]],
            "plan_allowed_tools": plan["allowed_tools"],
            "input_tokens": run["input_tokens"],
            "output_tokens": run["output_tokens"],
            "elapsed_ms": elapsed_ms,
            "llm_timeout_seconds": args.llm_timeout_seconds,
            "conclusion": result.get("conclusion"),
            "evidence": [
                {"id": item["id"], "type": item["type"]} for item in evidence
            ],
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
            "code_evidence_references": code_references,
            "evidence_references": evidence_references,
            "expected_code_paths": expected_paths,
            "expected_root_cause_keywords": expected_terms,
            "expected_tools": sorted(required_tools),
            "expected_evidence_types": sorted(required_evidence),
            "log_source_reference": excerpt.source_reference,
            "external_model_called": True,
            "report": str(report_path.resolve()),
            "acceptance_failures": failures,
        }
        (output / "demo-summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        if failures:
            raise RuntimeError("real-model acceptance failed: " + "; ".join(failures))


if __name__ == "__main__":
    main()
