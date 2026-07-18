from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from app_diagnosis.adapters.config import LocalConfigRepository
from app_diagnosis.adapters.logs import LocalLogFileReader
from app_diagnosis.adapters.redaction import LocalRuleRedactor
from app_diagnosis.domain.diagnosis import ProblemType
from app_diagnosis.ports.health_check import HealthCheckResult
from app_diagnosis.tools.config import ConfigReadInput, ConfigReadTool
from app_diagnosis.tools.contracts import ToolExecutionContext, ToolExecutionStatus, ToolRiskLevel
from app_diagnosis.tools.health import HealthCheckInput, HealthCheckTool
from app_diagnosis.tools.log_search import LogSearchInput, LogSearchTool


def _context() -> ToolExecutionContext:
    return ToolExecutionContext(
        diagnosis_id=uuid4(),
        agent_run_id=uuid4(),
        actor="test",
        environment="test",
        deadline=datetime.now(UTC) + timedelta(minutes=1),
        audit_correlation_id="phase2-tools",
        permissions=frozenset({"config:read", "log:read", "health:read"}),
        problem_type=ProblemType.GENERIC_APPLICATION_ERROR,
        max_output_bytes=4096,
    )


async def test_config_tool_redacts_before_result_and_evidence(tmp_path: Path) -> None:
    (tmp_path / "application.yml").write_text("password=secret\n", encoding="utf-8")
    tool = ConfigReadTool(LocalConfigRepository(tmp_path), LocalRuleRedactor())
    result = await tool.execute(
        ConfigReadInput(path="application.yml", start_line=1, end_line=1), _context()
    )
    assert tool.risk_level is ToolRiskLevel.READ_ONLY
    assert result.status is ToolExecutionStatus.SUCCESS
    assert "secret" not in result.model_summary
    assert result.evidence_drafts[0].type == "config_excerpt"


async def test_log_tool_preserves_single_event_and_redacts(tmp_path: Path) -> None:
    (tmp_path / "app.log").write_text(
        "2026-07-18 10:00:00 ERROR timeout password=secret\n"
        " stack\n"
        "2026-07-18 10:00:01 ERROR later failure\n",
        encoding="utf-8",
    )
    tool = LogSearchTool(LocalLogFileReader(tmp_path), LocalRuleRedactor())
    result = await tool.execute(LogSearchInput(path="app.log", keyword="timeout"), _context())
    assert result.status is ToolExecutionStatus.SUCCESS
    assert "secret" not in result.model_summary
    assert "later failure" not in result.model_summary
    assert result.evidence_drafts[0].source == "local_log"


class _FakeHealthClient:
    async def check(self, target: str) -> HealthCheckResult:
        return HealthCheckResult(
            target=target,
            reachable=False,
            status_code=None,
            duration_ms=12,
            summary="ConnectError",
            error_code="ConnectError",
        )


async def test_health_connection_failure_is_successful_diagnostic_result() -> None:
    tool = HealthCheckTool(_FakeHealthClient())
    result = await tool.execute(HealthCheckInput(target="java-lab"), _context())
    assert tool.risk_level is ToolRiskLevel.READ_ONLY
    assert result.status is ToolExecutionStatus.SUCCESS
    assert result.data is not None and result.data.reachable is False
    assert result.evidence_drafts[0].type == "health_check"
