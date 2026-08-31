import json
from pathlib import Path

from app_diagnosis.evaluation.scenarios import EvaluationScenarioDataset


def test_real_model_v1_scenarios_are_executable_and_balanced() -> None:
    payload = json.loads(
        Path("evals/cases/real-model-v1-definitions.json").read_text(encoding="utf-8")
    )
    dataset = EvaluationScenarioDataset.model_validate(payload)

    assert dataset.dataset_version == "java-lab-real-v1"
    assert len(dataset.scenarios) == 12
    assert len({item.base_case_id for item in dataset.scenarios}) == 8
    assert {item.expected_category for item in dataset.scenarios} == {
        "code_bug",
        "config",
        "dependency",
        "external",
    }
    assert all(item.keyword in item.symptom for item in dataset.scenarios)
    assert all(item.allowed_root_cause_keywords for item in dataset.scenarios)


def test_real_model_definitions_do_not_contain_generated_observations() -> None:
    payload = json.loads(
        Path("evals/cases/real-model-v1-definitions.json").read_text(encoding="utf-8")
    )

    assert all("observation" not in item for item in payload["scenarios"])
    assert set(payload["annotation_policy"]) == {"top1", "top3", "keywords"}
