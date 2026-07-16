from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Self


class InvalidKnowledgeValue(ValueError):
    """Raised when a knowledge entry violates a domain invariant."""


class InvalidKnowledgeStatusTransition(ValueError):
    """Raised when a knowledge status transition is not allowed."""


class KnowledgeStatus(StrEnum):
    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    RETIRED = "retired"


@dataclass(frozen=True, slots=True)
class KnowledgeEntry:
    id: str
    title: str
    summary: str
    error_types: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    source: str = "manual"
    status: KnowledgeStatus = KnowledgeStatus.CANDIDATE
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        for name, value, maximum in (
            ("id", self.id, 100),
            ("title", self.title, 200),
            ("summary", self.summary, 4000),
            ("source", self.source, 100),
        ):
            if not value.strip():
                raise InvalidKnowledgeValue(f"{name} must not be blank")
            if len(value) > maximum:
                raise InvalidKnowledgeValue(f"{name} exceeds {maximum} characters")
        if len(self.error_types) > 20 or len(self.tags) > 30:
            raise InvalidKnowledgeValue("knowledge classification count exceeds limit")
        if any(not item.strip() for item in (*self.error_types, *self.tags)):
            raise InvalidKnowledgeValue("knowledge classifications must not be blank")
        _require_utc(self.created_at, "created_at")
        _require_utc(self.updated_at, "updated_at")
        if self.updated_at < self.created_at:
            raise InvalidKnowledgeValue("updated_at must not be earlier than created_at")
        object.__setattr__(self, "id", self.id.strip())
        object.__setattr__(self, "title", self.title.strip())
        object.__setattr__(self, "summary", self.summary.strip())
        object.__setattr__(self, "source", self.source.strip())
        object.__setattr__(self, "error_types", _normalized(self.error_types))
        object.__setattr__(self, "tags", _normalized(self.tags))

    @classmethod
    def create(
        cls,
        *,
        entry_id: str,
        title: str,
        summary: str,
        source: str,
        error_types: tuple[str, ...] = (),
        tags: tuple[str, ...] = (),
        status: KnowledgeStatus = KnowledgeStatus.CANDIDATE,
        now: datetime | None = None,
    ) -> Self:
        occurred_at = now or datetime.now(UTC)
        return cls(
            id=entry_id,
            title=title,
            summary=summary,
            error_types=error_types,
            tags=tags,
            source=source,
            status=status,
            created_at=occurred_at,
            updated_at=occurred_at,
        )

    def with_status(self, status: KnowledgeStatus, *, at: datetime | None = None) -> Self:
        if status is self.status:
            return self
        allowed = {
            KnowledgeStatus.CANDIDATE: {
                KnowledgeStatus.CONFIRMED,
                KnowledgeStatus.RETIRED,
            },
            KnowledgeStatus.CONFIRMED: {KnowledgeStatus.RETIRED},
            KnowledgeStatus.RETIRED: set(),
        }
        if status not in allowed[self.status]:
            raise InvalidKnowledgeStatusTransition(
                f"knowledge status cannot change from {self.status.value} to {status.value}"
            )
        occurred_at = at or datetime.now(UTC)
        return KnowledgeEntry(
            id=self.id,
            title=self.title,
            summary=self.summary,
            error_types=self.error_types,
            tags=self.tags,
            source=self.source,
            status=status,
            created_at=self.created_at,
            updated_at=occurred_at,
        )


def _require_utc(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise InvalidKnowledgeValue(f"{name} must be timezone-aware UTC")


def _normalized(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item.strip() for item in values))
