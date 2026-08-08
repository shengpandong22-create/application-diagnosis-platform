import json
from pathlib import Path


def test_java_lab_case_definitions_cover_phase4a_quality_dimensions() -> None:
    payload = json.loads(
        Path("evals/cases/phase4a-java-lab-cases.json").read_text(encoding="utf-8")
    )
    cases = {item["id"]: item for item in payload["cases"]}

    assert payload["dataset_version"] == "java-lab-phase4a-v1"
    assert len(cases) == 8
    assert {item["expected_category"] for item in cases.values()} == {
        "code_bug",
        "config",
        "dependency",
        "external",
    }
    assert {item["expected_context_depth"] for item in cases.values()} >= {
        "class",
        "cross_file",
        "config",
        "related_logs",
    }
    assert cases["connection-refused"]["expected_code_paths"] == [
        "PaymentClient.java",
        "application.yml",
    ]
    assert cases["timeout"]["expected_code_paths"] == [
        "InventoryClient.java",
        "application.yml",
    ]
    assert "related_logs__query" in cases["chained-downstream-npe"]["expected_tools"]
    assert all(item["trigger_path"].startswith("/lab/") for item in cases.values())
    assert all(item["keyword"] for item in cases.values())
    assert all(item["expected_evidence_types"] for item in cases.values())
    assert all(item["allowed_root_cause_keywords"] for item in cases.values())
