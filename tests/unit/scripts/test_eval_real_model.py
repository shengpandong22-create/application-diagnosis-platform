import importlib.util
import json
from pathlib import Path

import pytest

from app_diagnosis.evaluation.scenarios import EvaluationScenarioDataset


def load_script():
    path = Path("scripts/eval-real-model.py")
    spec = importlib.util.spec_from_file_location("eval_real_model", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dataset() -> EvaluationScenarioDataset:
    return EvaluationScenarioDataset.model_validate_json(
        Path("evals/cases/real-model-v1-definitions.json").read_text(encoding="utf-8")
    )


def test_selection_is_bounded_and_rejects_unknown_case() -> None:
    module = load_script()
    selected = module.select_scenarios(dataset(), {"npe", "timeout"}, 1)
    assert [item.id for item in selected] == ["npe"]
    with pytest.raises(ValueError, match="unknown cases"):
        module.select_scenarios(dataset(), {"not-a-case"}, 4)


def test_scored_case_preserves_observed_facts() -> None:
    module = load_script()
    scenario = dataset().scenarios[0]
    summary = {
        "termination_reason": "completed",
        "model": "deepseek-chat",
        "elapsed_ms": 123,
        "input_tokens": 20,
        "output_tokens": 10,
        "tool_trace": [{"name": "code__read", "status": "success"}],
        "evidence": [{"id": "11111111-1111-4111-8111-111111111111", "type": "code_excerpt"}],
        "conclusion": {"root_causes": []},
    }
    case = module.build_scored_case(scenario, summary, "real-v2-timeout60")
    encoded = json.dumps(case)
    assert case["observation"]["latency_ms"] == 123
    assert case["observation"]["observed_category"] is None
    assert case["expected_category"] is None
    assert case["versions"]["code_revision"] == "real-v2-timeout60"
    assert "deepseek-chat" in encoded


def test_model_error_is_a_scoreable_observation() -> None:
    module = load_script()
    scenario = dataset().scenarios[0]
    case = module.build_scored_case(
        scenario,
        {
            "termination_reason": "model_error",
            "run_error_code": "LLMTimeoutError",
            "tool_trace": [],
            "evidence": [],
            "conclusion": None,
        },
    )

    assert case["observation"]["termination_reason"] == "model_error"
    assert case["observation"]["conclusion"] is None


def test_runtime_timeout_must_be_positive() -> None:
    module = load_script()
    assert module.validate_timeout(60.0) == 60.0
    with pytest.raises(ValueError, match="must be positive"):
        module.validate_timeout(0)
