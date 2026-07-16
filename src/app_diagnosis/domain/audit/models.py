from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class AuditEvent:
    id: UUID
    actor: str
    action: str
    target_type: str
    target_id: str
    summary: str
    correlation_id: str | None
    created_at: datetime

    def __post_init__(self) -> None:
        for name, value in (
            ("actor", self.actor),
            ("action", self.action),
            ("target_type", self.target_type),
            ("target_id", self.target_id),
            ("summary", self.summary),
        ):
            if not value.strip():
                raise ValueError(f"audit {name} must not be blank")
        if len(self.summary) > 500:
            raise ValueError("audit summary must not exceed 500 characters")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() != UTC.utcoffset(
            self.created_at
        ):
            raise ValueError("audit created_at must be timezone-aware UTC")

    @classmethod
    def create(
        cls,
        *,
        actor: str,
        action: str,
        target_type: str,
        target_id: str,
        summary: str,
        correlation_id: str | None = None,
    ) -> "AuditEvent":
        return cls(
            id=uuid4(),
            actor=actor.strip(),
            action=action.strip(),
            target_type=target_type.strip(),
            target_id=target_id.strip(),
            summary=summary.strip(),
            correlation_id=correlation_id.strip() if correlation_id else None,
            created_at=datetime.now(UTC),
        )
