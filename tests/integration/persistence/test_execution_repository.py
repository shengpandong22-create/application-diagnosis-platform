from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from app_diagnosis.adapters.persistence import (
    Database,
    SqlAlchemyAgentExecutionRepository,
    SqlAlchemyDiagnosisRepository,
)
from app_diagnosis.adapters.persistence.models import Base
from app_diagnosis.domain.diagnosis import AgentTerminationReason, DiagnosisCase
from app_diagnosis.domain.execution import AgentRun, ToolRun, ToolRunStatus

NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
DIAGNOSIS_ID = UUID("22222222-2222-2222-2222-222222222222")
RUN_ID = UUID("55555555-5555-5555-5555-555555555555")


@pytest.fixture
async def database(tmp_path: Path) -> Database:
    database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'execution.db').as_posix()}")
    await database.start()
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with database.session_factory.begin() as session:
        await SqlAlchemyDiagnosisRepository(session).add(
            DiagnosisCase.create(
                diagnosis_id=DIAGNOSIS_ID,
                title="Failure",
                symptom="HTTP 500",
                now=NOW,
            )
        )
    try:
        yield database
    finally:
        await database.dispose()


async def test_agent_and_tool_runs_round_trip(database: Database) -> None:
    repository = SqlAlchemyAgentExecutionRepository(database.session_factory)
    run = AgentRun.start(
        diagnosis_id=DIAGNOSIS_ID,
        strategy="generic_v1",
        run_id=RUN_ID,
        now=NOW,
    )
    await repository.add_agent_run(run)
    run.record_model_response(model="fake-model", input_tokens=10, output_tokens=5)
    run.record_tool_calls(1)
    await repository.update_agent_run(run)
    tool_run = ToolRun(
        id=UUID("66666666-6666-6666-6666-666666666666"),
        agent_run_id=RUN_ID,
        tool_call_id="call-1",
        tool_name="knowledge__search",
        arguments_json={"query": "NPE", "limit": 5},
        status=ToolRunStatus.SUCCESS,
        result_json={"matches": []},
        duration_ms=12,
        error_code=None,
        created_at=NOW,
    )
    await repository.add_tool_run(tool_run)
    run.finish(AgentTerminationReason.COMPLETED, now=NOW)
    await repository.update_agent_run(run)

    loaded = await repository.get_agent_run(RUN_ID)
    tools = await repository.list_tool_runs(RUN_ID)

    assert loaded is not None
    assert loaded.termination_reason is AgentTerminationReason.COMPLETED
    assert loaded.round_count == 1
    assert loaded.tool_call_count == 1
    assert tools == (tool_run,)
