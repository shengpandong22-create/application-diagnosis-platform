from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest

from app_diagnosis.domain.diagnosis import (
    AgentTerminationReason,
    DiagnosisCase,
    DiagnosisStatus,
    FindingStatus,
    InvalidDiagnosisStateTransition,
    InvalidDiagnosisValue,
    ProblemType,
)

NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)


def create_case() -> DiagnosisCase:
    return DiagnosisCase.create(
        diagnosis_id=UUID("11111111-1111-1111-1111-111111111111"),
        title=" Payment API failure ",
        symptom=" HTTP 500 with NullPointerException ",
        submitted_log="java.lang.NullPointerException",
        now=NOW,
    )


def test_create_case_normalizes_values_and_sets_initial_state() -> None:
    case = create_case()

    assert case.id == UUID("11111111-1111-1111-1111-111111111111")
    assert case.title == "Payment API failure"
    assert case.symptom == "HTTP 500 with NullPointerException"
    assert case.problem_type is ProblemType.GENERIC_APPLICATION_ERROR
    assert case.status is DiagnosisStatus.CREATED
    assert case.version == 0
    assert case.created_at == NOW
    assert case.updated_at == NOW
    assert not case.is_terminal


@pytest.mark.parametrize("field,value", [("title", "  "), ("symptom", "")])
def test_create_case_rejects_blank_required_text(field: str, value: str) -> None:
    arguments = {"title": "title", "symptom": "symptom", field: value}

    with pytest.raises(InvalidDiagnosisValue):
        DiagnosisCase.create(**arguments, now=NOW)


@pytest.mark.parametrize(
    "invalid_time",
    [
        datetime(2026, 7, 15, 12, 0),
        datetime(2026, 7, 15, 20, 0, tzinfo=timezone(timedelta(hours=8))),
    ],
)
def test_create_case_requires_explicit_utc(invalid_time: datetime) -> None:
    with pytest.raises(InvalidDiagnosisValue, match="timezone-aware UTC"):
        DiagnosisCase.create(title="title", symptom="symptom", now=invalid_time)


def test_investigation_can_wait_for_input_and_resume() -> None:
    case = create_case()

    case.start_investigation(at=NOW + timedelta(seconds=1))
    case.wait_for_input(at=NOW + timedelta(seconds=2))
    case.start_investigation(at=NOW + timedelta(seconds=3))

    assert case.status is DiagnosisStatus.INVESTIGATING
    assert case.version == 3
    assert case.updated_at == NOW + timedelta(seconds=3)


@pytest.mark.parametrize("decision", ["confirm", "reject"])
def test_waiting_confirmation_accepts_a_human_decision(decision: str) -> None:
    case = create_case()
    case.start_investigation(at=NOW)
    case.request_confirmation(at=NOW)

    getattr(case, decision)(at=NOW)

    expected = DiagnosisStatus.CONFIRMED if decision == "confirm" else DiagnosisStatus.REJECTED
    assert case.status is expected
    assert case.is_terminal


def test_waiting_confirmation_can_reopen_investigation() -> None:
    case = create_case()
    case.start_investigation(at=NOW)
    case.request_confirmation(at=NOW)

    case.reopen_investigation(at=NOW)

    assert case.status is DiagnosisStatus.INVESTIGATING
    assert not case.is_terminal


def test_investigation_can_end_inconclusive() -> None:
    case = create_case()
    case.start_investigation(at=NOW)

    case.mark_inconclusive(at=NOW)

    assert case.status is DiagnosisStatus.INCONCLUSIVE
    assert case.is_terminal


@pytest.mark.parametrize("start_first", [False, True])
def test_created_or_investigating_case_can_be_cancelled(start_first: bool) -> None:
    case = create_case()
    if start_first:
        case.start_investigation(at=NOW)

    case.cancel(at=NOW)

    assert case.status is DiagnosisStatus.CANCELLED
    assert case.is_terminal


def test_invalid_transition_preserves_case_state() -> None:
    case = create_case()

    with pytest.raises(InvalidDiagnosisStateTransition) as error:
        case.confirm(at=NOW)

    assert error.value.current is DiagnosisStatus.CREATED
    assert error.value.target is DiagnosisStatus.CONFIRMED
    assert case.status is DiagnosisStatus.CREATED
    assert case.version == 0
    assert case.updated_at == NOW


@pytest.mark.parametrize(
    "terminal_action",
    ["confirm", "reject", "mark_inconclusive", "cancel"],
)
def test_terminal_state_cannot_transition_again(terminal_action: str) -> None:
    case = create_case()
    case.start_investigation(at=NOW)
    if terminal_action in {"confirm", "reject"}:
        case.request_confirmation(at=NOW)
    getattr(case, terminal_action)(at=NOW)

    with pytest.raises(InvalidDiagnosisStateTransition):
        case.start_investigation(at=NOW)


def test_transition_rejects_time_before_last_update() -> None:
    case = create_case()
    case.start_investigation(at=NOW + timedelta(seconds=10))

    with pytest.raises(InvalidDiagnosisValue, match="earlier than updated_at"):
        case.wait_for_input(at=NOW + timedelta(seconds=9))

    assert case.status is DiagnosisStatus.INVESTIGATING
    assert case.version == 1


def test_domain_enums_have_stable_wire_values() -> None:
    assert FindingStatus.INSUFFICIENT_EVIDENCE == "insufficient_evidence"
    assert AgentTerminationReason.TOOL_BUDGET_EXHAUSTED == "tool_budget_exhausted"
