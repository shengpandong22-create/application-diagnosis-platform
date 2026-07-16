from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class ConfirmationAction(StrEnum):
    CONFIRM = "confirm"
    REJECT = "reject"
    CONTINUE_INVESTIGATION = "continue_investigation"


@dataclass(frozen=True, slots=True)
class Confirmation:
    id: UUID
    diagnosis_id: UUID
    action: ConfirmationAction
    actor: str
    comment: str | None
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.actor.strip():
            raise ValueError("confirmation actor must not be blank")
        if self.comment is not None and not self.comment.strip():
            raise ValueError("confirmation comment must not be blank")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() != UTC.utcoffset(
            self.created_at
        ):
            raise ValueError("created_at must be timezone-aware UTC")

    @classmethod
    def create(
        cls,
        *,
        diagnosis_id: UUID,
        action: ConfirmationAction,
        actor: str,
        comment: str | None = None,
    ) -> "Confirmation":
        return cls(
            id=uuid4(),
            diagnosis_id=diagnosis_id,
            action=action,
            actor=actor.strip(),
            comment=comment.strip() if comment else None,
            created_at=datetime.now(UTC),
        )
