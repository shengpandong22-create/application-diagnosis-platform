from dataclasses import dataclass
from typing import Protocol

from app_diagnosis.domain.evidence import RedactionStatus


@dataclass(frozen=True, slots=True)
class RedactionResult:
    content: str
    status: RedactionStatus
    redaction_count: int
    matched_categories: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.redaction_count < 0:
            raise ValueError("redaction_count must not be negative")
        if self.redaction_count == 0 and self.status is not RedactionStatus.NOT_REQUIRED:
            raise ValueError("unchanged content must have not_required status")
        if self.redaction_count > 0 and self.status is not RedactionStatus.REDACTED:
            raise ValueError("changed content must have redacted status")


class Redactor(Protocol):
    def redact(self, content: str) -> RedactionResult: ...
