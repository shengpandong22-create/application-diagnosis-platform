from datetime import UTC, datetime
from pathlib import Path

from tests.integration.test_service_catalog_api import migrated_client


def test_ingest_deduplicate_redact_and_list_incident(tmp_path: Path) -> None:
    with migrated_client(tmp_path) as client:
        service = client.post(
            "/api/v1/services", json={"name": "java-lab", "environment": "local"}
        ).json()
        payload = {
            "service_id": service["id"],
            "environment": "local",
            "occurred_at": datetime(2026, 8, 8, 10, 7, tzinfo=UTC).isoformat(),
            "severity": "ERROR",
            "message": "request failed password=secret-value",
            "exception_type": "java.lang.NullPointerException",
            "source_event_id": "event-001",
            "stack_frames": [
                {
                    "class_name": "dev.lab.OrderService",
                    "method_name": "submit",
                    "file_name": "OrderService.java",
                    "line_number": 42,
                }
            ],
        }
        first = client.post("/api/v1/incidents/events", json=payload)
        duplicate = client.post("/api/v1/incidents/events", json=payload)
        assert first.status_code == 201
        assert first.json()["is_novel"] is True
        assert "secret-value" not in first.json()["incident"]["sample_message"]
        assert duplicate.json()["duplicate_event"] is True
        assert duplicate.json()["incident"]["occurrence_count"] == 1
        listed = client.get(f"/api/v1/incidents?service_id={service['id']}")
        assert listed.status_code == 200
        assert len(listed.json()) == 1
