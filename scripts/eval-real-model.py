import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from app_diagnosis.evaluation.scenarios import EvaluationScenarioDataset

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def validate_timeout(value: float) -> float:
    if value <= 0:
        raise ValueError("--llm-timeout-seconds must be positive")
    return value


def select_scenarios(
    dataset: EvaluationScenarioDataset, case_ids: set[str], limit: int
) -> list[Any]:
    selected = [item for item in dataset.scenarios if not case_ids or item.id in case_ids]
    unknown = case_ids - {item.id for item in selected}
    if unknown:
        raise ValueError(f"unknown cases: {', '.join(sorted(unknown))}")
    return selected[:limit]


def build_scored_case(scenario: Any, summary: dict[str, Any]) -> dict[str, Any]:
    observation = {
        "termination_reason": summary.get("termination_reason", "runner_error"),
        "tool_statuses": [item["status"] for item in summary.get("tool_trace", [])],
        "tool_names": [item["name"] for item in summary.get("tool_trace", [])],
        "evidence": summary.get("evidence", []),
        "conclusion": summary.get("conclusion"),
        "observed_category": None,
        "confidence": None,
        "latency_ms": summary.get("elapsed_ms", 0),
        "prompt_tokens": summary.get("input_tokens", 0),
        "completion_tokens": summary.get("output_tokens", 0),
        "estimated_cost_usd": 0.0,
    }
    return {
        "id": scenario.id,
        "title": scenario.title,
        "source": scenario.source,
        "versions": {
            "dataset_version": "java-lab-real-v1",
            "model_id": summary.get("model", "unknown"),
            "prompt_version": "real-v1",
            "strategy_version": "phase3-router-v1",
            "tool_schema_version": "phase4-v1",
            "citation_policy_version": "phase0b-v1",
            "code_revision": "d3-real-model-baseline",
        },
        "expected_termination_reason": "completed",
        # DiagnosisConclusion does not currently emit a category. Keep category
        # ground truth in the Scenario, but do not score an unobserved field.
        "expected_category": None,
        "expected_information_sufficient": True,
        "expected_tool_names": scenario.expected_tool_names,
        "required_evidence_types": scenario.required_evidence_types,
        "required_evidence_ids": [],
        "allowed_root_cause_keywords": scenario.allowed_root_cause_keywords,
        "forbidden_root_cause_keywords": scenario.forbidden_root_cause_keywords,
        "observation": observation,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a bounded real-model evaluation batch")
    parser.add_argument(
        "--definitions",
        type=Path,
        default=PROJECT_ROOT / "evals/cases/real-model-v1-definitions.json",
    )
    parser.add_argument("--java-lab", type=Path, default=PROJECT_ROOT.parent / "diagnosis-java-lab")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "evals/results/real-model-v1")
    parser.add_argument("--cases", help="comma-separated scenario ids")
    parser.add_argument("--limit", type=int, default=4)
    parser.add_argument("--llm-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument(
        "--rebuild-only",
        action="store_true",
        help="Rebuild aggregate files from existing summaries without running the model",
    )
    args = parser.parse_args()
    if not 1 <= args.limit <= 12:
        raise ValueError("--limit must be between 1 and 12")
    validate_timeout(args.llm_timeout_seconds)

    dataset = EvaluationScenarioDataset.model_validate_json(
        args.definitions.read_text(encoding="utf-8")
    )
    case_ids = {item.strip() for item in (args.cases or "").split(",") if item.strip()}
    selected = select_scenarios(dataset, case_ids, args.limit)
    runs_dir = args.output / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    scored_cases: list[dict[str, Any]] = []

    for scenario in selected:
        summary_path = runs_dir / scenario.id / "demo-summary.json"
        if args.rebuild_only and not summary_path.exists():
            records.append({"case_id": scenario.id, "status": "summary_missing"})
            continue
        if args.no_resume or not summary_path.exists():
            command = [
                sys.executable,
                str(PROJECT_ROOT / "scripts/diagnose-java-log-real.py"),
                "--java-lab",
                str(args.java_lab),
                "--case",
                scenario.id,
                "--cases",
                str(args.definitions),
                "--output",
                str(runs_dir),
                "--llm-timeout-seconds",
                str(args.llm_timeout_seconds),
            ]
            completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
            if not summary_path.exists():
                records.append(
                    {
                        "case_id": scenario.id,
                        "status": "runner_error",
                        "process_return_code": completed.returncode,
                    }
                )
                continue
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        records.append(
            {
                "case_id": scenario.id,
                "status": summary.get("termination_reason", "unknown"),
                "summary": summary,
            }
        )
        scored_cases.append(build_scored_case(scenario, summary))

    (args.output / "observations.json").write_text(
        json.dumps(
            {"dataset_version": dataset.dataset_version, "runs": records},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (args.output / "scored-cases.json").write_text(
        json.dumps(
            {"dataset_version": dataset.dataset_version, "cases": scored_cases},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "selected": len(selected),
                "completed": len(scored_cases),
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
