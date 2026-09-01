import json
from pathlib import Path


def test_java_lab_case_definitions_cover_three_distinct_failures() -> None:
    payload = json.loads(
        Path("evals/cases/phase1-java-lab-cases.json").read_text(encoding="utf-8")
    )
    cases = {item["id"]: item for item in payload["cases"]}

    assert set(cases) == {"npe", "connection-refused", "timeout"}
    assert cases["connection-refused"]["expected_code_paths"] == ["PaymentClient.java"]
    assert cases["timeout"]["expected_code_paths"] == ["InventoryClient.java"]
    assert cases["timeout"]["keyword"] == "InventoryClient.loadInventory"
    assert all(item["keyword"] for item in cases.values())
    assert all(item["allowed_root_cause_keywords"] for item in cases.values())
