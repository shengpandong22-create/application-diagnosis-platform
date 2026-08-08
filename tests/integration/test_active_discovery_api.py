import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from tests.fakes.llm import FakeLLMClient
from tests.integration.test_service_catalog_api import (
    conclusion_without_citations,
    migrated_client,
    response,
)

from app_diagnosis.ports.llm import LLMTransportError, ToolCall


def _event(service_id: str, *, source_event_id: str = "source-001") -> dict:
    return {
        "service_id": service_id,
        "environment": "local",
        "occurred_at": datetime(2026, 8, 8, 10, 7, tzinfo=UTC).isoformat(),
        "severity": "ERROR",
        "message": "NullPointerException password=secret-value",
        "exception_type": "java.lang.NullPointerException",
        "source_event_id": source_event_id,
        "stack_frames": [
            {
                "class_name": "dev.agentstudy.lab.OrderService",
                "method_name": "submit",
                "file_name": "OrderService.java",
                "line_number": 42,
            }
        ],
    }


def _service(client) -> dict:
    return client.post(
        "/api/v1/services",
        json={"name": "java-lab", "environment": "local"},
    ).json()


def test_new_incident_triggers_once_and_is_visible_in_report_trace(tmp_path: Path) -> None:
    fake = FakeLLMClient([response(content=conclusion_without_citations())])
    with migrated_client(tmp_path, fake) as client:
        service = _service(client)
        first = client.post("/api/v1/discovery/replay", json=[_event(service["id"])])
        assert first.status_code == 200
        result = first.json()[0]
        assert result["triggered"] is True
        assert result["diagnosis_id"]
        assert len(fake.calls) == 1

        repeated = client.post("/api/v1/discovery/replay", json=[_event(service["id"])])
        assert repeated.status_code == 200
        assert repeated.json()[0]["triggered"] is False
        assert len(fake.calls) == 1

        diagnosis_id = result["diagnosis_id"]
        evidence = client.get(f"/api/v1/diagnoses/{diagnosis_id}/evidence").json()
        serialized = str(evidence)
        assert "secret-value" not in serialized
        assert any(item["metadata"].get("automatic_trigger") for item in evidence)
        diagnosis = client.get(f"/api/v1/diagnoses/{diagnosis_id}").json()
        assert diagnosis["status"] != "confirmed"

        report = client.get(f"/api/v1/diagnoses/{diagnosis_id}/report.md").text
        assert "主动发现来源" in report
        assert result["incident"]["id"] in report
        trace = client.get(f"/api/v1/diagnoses/{diagnosis_id}/trace").json()
        assert trace["incident_id"] == result["incident"]["id"]


def test_unregistered_service_is_rejected_before_model_call(tmp_path: Path) -> None:
    fake = FakeLLMClient([])
    with migrated_client(tmp_path, fake) as client:
        result = client.post("/api/v1/discovery/replay", json=[_event(str(uuid4()))])
        assert result.status_code == 404
        assert fake.calls == []


def test_model_failure_preserves_discovery_facts(tmp_path: Path) -> None:
    fake = FakeLLMClient(
        [
            response(
                tool_calls=(
                    ToolCall(
                        id="knowledge-1",
                        name="knowledge__search",
                        arguments_json='{"query":"NullPointerException","limit":1}',
                    ),
                )
            ),
            LLMTransportError("offline"),
        ]
    )
    with migrated_client(tmp_path, fake) as client:
        service = _service(client)
        result = client.post(
            "/api/v1/discovery/replay",
            json=[_event(service["id"], source_event_id="failure-001")],
        ).json()[0]
        assert result["triggered"] is True
        assert result["termination_reason"] != "completed"
        diagnosis_id = result["diagnosis_id"]
        assert client.get(f"/api/v1/incidents/{result['incident']['id']}").status_code == 200
        assert client.get(f"/api/v1/diagnoses/{diagnosis_id}/evidence").json()
        runs = client.get(f"/api/v1/diagnoses/{diagnosis_id}/runs")
        assert runs.status_code == 200
        assert "knowledge__search" in runs.text
    with sqlite3.connect(tmp_path / "services.db") as connection:
        actions = {row[0] for row in connection.execute("SELECT action FROM audit_events")}
    assert "diagnosis.auto_triggered" in actions
