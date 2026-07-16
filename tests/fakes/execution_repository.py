from copy import deepcopy
from uuid import UUID

from app_diagnosis.domain.execution import AgentRun, ToolRun


class InMemoryAgentExecutionRepository:
    def __init__(self) -> None:
        self.agent_runs: dict[UUID, AgentRun] = {}
        self.tool_runs: list[ToolRun] = []

    async def add_agent_run(self, run: AgentRun) -> None:
        self.agent_runs[run.id] = deepcopy(run)

    async def update_agent_run(self, run: AgentRun) -> None:
        self.agent_runs[run.id] = deepcopy(run)

    async def get_agent_run(self, run_id: UUID) -> AgentRun | None:
        run = self.agent_runs.get(run_id)
        return deepcopy(run) if run else None

    async def list_agent_runs(self, diagnosis_id: UUID) -> tuple[AgentRun, ...]:
        runs = (run for run in self.agent_runs.values() if run.diagnosis_id == diagnosis_id)
        return tuple(
            deepcopy(run)
            for run in sorted(
                runs,
                key=lambda item: (item.started_at, str(item.id)),
                reverse=True,
            )
        )

    async def add_tool_run(self, run: ToolRun) -> None:
        self.tool_runs.append(deepcopy(run))

    async def list_tool_runs(self, agent_run_id: UUID) -> tuple[ToolRun, ...]:
        return tuple(deepcopy(run) for run in self.tool_runs if run.agent_run_id == agent_run_id)
