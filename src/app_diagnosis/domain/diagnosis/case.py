from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any, ClassVar, Self
from uuid import UUID, uuid4

from app_diagnosis.domain.diagnosis.enums import DiagnosisStatus, ProblemType
from app_diagnosis.domain.diagnosis.errors import (
    InvalidDiagnosisStateTransition,
    InvalidDiagnosisValue,
)


def _require_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise InvalidDiagnosisValue(f"{field_name} must be timezone-aware UTC")


@dataclass(slots=True)
class DiagnosisCase:
    id: UUID
    title: str
    problem_type: ProblemType
    status: DiagnosisStatus
    symptom: str
    submitted_log: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    conclusion: dict[str, Any] | None = None

    _ALLOWED_TRANSITIONS: ClassVar[Mapping[DiagnosisStatus, frozenset[DiagnosisStatus]]] = (
        MappingProxyType(
            {
                DiagnosisStatus.CREATED: frozenset(
                    {DiagnosisStatus.INVESTIGATING, DiagnosisStatus.CANCELLED}
                ),
                DiagnosisStatus.INVESTIGATING: frozenset(
                    {
                        DiagnosisStatus.WAITING_FOR_INPUT,
                        DiagnosisStatus.WAITING_FOR_CONFIRMATION,
                        DiagnosisStatus.INCONCLUSIVE,
                        DiagnosisStatus.CANCELLED,
                    }
                ),
                DiagnosisStatus.WAITING_FOR_INPUT: frozenset({DiagnosisStatus.INVESTIGATING}),
                DiagnosisStatus.WAITING_FOR_CONFIRMATION: frozenset(
                    {
                        DiagnosisStatus.CONFIRMED,
                        DiagnosisStatus.REJECTED,
                        DiagnosisStatus.INVESTIGATING,
                    }
                ),
                DiagnosisStatus.CONFIRMED: frozenset(),
                DiagnosisStatus.REJECTED: frozenset(),
                DiagnosisStatus.INCONCLUSIVE: frozenset(),
                DiagnosisStatus.CANCELLED: frozenset(),
            }
        )
    )

    def __post_init__(self) -> None:
        self.title = self.title.strip()
        self.symptom = self.symptom.strip()
        if not self.title:
            raise InvalidDiagnosisValue("title must not be blank")
        if not self.symptom:
            raise InvalidDiagnosisValue("symptom must not be blank")
        if self.version < 0:
            raise InvalidDiagnosisValue("version must not be negative")
        _require_utc(self.created_at, "created_at")
        _require_utc(self.updated_at, "updated_at")
        if self.updated_at < self.created_at:
            raise InvalidDiagnosisValue("updated_at must not be earlier than created_at")

    @classmethod
    def create(
        cls,
        *,
        title: str,
        symptom: str,
        submitted_log: str | None = None,
        problem_type: ProblemType = ProblemType.GENERIC_APPLICATION_ERROR,
        diagnosis_id: UUID | None = None,
        now: datetime | None = None,
    ) -> Self:
        occurred_at = now or datetime.now(UTC)
        _require_utc(occurred_at, "now")
        return cls(
            id=diagnosis_id or uuid4(),
            title=title,
            problem_type=problem_type,
            status=DiagnosisStatus.CREATED,
            symptom=symptom,
            submitted_log=submitted_log,
            version=0,
            created_at=occurred_at,
            updated_at=occurred_at,
            conclusion=None,
        )

    @property
    def is_terminal(self) -> bool:
        return self.status.is_terminal

    def start_investigation(self, *, at: datetime | None = None) -> None:
        self._transition_to(DiagnosisStatus.INVESTIGATING, at=at)

    def wait_for_input(self, *, at: datetime | None = None) -> None:
        self._transition_to(DiagnosisStatus.WAITING_FOR_INPUT, at=at)

    def request_confirmation(self, *, at: datetime | None = None) -> None:
        self._transition_to(DiagnosisStatus.WAITING_FOR_CONFIRMATION, at=at)

    def mark_inconclusive(self, *, at: datetime | None = None) -> None:
        self._transition_to(DiagnosisStatus.INCONCLUSIVE, at=at)

    def confirm(self, *, at: datetime | None = None) -> None:
        self._transition_to(DiagnosisStatus.CONFIRMED, at=at)

    def reject(self, *, at: datetime | None = None) -> None:
        self._transition_to(DiagnosisStatus.REJECTED, at=at)

    def reopen_investigation(self, *, at: datetime | None = None) -> None:
        self._transition_to(DiagnosisStatus.INVESTIGATING, at=at)

    def cancel(self, *, at: datetime | None = None) -> None:
        self._transition_to(DiagnosisStatus.CANCELLED, at=at)

    def record_initial_conclusion(
        self,
        conclusion: dict[str, Any],
        *,
        needs_input: bool,
        at: datetime | None = None,
    ) -> None:
        if not conclusion:
            raise InvalidDiagnosisValue("conclusion must not be empty")
        target = (
            DiagnosisStatus.WAITING_FOR_INPUT
            if needs_input
            else DiagnosisStatus.WAITING_FOR_CONFIRMATION
        )
        self._transition_to(target, at=at)
        self.conclusion = dict(conclusion)

    def _transition_to(self, target: DiagnosisStatus, *, at: datetime | None) -> None:
        if target not in self._ALLOWED_TRANSITIONS[self.status]:
            raise InvalidDiagnosisStateTransition(self.status, target)

        occurred_at = at or datetime.now(UTC)
        _require_utc(occurred_at, "transition time")
        if occurred_at < self.updated_at:
            raise InvalidDiagnosisValue("transition time must not be earlier than updated_at")

        self.status = target
        self.updated_at = occurred_at
        self.version += 1
