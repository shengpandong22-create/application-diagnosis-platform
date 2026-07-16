from datetime import UTC, datetime, timedelta

import pytest

from app_diagnosis.domain.knowledge import (
    InvalidKnowledgeStatusTransition,
    InvalidKnowledgeValue,
    KnowledgeEntry,
    KnowledgeStatus,
)

NOW = datetime(2026, 7, 16, 10, 0, tzinfo=UTC)


def test_create_normalizes_classifications_and_defaults_to_candidate() -> None:
    entry = KnowledgeEntry.create(
        entry_id=" npe ",
        title=" NPE ",
        summary=" Check stack ",
        source=" manual ",
        error_types=("NPE", "NPE"),
        tags=("java",),
        now=NOW,
    )
    assert entry.id == "npe"
    assert entry.error_types == ("NPE",)
    assert entry.status is KnowledgeStatus.CANDIDATE


def test_status_transition_returns_new_entry_and_preserves_creation_time() -> None:
    entry = KnowledgeEntry.create(
        entry_id="npe", title="NPE", summary="Check stack", source="manual", now=NOW
    )
    confirmed = entry.with_status(KnowledgeStatus.CONFIRMED, at=NOW + timedelta(seconds=1))
    assert entry.status is KnowledgeStatus.CANDIDATE
    assert confirmed.status is KnowledgeStatus.CONFIRMED
    assert confirmed.created_at == NOW


def test_status_transition_is_idempotent_for_same_status() -> None:
    entry = KnowledgeEntry.create(
        entry_id="npe", title="NPE", summary="Check stack", source="manual", now=NOW
    )
    assert entry.with_status(KnowledgeStatus.CANDIDATE) is entry


def test_status_transition_rejects_reverse_and_retired_changes() -> None:
    candidate = KnowledgeEntry.create(
        entry_id="npe", title="NPE", summary="Check stack", source="manual", now=NOW
    )
    confirmed = candidate.with_status(KnowledgeStatus.CONFIRMED, at=NOW + timedelta(seconds=1))
    retired = confirmed.with_status(KnowledgeStatus.RETIRED, at=NOW + timedelta(seconds=2))
    with pytest.raises(InvalidKnowledgeStatusTransition):
        confirmed.with_status(KnowledgeStatus.CANDIDATE)
    with pytest.raises(InvalidKnowledgeStatusTransition):
        retired.with_status(KnowledgeStatus.CONFIRMED)


def test_rejects_blank_and_naive_time() -> None:
    with pytest.raises(InvalidKnowledgeValue):
        KnowledgeEntry.create(entry_id="", title="NPE", summary="Check", source="manual", now=NOW)
    with pytest.raises(InvalidKnowledgeValue, match="UTC"):
        KnowledgeEntry.create(
            entry_id="npe", title="NPE", summary="Check", source="manual", now=datetime(2026, 7, 16)
        )
