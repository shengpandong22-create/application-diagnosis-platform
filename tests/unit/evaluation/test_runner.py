import json
from pathlib import Path

from app_diagnosis.evaluation import EvaluationCase, evaluate_suite


def test_baseline_suite_is_deterministic_and_passes() -> None:
    payload = json.loads(Path("evals/cases/phase0c-baseline.json").read_text(encoding="utf-8"))
    first = evaluate_suite([EvaluationCase.model_validate(x) for x in payload["cases"]])
    second = evaluate_suite([EvaluationCase.model_validate(x) for x in payload["cases"]])
    assert first == second
    assert first.total == first.passed == 2
    assert first.citation_valid_rate == 1.0
