from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from app_diagnosis.adapters.logs import LocalLogFileReader
from app_diagnosis.adapters.redaction import LocalRuleRedactor
from app_diagnosis.domain.diagnosis import ProblemType
from app_diagnosis.tools.contracts import ToolExecutionContext, ToolExecutionStatus
from app_diagnosis.tools.related_logs import RelatedLogsInput, RelatedLogsQueryTool


def _context(reader: LocalLogFileReader) -> ToolExecutionContext:
    return ToolExecutionContext(
        diagnosis_id=uuid4(), agent_run_id=uuid4(), actor="test", environment="local",
        deadline=datetime.now(UTC) + timedelta(seconds=5), audit_correlation_id="trace-1",
        permissions=frozenset({"log:read"}),
        problem_type=ProblemType.GENERIC_APPLICATION_ERROR,
        max_output_bytes=10_000, log_reader=reader,
    )


async def test_related_logs_are_time_bounded_redacted_and_evidence_backed(
    tmp_path: Path,
) -> None:
    (tmp_path / "app.log").write_text(
        "2026-08-08 10:00:00 ERROR trace-1 first password=secret\n"
        "  at dev.lab.A.run(A.java:1)\n"
        "2026-08-08 11:00:00 ERROR trace-1 second\n"
        "2026-08-08 12:00:00 ERROR other ignored\n",
        encoding="utf-8",
    )
    reader = LocalLogFileReader(tmp_path)
    result = await RelatedLogsQueryTool(reader, LocalRuleRedactor()).execute(
        RelatedLogsInput(
            path="app.log", trace_id="trace-1",
            started_at=datetime(2026, 8, 8, 9, 30, tzinfo=UTC),
            ended_at=datetime(2026, 8, 8, 11, 30, tzinfo=UTC), limit=1,
        ),
        _context(reader),
    )
    assert result.status is ToolExecutionStatus.SUCCESS
    assert len(result.evidence_drafts) == 1
    assert "secret" not in result.evidence_drafts[0].content
    assert result.evidence_drafts[0].source_reference == "app.log:1-2"


async def test_related_logs_reject_range_over_24_hours(tmp_path: Path) -> None:
    (tmp_path / "app.log").write_text("2026-08-08 10:00:00 trace-1\n", encoding="utf-8")
    reader = LocalLogFileReader(tmp_path)
    result = await RelatedLogsQueryTool(reader, LocalRuleRedactor()).execute(
        RelatedLogsInput(
            path="app.log", trace_id="trace-1",
            started_at=datetime(2026, 8, 7, tzinfo=UTC),
            ended_at=datetime(2026, 8, 9, tzinfo=UTC), limit=10,
        ),
        _context(reader),
    )
    assert result.status is ToolExecutionStatus.FAILED
