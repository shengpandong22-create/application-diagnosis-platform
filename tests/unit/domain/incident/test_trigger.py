from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app_diagnosis.domain.incident import (
    DiagnosisTriggerPolicy,
    Incident,
    IncidentAggregation,
    IncidentStatus,
)


def candidate() -> Incident:
    now = datetime(2026, 8, 8, 10, 0, tzinfo=UTC)
    return Incident(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        service_id=UUID("22222222-2222-2222-2222-222222222222"),
        environment="local",
        fingerprint="a" * 64,
        fingerprint_version="v1",
        aggregation_key="key",
        diagnosis_id=None,
        status=IncidentStatus.OPEN,
        exception_type="RuntimeException",
        sample_message="safe",
        occurrence_count=1,
        first_seen_at=now,
        last_seen_at=now,
        window_started_at=now,
        window_ends_at=now + timedelta(minutes=15),
        created_at=now,
        updated_at=now,
    )


def test_trigger_only_when_incident_has_no_diagnosis() -> None:
    policy = DiagnosisTriggerPolicy()
    incident = candidate()
    assert policy.decide(IncidentAggregation(incident, True)).should_trigger is True
    linked = replace(incident, diagnosis_id=incident.id)
    assert policy.decide(IncidentAggregation(linked, False)).should_trigger is False
    assert policy.decide(IncidentAggregation(incident, False, True)).should_trigger is False
