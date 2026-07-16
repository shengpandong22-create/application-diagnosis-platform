from datetime import UTC, datetime
from uuid import UUID

import pytest

from app_diagnosis.domain.evidence import (
    Evidence,
    EvidenceReliability,
    EvidenceSource,
    EvidenceType,
    InvalidEvidenceValue,
    RedactionStatus,
)

DIAGNOSIS_ID = UUID("11111111-1111-1111-1111-111111111111")
NOW = datetime(2026, 7, 16, 9, 0, tzinfo=UTC)


def create_evidence(content: str = "HTTP 500 at payment endpoint") -> Evidence:
    return Evidence.create(
        diagnosis_id=DIAGNOSIS_ID,
        type=EvidenceType.USER_STATEMENT,
        source=EvidenceSource.USER_INPUT,
        content=content,
        reliability=EvidenceReliability.MEDIUM,
        now=NOW,
    )


def test_create_computes_stable_sha256_hash() -> None:
    evidence = create_evidence("  HTTP 500  ")
    assert evidence.content == "HTTP 500"
    assert evidence.content_hash == Evidence.hash_content("HTTP 500")
    assert len(evidence.content_hash) == 64


@pytest.mark.parametrize("content", ["", "   ", "x" * (Evidence.MAX_CONTENT_BYTES + 1)])
def test_rejects_blank_or_oversized_content(content: str) -> None:
    with pytest.raises(InvalidEvidenceValue):
        create_evidence(content)


@pytest.mark.parametrize(
    "content",
    [
        "Authorization: Bearer abcdefghijklmnop",
        "api_key=sk-abcdefghijklmnop",
        "password: super-secret",
        "postgresql://admin:secret@localhost/app",
    ],
)
def test_rejects_common_unredacted_secrets(content: str) -> None:
    with pytest.raises(InvalidEvidenceValue, match="unredacted secret"):
        create_evidence(content)


def test_accepts_redacted_content_and_status() -> None:
    evidence = Evidence.create(
        diagnosis_id=DIAGNOSIS_ID,
        type=EvidenceType.LOG_EXCERPT,
        source=EvidenceSource.USER_INPUT,
        content="Authorization: Bearer [REDACTED]",
        reliability=EvidenceReliability.HIGH,
        redaction_status=RedactionStatus.REDACTED,
        now=NOW,
    )
    assert evidence.redaction_status is RedactionStatus.REDACTED


def test_rejects_tampered_content_hash() -> None:
    valid = create_evidence()
    with pytest.raises(InvalidEvidenceValue, match="content_hash"):
        Evidence(
            id=valid.id,
            diagnosis_id=valid.diagnosis_id,
            type=valid.type,
            source=valid.source,
            source_reference=None,
            content=valid.content,
            content_hash="0" * 64,
            reliability=valid.reliability,
            created_at=NOW,
        )


def test_requires_utc_timestamp() -> None:
    with pytest.raises(InvalidEvidenceValue, match="UTC"):
        Evidence.create(
            diagnosis_id=DIAGNOSIS_ID,
            type=EvidenceType.KNOWLEDGE_ENTRY,
            source=EvidenceSource.LOCAL_KNOWLEDGE,
            content="Known NPE remediation",
            reliability=EvidenceReliability.HIGH,
            now=datetime(2026, 7, 16, 9, 0),
        )
