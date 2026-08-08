import json
from pathlib import Path

from app_diagnosis.evaluation import EvaluationCase, evaluate_suite


def _baseline_cases() -> list[EvaluationCase]:
    payload = json.loads(
        Path("evals/cases/phase4a-quality-baseline.json").read_text(encoding="utf-8")
    )
    return [EvaluationCase.model_validate(item) for item in payload["cases"]]


def test_phase4a_suite_is_deterministic_versioned_and_passes() -> None:
    first = evaluate_suite(_baseline_cases())
    second = evaluate_suite(_baseline_cases())

    assert first == second
    assert first.total == first.passed == 2
    assert first.dataset_versions == ["phase4a-v1"]
    assert first.citation_valid_rate == 1.0
    assert first.citation_precision == first.citation_recall == 1.0
    assert first.category_accuracy == 1.0
    assert first.category_confusion_matrix == {
        "code_bug": {"code_bug": 1},
        "insufficient_evidence": {"insufficient_evidence": 1},
    }
    assert first.information_sufficiency_accuracy == 1.0
    assert first.tool_selection_accuracy == 1.0
    assert first.root_cause_top1_rate == first.root_cause_top3_rate == 1.0
    assert first.unsupported_claim_rate == first.high_confidence_error_rate == 0.0
    assert first.total_tokens == 415
    assert first.average_latency_ms == 100.0


def test_suite_reports_unsupported_claims_and_high_confidence_errors() -> None:
    raw = _baseline_cases()[0].model_dump(mode="json")
    raw["id"] = "bad-high-confidence-case"
    raw["observation"]["observed_category"] = "dependency"
    raw["observation"]["confidence"] = 0.95
    raw["observation"]["conclusion"]["root_causes"] = [
        {
            "statement": "Unrelated database issue",
            "status": "probable",
            "evidence_ids": [],
        }
    ]

    suite = evaluate_suite([EvaluationCase.model_validate(raw)])
    result = suite.results[0]

    assert not result.passed
    assert result.category_matches is False
    assert not result.root_cause_top1_matches
    assert result.unsupported_claim_rate > 0
    assert result.high_confidence_error
    assert "category_mismatch" in result.failures
    assert "unsupported_claims" in result.failures
    assert suite.category_confusion_matrix == {"code_bug": {"dependency": 1}}
    assert suite.high_confidence_error_rate == 1.0


def test_legacy_case_shape_remains_compatible() -> None:
    payload = json.loads(Path("evals/cases/phase0c-baseline.json").read_text(encoding="utf-8"))
    suite = evaluate_suite([EvaluationCase.model_validate(item) for item in payload["cases"]])

    assert suite.passed == suite.total == 2
    assert suite.dataset_versions == ["unspecified"]
    assert suite.category_accuracy is None
    assert suite.tool_selection_accuracy is None
