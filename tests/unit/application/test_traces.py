from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app_diagnosis.application.traces import _events
from app_diagnosis.domain.diagnosis import AgentTerminationReason
from app_diagnosis.domain.execution import AgentRun, ToolRun, ToolRunStatus


def test_trace_events_include_tool_evidence_ids_without_guessing() -> None:
    started = datetime(2026, 7, 18, 8, 0, tzinfo=UTC)
    evidence_id = uuid4()
    run = AgentRun.start(diagnosis_id=uuid4(), strategy="test", now=started)
    run.finish(AgentTerminationReason.COMPLETED, now=started + timedelta(seconds=2))
    tool = ToolRun(
        id=uuid4(),
        agent_run_id=run.id,
        tool_call_id="call-1",
        tool_name="config__read",
        arguments_json={"path": "application.yml"},
        status=ToolRunStatus.SUCCESS,
        result_json={"content": "safe", "evidence_ids": [str(evidence_id), "invalid"]},
        duration_ms=50,
        error_code=None,
        created_at=started + timedelta(seconds=1),
    )

    events = _events(run, (tool,))

    assert [item.type.value for item in events] == [
        "run_started",
        "tool_call",
        "run_finished",
    ]
    assert events[1].evidence_ids == (evidence_id,)


def test_historical_tool_without_evidence_link_returns_empty_ids() -> None:
    started = datetime(2026, 7, 18, 8, 0, tzinfo=UTC)
    run = AgentRun.start(diagnosis_id=uuid4(), strategy="test", now=started)
    tool = ToolRun(
        id=uuid4(),
        agent_run_id=run.id,
        tool_call_id="legacy",
        tool_name="knowledge__search",
        arguments_json=None,
        status=ToolRunStatus.SUCCESS,
        result_json={"matches": []},
        duration_ms=1,
        error_code=None,
        created_at=started,
    )
    assert _events(run, (tool,))[1].evidence_ids == ()
