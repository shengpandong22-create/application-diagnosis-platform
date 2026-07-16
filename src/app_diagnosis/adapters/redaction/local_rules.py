import re
from dataclasses import dataclass

from app_diagnosis.domain.evidence import RedactionStatus
from app_diagnosis.ports.redaction import RedactionResult


@dataclass(frozen=True, slots=True)
class _Rule:
    category: str
    pattern: re.Pattern[str]
    replacement: str


class LocalRuleRedactor:
    """Deterministic, offline redaction for common credential shapes."""

    _RULES = (
        _Rule(
            "bearer_token",
            re.compile(r"(?i)\bbearer\s+(?!\[redacted\])[^\s,;]+"),
            "Bearer [REDACTED]",
        ),
        _Rule(
            "api_key",
            re.compile(
                r"(?i)\b(?:api[_-]?key|access[_-]?token|secret[_-]?key)\b"
                r"[\"']?\s*[=:]\s*[\"']?(?!\[redacted\])[^\s,;\"']+[\"']?"
            ),
            "api_key=[REDACTED]",
        ),
        _Rule(
            "password",
            re.compile(
                r"(?i)\b(?:password|passwd|pwd)\b[\"']?\s*[=:]\s*"
                r"[\"']?(?!\[redacted\])[^\s,;\"']+[\"']?"
            ),
            "password=[REDACTED]",
        ),
        _Rule(
            "private_api_key",
            re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
            "[REDACTED]",
        ),
        _Rule(
            "connection_string",
            re.compile(
                r"(?i)(\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^\s:/]+:)"
                r"[^\s@]+(@)"
            ),
            r"\1[REDACTED]\2",
        ),
        _Rule(
            "jwt",
            re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
            "[REDACTED]",
        ),
    )

    def redact(self, content: str) -> RedactionResult:
        redacted = content
        count = 0
        categories: list[str] = []
        for rule in self._RULES:
            redacted, replacements = rule.pattern.subn(rule.replacement, redacted)
            if replacements:
                count += replacements
                categories.append(rule.category)
        return RedactionResult(
            content=redacted,
            status=RedactionStatus.REDACTED if count else RedactionStatus.NOT_REQUIRED,
            redaction_count=count,
            matched_categories=tuple(categories),
        )
