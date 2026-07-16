from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from app_diagnosis.adapters.code import LocalCodeRepository
from app_diagnosis.domain.code_workspace import CodeWorkspace
from app_diagnosis.domain.diagnosis import ProblemType
from app_diagnosis.tools.code import CodeReadInput, CodeReadTool, CodeSearchInput, CodeSearchTool
from app_diagnosis.tools.contracts import ToolExecutionContext, ToolExecutionStatus


def context() -> ToolExecutionContext:
    return ToolExecutionContext(
        diagnosis_id=uuid4(),
        agent_run_id=uuid4(),
        actor="test",
        environment="test",
        deadline=datetime.now(UTC) + timedelta(minutes=1),
        audit_correlation_id="code-test",
        permissions=frozenset({"code:read"}),
        problem_type=ProblemType.GENERIC_APPLICATION_ERROR,
        max_output_bytes=4096,
    )


async def test_code_read_creates_citable_evidence(tmp_path: Path) -> None:
    source = tmp_path / "OrderService.java"
    source.write_text(
        "class OrderService {\n  String create() { return customer.trim(); }\n}\n", encoding="utf-8"
    )
    repository = LocalCodeRepository(
        CodeWorkspace(name="java-lab", root=tmp_path, revision="abc123")
    )

    searched = await CodeSearchTool(repository).execute(
        CodeSearchInput(query="customer.trim"), context()
    )
    result = await CodeReadTool(repository).execute(
        CodeReadInput(path="OrderService.java", start_line=1, end_line=3), context()
    )

    assert searched.status is ToolExecutionStatus.SUCCESS
    assert result.status is ToolExecutionStatus.SUCCESS
    assert result.evidence_drafts[0].type == "code_excerpt"
    assert result.evidence_drafts[0].metadata["revision"] == "abc123"
