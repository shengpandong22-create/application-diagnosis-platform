import argparse
import json
from pathlib import Path

from app_diagnosis.evaluation.models import EvaluationCase
from app_diagnosis.evaluation.runner import evaluate_suite


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic Phase 0C evaluations")
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.cases.read_text(encoding="utf-8"))
    suite = evaluate_suite([EvaluationCase.model_validate(item) for item in payload["cases"]])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(suite.model_dump_json(indent=2), encoding="utf-8")
    print(f"Phase 0C evaluation: {suite.passed}/{suite.total} passed")
    if suite.passed != suite.total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
