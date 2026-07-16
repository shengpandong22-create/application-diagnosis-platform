from pathlib import Path
from uuid import uuid4

from tests.fakes.execution_repository import InMemoryAgentExecutionRepository

from app_diagnosis.adapters.persistence import Database
from app_diagnosis.adapters.persistence.evidence_models import EvidenceRecord  # noqa: F401
from app_diagnosis.adapters.persistence.models import Base
from app_diagnosis.adapters.redaction import LocalRuleRedactor
from app_diagnosis.agent.runtime import AgentBudget, ToolLoopResult
from app_diagnosis.agent.schemas import DiagnosisConclusion
from app_diagnosis.agent.strategies import GenericApplicationErrorStrategy
from app_diagnosis.application import DiagnosisApplicationService
from app_diagnosis.domain.diagnosis import AgentTerminationReason, DiagnosisStatus


class StubRunner:
    def __init__(self, result: ToolLoopResult) -> None:
        self._result = result

    async def run(self, **kwargs) -> ToolLoopResult:
        return self._result


async def test_inconclusive_run_does_not_promote_candidate_conclusion(tmp_path: Path) -> None:
    database_path = tmp_path / "service.db"
    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    database = Database(database_url)
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    conclusion = DiagnosisConclusion(
        symptom_summary="Candidate only",
        facts=[],
        root_causes=[],
        recommendations=[],
        missing_information=[],
    )
    service = DiagnosisApplicationService(
        session_factory=database.session_factory,
        runner=StubRunner(
            ToolLoopResult(
                agent_run_id=uuid4(),
                termination_reason=AgentTerminationReason.INCONCLUSIVE,
                conclusion=conclusion,
            )
        ),  # type: ignore[arg-type]
        executions=InMemoryAgentExecutionRepository(),
        strategy=GenericApplicationErrorStrategy(),
        budget=AgentBudget(),
        max_input_log_bytes=4096,
        redactor=LocalRuleRedactor(),
    )
    try:
        diagnosis = await service.create(title="Failure", symptom="HTTP 500", submitted_log=None)
        await service.run(
            diagnosis.id,
            actor="test",
            environment="test",
            correlation_id="test-1",
            max_tool_output_bytes=4096,
        )
        stored = await service.get(diagnosis.id)
        assert stored.status is DiagnosisStatus.INCONCLUSIVE
        assert stored.conclusion is None
    finally:
        await database.dispose()
