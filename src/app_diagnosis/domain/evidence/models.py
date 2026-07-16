import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, ClassVar, Self
from uuid import UUID, uuid4


class InvalidEvidenceValue(ValueError):
    """Raised when evidence violates a domain invariant."""


class EvidenceType(StrEnum):
    USER_STATEMENT = "user_statement"
    LOG_EXCERPT = "log_excerpt"
    KNOWLEDGE_ENTRY = "knowledge_entry"


class EvidenceSource(StrEnum):
    USER_INPUT = "user_input"
    LOCAL_KNOWLEDGE = "local_knowledge"


class EvidenceReliability(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RedactionStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    REDACTED = "redacted"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class Evidence:
    MAX_CONTENT_BYTES: ClassVar[int] = 16 * 1024
    _SECRET_PATTERNS: ClassVar[tuple[re.Pattern[str], ...]] = (
        re.compile(r"(?i)\bbearer\s+(?!\[redacted\])[^\s,;]+"),
        re.compile(r"(?i)\b(?:api[_-]?key|password|passwd|pwd)\s*[:=]\s*(?!\[redacted\])\S+"),
        re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
        re.compile(r"(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^\s]+:[^\s@]+@"),
    )

    id: UUID
    diagnosis_id: UUID
    type: EvidenceType
    source: EvidenceSource
    source_reference: str | None
    content: str
    content_hash: str
    reliability: EvidenceReliability
    metadata: dict[str, Any] = field(default_factory=dict)
    redaction_status: RedactionStatus = RedactionStatus.NOT_REQUIRED
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        content = self.content.strip()
        if not content:
            raise InvalidEvidenceValue("content must not be blank")
        if len(content.encode("utf-8")) > self.MAX_CONTENT_BYTES:
            raise InvalidEvidenceValue(
                f"content must not exceed {self.MAX_CONTENT_BYTES} UTF-8 bytes"
            )
        if any(pattern.search(content) for pattern in self._SECRET_PATTERNS):
            raise InvalidEvidenceValue("content appears to contain an unredacted secret")
        if self.source_reference is not None and not self.source_reference.strip():
            raise InvalidEvidenceValue("source_reference must not be blank")
        expected_hash = self.hash_content(content)
        if self.content_hash != expected_hash:
            raise InvalidEvidenceValue("content_hash does not match content")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() != UTC.utcoffset(
            self.created_at
        ):
            raise InvalidEvidenceValue("created_at must be timezone-aware UTC")
        if not isinstance(self.metadata, dict):
            raise InvalidEvidenceValue("metadata must be a dictionary")
        object.__setattr__(self, "content", content)
        object.__setattr__(self, "metadata", dict(self.metadata))

    @classmethod
    def create(
        cls,
        *,
        diagnosis_id: UUID,
        type: EvidenceType,
        source: EvidenceSource,
        content: str,
        reliability: EvidenceReliability,
        source_reference: str | None = None,
        metadata: dict[str, Any] | None = None,
        redaction_status: RedactionStatus = RedactionStatus.NOT_REQUIRED,
        evidence_id: UUID | None = None,
        now: datetime | None = None,
    ) -> Self:
        normalized = content.strip()
        return cls(
            id=evidence_id or uuid4(),
            diagnosis_id=diagnosis_id,
            type=type,
            source=source,
            source_reference=source_reference.strip() if source_reference else None,
            content=normalized,
            content_hash=cls.hash_content(normalized),
            reliability=reliability,
            metadata=metadata or {},
            redaction_status=redaction_status,
            created_at=now or datetime.now(UTC),
        )

    @staticmethod
    def hash_content(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
