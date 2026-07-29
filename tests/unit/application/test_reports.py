from datetime import UTC, datetime

from app_diagnosis.application.reports import render_markdown
from app_diagnosis.domain.diagnosis import DiagnosisCase
from app_diagnosis.domain.evidence import (
    Evidence,
    EvidenceReliability,
    EvidenceSource,
    EvidenceType,
)
from app_diagnosis.domain.report import DiagnosisReport


def test_markdown_report_separates_sections_and_uses_safe_evidence() -> None:
    diagnosis = DiagnosisCase.create(title="HTTP 500", symptom="password=[REDACTED]")
    evidence = Evidence.create(
        diagnosis_id=diagnosis.id,
        type=EvidenceType.USER_STATEMENT,
        source=EvidenceSource.USER_INPUT,
        content=diagnosis.symptom,
        reliability=EvidenceReliability.MEDIUM,
    )
    report = DiagnosisReport(diagnosis, None, (evidence,), (), (), (), datetime.now(UTC))
    markdown = render_markdown(report)
    assert "## Evidence" in markdown
    assert "password=[REDACTED]" in markdown
    assert "## 人工决定" in markdown
