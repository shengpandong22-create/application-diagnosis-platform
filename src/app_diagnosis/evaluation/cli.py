import argparse
import json
from pathlib import Path

from app_diagnosis.evaluation.models import EvaluationCase
from app_diagnosis.evaluation.runner import evaluate_suite


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic diagnosis evaluations")
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.cases.read_text(encoding="utf-8"))
    suite = evaluate_suite([EvaluationCase.model_validate(item) for item in payload["cases"]])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(suite.model_dump_json(indent=2), encoding="utf-8")
    versions = ", ".join(suite.dataset_versions)
    print(
        f"Diagnosis evaluation [{versions}]: {suite.passed}/{suite.total} passed; "
        f"citation={suite.citation_valid_rate:.1%}; "
        f"root_top1={suite.root_cause_top1_rate:.1%}; tokens={suite.total_tokens}"
    )
    if suite.passed != suite.total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
