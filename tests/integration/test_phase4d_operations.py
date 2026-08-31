from datetime import UTC, datetime
from pathlib import Path

import pytest
from tests.fakes.llm import FakeLLMClient
from tests.integration.test_active_discovery_api import _event, _service
from tests.integration.test_service_catalog_api import (
    conclusion_without_citations,
    migrated_client,
    response,
)


def test_daily_summary_matches_incident_and_diagnosis_facts(tmp_path: Path) -> None:
    fake = FakeLLMClient([response(content=conclusion_without_citations())])
    fixed_now = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)
    with migrated_client(tmp_path, fake, clock=lambda: fixed_now) as client:
        service = _service(client)
        first = _event(service["id"], source_event_id="daily-1")
        second = _event(service["id"], source_event_id="daily-2")
        client.post("/api/v1/discovery/replay", json=[first]).raise_for_status()
        client.post("/api/v1/discovery/replay", json=[second]).raise_for_status()
        summary = client.get(f"/api/v1/services/{service['id']}/daily-summary?day=2026-08-08")
        assert summary.status_code == 200
        body = summary.json()
        assert body["incident_count"] == 1
        assert body["new_fingerprint_count"] == 1
        assert body["occurrence_count"] == 2
        assert body["waiting_for_confirmation"] == 1
        markdown = client.get(f"/api/v1/services/{service['id']}/daily-summary.md?day=2026-08-08")
        assert "demo-secret" not in markdown.text
        assert "高频 Incident" in markdown.text


@pytest.mark.parametrize("fixed_day", [(2025, 1, 1), (2026, 1, 1)])
def test_daily_summary_is_independent_of_system_date(
    tmp_path: Path, fixed_day: tuple[int, int, int]
) -> None:
    fixed_now = datetime(*fixed_day, 12, 0, tzinfo=UTC)
    fake = FakeLLMClient([response(content=conclusion_without_citations())])
    with migrated_client(tmp_path, fake, clock=lambda: fixed_now) as client:
        service = _service(client)
        event = _event(service["id"], source_event_id=f"cross-date-{fixed_now.date()}")
        event["occurred_at"] = fixed_now.isoformat()
        client.post("/api/v1/discovery/replay", json=[event]).raise_for_status()

        summary = client.get(
            f"/api/v1/services/{service['id']}/daily-summary?day={fixed_now.date()}"
        )
        summary.raise_for_status()
        body = summary.json()
        assert body["incident_count"] == 1
        assert body["waiting_for_confirmation"] == 1


def test_reject_candidate_requires_label_before_promotion(tmp_path: Path) -> None:
    fake = FakeLLMClient([response(content=conclusion_without_citations())])
    with migrated_client(tmp_path, fake) as client:
        service = _service(client)
        discovered = client.post(
            "/api/v1/discovery/replay",
            json=[_event(service["id"], source_event_id="reject-1")],
        ).json()[0]
        diagnosis_id = discovered["diagnosis_id"]
        rejected = client.post(
            f"/api/v1/diagnoses/{diagnosis_id}/confirmation",
            json={"action": "reject", "comment": "root cause was inaccurate"},
        )
        assert rejected.status_code == 200
        candidates = client.get("/api/v1/evaluation-candidates").json()
        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate["status"] == "candidate"
        premature = client.post(f"/api/v1/evaluation-candidates/{candidate['id']}/promote")
        assert premature.status_code == 409
        evidence = client.get(f"/api/v1/diagnoses/{diagnosis_id}/evidence").json()
        foreign = client.post(
            f"/api/v1/evaluation-candidates/{candidate['id']}/label",
            json={
                "expected_category": "code_bug",
                "expected_root_cause": "wrong evidence",
                "required_evidence_ids": ["11111111-1111-1111-1111-111111111111"],
                "prompt_version": "generic-v1",
            },
        )
        assert foreign.status_code == 409
        labeled = client.post(
            f"/api/v1/evaluation-candidates/{candidate['id']}/label",
            json={
                "expected_category": "code_bug",
                "expected_root_cause": "Order object was null",
                "required_evidence_ids": [evidence[0]["id"]],
                "prompt_version": "generic-v1",
            },
        )
        assert labeled.status_code == 200
        assert labeled.json()["status"] == "labeled"
        promoted = client.post(f"/api/v1/evaluation-candidates/{candidate['id']}/promote")
        assert promoted.status_code == 200
        assert promoted.json()["status"] == "promoted"
        trend = client.get("/api/v1/evaluation-candidates/trend").json()
        assert trend["status_counts"] == {"promoted": 1}
        assert trend["prompt_version_counts"] == {"generic-v1": 1}
