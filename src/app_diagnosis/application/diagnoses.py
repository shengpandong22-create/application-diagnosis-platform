"""诊断用例的确定性编排层。

这个模块站在 API 和 Agent Runtime 之间，负责并发保护、事务边界、
Strategy 选择，以及把 ToolLoopRunner 的结果回写到 DiagnosisCase 状态机。
后续改造时应继续保持这个边界：LLM 可以产生 ToolLoopResult，
但不能直接修改诊断聚合根状态。
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_diagnosis.adapters.code import LocalCodeRepository
from app_diagnosis.adapters.config import LocalConfigRepository
from app_diagnosis.adapters.health import HttpHealthCheckClient
from app_diagnosis.adapters.logs import LocalLogFileReader
from app_diagnosis.adapters.persistence import SqlAlchemyDiagnosisRepository
from app_diagnosis.adapters.persistence.audit_repository import SqlAlchemyAuditRepository
from app_diagnosis.adapters.persistence.service_profile_repository import (
    SqlAlchemyServiceProfileRepository,
)
from app_diagnosis.agent.runtime import AgentBudget, ToolLoopContext, ToolLoopResult, ToolLoopRunner
from app_diagnosis.agent.runtime.models import ToolResourceContext
from app_diagnosis.agent.strategies.base import DiagnosisStrategy
from app_diagnosis.agent.strategies.router import DiagnosisStrategyRouter
from app_diagnosis.domain.audit import AuditEvent
from app_diagnosis.domain.code_workspace import CodeWorkspace
from app_diagnosis.domain.diagnosis import (
    AgentTerminationReason,
    DiagnosisCase,
    DiagnosisStatus,
    InvalidDiagnosisValue,
)
from app_diagnosis.domain.execution import AgentRun, ToolRun
from app_diagnosis.ports.execution_repository import AgentExecutionRepository
from app_diagnosis.ports.redaction import Redactor


class DiagnosisNotFound(LookupError):
    pass


class DiagnosisRunConflict(RuntimeError):
    pass


ToolResourceResolver = Callable[[DiagnosisCase], Awaitable[ToolResourceContext]]


@dataclass(frozen=True, slots=True)
class DiagnosisRunDetails:
    run: AgentRun
    tool_runs: tuple[ToolRun, ...]


def build_service_tool_resource_resolver(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    redactor: Redactor,
    default_code_workspace_name: str,
    default_code_workspace_path: str,
    default_log_directory: str,
    default_config_workspace_path: str,
    default_health_targets: dict[str, str],
) -> ToolResourceResolver:
    """构建“全局默认 + 服务覆盖”的工具资源解析器。

    解析器只根据 Diagnosis 绑定的 ServiceProfile 创建受限 Adapter，不做目录扫描。
    当 Diagnosis 没有关联服务时，继续使用 Settings 中的全局工具资源，保证旧演示链路不被破坏。
    """

    default_resources = _build_tool_resources(
        code_workspace_name=default_code_workspace_name,
        code_workspace_path=default_code_workspace_path,
        log_directory=default_log_directory,
        config_workspace_path=default_config_workspace_path,
        health_targets=default_health_targets,
        redactor=redactor,
    )
    services = SqlAlchemyServiceProfileRepository(session_factory)

    async def resolve(diagnosis: DiagnosisCase) -> ToolResourceContext:
        if diagnosis.service_id is None:
            return default_resources
        service = await services.get(diagnosis.service_id)
        if service is None:
            return default_resources
        return _build_tool_resources(
            code_workspace_name=service.name,
            code_workspace_path=service.code_workspace_path or "",
            log_directory=service.log_directory or "",
            config_workspace_path=service.config_workspace_path or "",
            health_targets=_parse_health_targets(service.health_targets),
            redactor=redactor,
        )

    return resolve


def _build_tool_resources(
    *,
    code_workspace_name: str,
    code_workspace_path: str,
    log_directory: str,
    config_workspace_path: str,
    health_targets: dict[str, str],
    redactor: Redactor,
) -> ToolResourceContext:
    return ToolResourceContext(
        code_repository=(
            LocalCodeRepository(
                CodeWorkspace(
                    name=code_workspace_name,
                    root=Path(code_workspace_path),
                )
            )
            if code_workspace_path.strip()
            else None
        ),
        log_reader=LocalLogFileReader(Path(log_directory)) if log_directory.strip() else None,
        config_repository=(
            LocalConfigRepository(Path(config_workspace_path))
            if config_workspace_path.strip()
            else None
        ),
        health_check_client=(
            HttpHealthCheckClient(health_targets, redactor) if health_targets else None
        ),
    )


def _parse_health_targets(values: tuple[str, ...]) -> dict[str, str]:
    targets: dict[str, str] = {}
    for index, item in enumerate(values, 1):
        if "=" in item:
            name, url = item.split("=", 1)
            targets[name.strip() or f"target_{index}"] = url.strip()
        else:
            targets[f"target_{index}"] = item.strip()
    return {name: url for name, url in targets.items() if url}


class DiagnosisApplicationService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        runner: ToolLoopRunner,
        executions: AgentExecutionRepository,
        strategy: DiagnosisStrategy,
        budget: AgentBudget,
        max_input_log_bytes: int,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        strategy_router: DiagnosisStrategyRouter | None = None,
        tool_resource_resolver: ToolResourceResolver | None = None,
    ) -> None:
        self._sessions = session_factory
        self._runner = runner
        self._executions = executions
        self._strategy = strategy
        self._strategy_router = strategy_router
        self._tool_resource_resolver = tool_resource_resolver
        self._budget = budget
        self._max_input_log_bytes = max_input_log_bytes
        self._clock = clock
        self._active_tasks: dict[UUID, asyncio.Task] = {}
        self._active_lock = asyncio.Lock()

    async def create(
        self,
        *,
        title: str,
        symptom: str,
        submitted_log: str | None,
    ) -> DiagnosisCase:
        """创建诊断聚合根，但不启动 Agent 运行。

        这个基础实现只负责创建 DiagnosisCase。Phase 0B 之后的脱敏和
        初始 Evidence 创建由 EvidenceAwareDiagnosisApplicationService 覆盖。
        """
        if submitted_log and len(submitted_log.encode("utf-8")) > self._max_input_log_bytes:
            raise InvalidDiagnosisValue("submitted_log exceeds configured byte limit")
        diagnosis = DiagnosisCase.create(
            title=title,
            symptom=symptom,
            submitted_log=submitted_log,
            now=self._clock(),
        )
        async with self._sessions.begin() as session:
            await SqlAlchemyDiagnosisRepository(session).add(diagnosis)
        return diagnosis

    async def get(self, diagnosis_id: UUID) -> DiagnosisCase:
        """读取单个诊断，不存在时抛出应用层 NotFound。

        API 层不直接接触 Repository，因此统一通过这里把持久化返回值
        转换成应用层异常，方便全局异常处理返回一致响应。
        """
        async with self._sessions() as session:
            diagnosis = await SqlAlchemyDiagnosisRepository(session).get(diagnosis_id)
        if diagnosis is None:
            raise DiagnosisNotFound(str(diagnosis_id))
        return diagnosis

    async def list_by_service(self, service_id: UUID) -> tuple[DiagnosisCase, ...]:
        """读取某个服务的诊断历史，按创建时间倒序返回。"""
        async with self._sessions() as session:
            return await SqlAlchemyDiagnosisRepository(session).list_by_service(service_id)

    async def run(
        self,
        diagnosis_id: UUID,
        *,
        actor: str,
        environment: str,
        correlation_id: str,
        max_tool_output_bytes: int,
    ) -> ToolLoopResult:
        """启动一次有界诊断运行，并把结果应用回领域状态机。

        这是主调用链的核心入口：先登记当前诊断的活动任务，避免同一个
        Diagnosis 并发运行；再进入 INVESTIGATING；随后选择 Strategy 并调用
        ToolLoopRunner。Runner 返回后，只能通过 _apply_result 推动状态收敛。
        """
        task = asyncio.current_task()
        if task is None:
            raise RuntimeError("diagnosis run requires an asyncio task")
        async with self._active_lock:
            if diagnosis_id in self._active_tasks:
                raise DiagnosisRunConflict("diagnosis already has an active run")
            self._active_tasks[diagnosis_id] = task
        try:
            diagnosis = await self._start_investigation(
                diagnosis_id, actor=actor, correlation_id=correlation_id
            )
            strategy = (
                self._strategy_router.select(diagnosis)
                if self._strategy_router is not None
                else self._strategy
            )
            resources = (
                await self._tool_resource_resolver(diagnosis)
                if self._tool_resource_resolver is not None
                else ToolResourceContext()
            )
            # LLM 运行只拿到 Strategy、权限和预算；它不能直接修改 DiagnosisCase。
            # 这条边界很关键，后续增加更多 Agent 能力时也不应绕过。
            result = await self._runner.run(
                diagnosis=diagnosis,
                strategy=strategy,
                context=ToolLoopContext(
                    actor=actor,
                    environment=environment,
                    audit_correlation_id=correlation_id,
                    permissions=frozenset(
                        {
                            "knowledge:read",
                            "code:read",
                            "config:read",
                            "log:read",
                            "health:read",
                        }
                    ),
                    max_tool_output_bytes=max_tool_output_bytes,
                    resources=resources,
                ),
                budget=self._budget,
            )
            await self._apply_result(diagnosis_id, result)
            return result
        except asyncio.CancelledError:
            await asyncio.shield(self._mark_cancelled(diagnosis_id))
            raise
        finally:
            async with self._active_lock:
                self._active_tasks.pop(diagnosis_id, None)

    async def cancel(self, diagnosis_id: UUID) -> DiagnosisCase:
        """取消正在运行的内存任务，并持久化领域取消状态。

        asyncio.Task.cancel 只负责中断当前进程内的执行；真正对外可见的状态
        仍然要通过 _mark_cancelled 写回 DiagnosisCase。
        """
        async with self._active_lock:
            task = self._active_tasks.get(diagnosis_id)
            if task is not None:
                task.cancel()
        return await self._mark_cancelled(diagnosis_id)

    async def list_runs(self, diagnosis_id: UUID) -> tuple[DiagnosisRunDetails, ...]:
        """查询一次诊断下的 AgentRun 及其 ToolRun 明细。

        这是一条只读链路，用于 Trace 和调试展示，不应该在这里触发
        Agent 继续运行或改变 DiagnosisCase 状态。
        """
        await self.get(diagnosis_id)
        runs = await self._executions.list_agent_runs(diagnosis_id)
        details: list[DiagnosisRunDetails] = []
        for run in runs:
            details.append(
                DiagnosisRunDetails(
                    run=run,
                    tool_runs=await self._executions.list_tool_runs(run.id),
                )
            )
        return tuple(details)

    async def _start_investigation(
        self, diagnosis_id: UUID, *, actor: str, correlation_id: str
    ) -> DiagnosisCase:
        """将诊断推进到 INVESTIGATING，并记录运行开始审计事件。

        只允许 CREATED 或已经 INVESTIGATING 的诊断进入运行流程。
        这里也是运行开始审计的集中位置，避免 API 层和 Runner 分散记录。
        """
        async with self._sessions.begin() as session:
            repository = SqlAlchemyDiagnosisRepository(session)
            diagnosis = await repository.get(diagnosis_id)
            if diagnosis is None:
                raise DiagnosisNotFound(str(diagnosis_id))
            if diagnosis.status not in {
                DiagnosisStatus.CREATED,
                DiagnosisStatus.INVESTIGATING,
            }:
                raise DiagnosisRunConflict(
                    f"diagnosis cannot run from status {diagnosis.status.value}"
                )
            if diagnosis.status is DiagnosisStatus.CREATED:
                expected_version = diagnosis.version
                diagnosis.start_investigation()
                await repository.save(diagnosis, expected_version=expected_version)
            await SqlAlchemyAuditRepository(session).add(
                AuditEvent.create(
                    actor=actor,
                    action="diagnosis.run_started",
                    target_type="diagnosis",
                    target_id=str(diagnosis.id),
                    summary="Diagnosis investigation run started",
                    correlation_id=correlation_id,
                )
            )
            return diagnosis

    async def _apply_result(self, diagnosis_id: UUID, result: ToolLoopResult) -> None:
        """把 ToolLoopResult 转换成 DiagnosisCase 的状态机结果。

        这里是 Agent Runtime 结果进入领域状态的唯一收口。模型完成且有结论时，
        根据 missing_information 决定等待用户补充还是等待人工确认；其他终止原因
        收敛为 INCONCLUSIVE。后续改造时不要让 Runner 直接写状态。
        """
        async with self._sessions.begin() as session:
            repository = SqlAlchemyDiagnosisRepository(session)
            diagnosis = await repository.get(diagnosis_id)
            if diagnosis is None:
                raise DiagnosisNotFound(str(diagnosis_id))
            if diagnosis.status is DiagnosisStatus.CANCELLED:
                return
            expected_version = diagnosis.version
            if (
                result.termination_reason is AgentTerminationReason.COMPLETED
                and result.conclusion is not None
            ):
                conclusion = result.conclusion.model_dump(mode="json")
                diagnosis.record_initial_conclusion(
                    conclusion,
                    needs_input=bool(result.conclusion.missing_information),
                )
            else:
                diagnosis.mark_inconclusive()
            await repository.save(diagnosis, expected_version=expected_version)

    async def _mark_cancelled(self, diagnosis_id: UUID) -> DiagnosisCase:
        """在当前状态允许时持久化取消结果。

        取消不是任意状态都允许。已经终结的诊断不能再被取消，
        这样可以保护人工确认、驳回和 inconclusive 等最终状态不被覆盖。
        """
        async with self._sessions.begin() as session:
            repository = SqlAlchemyDiagnosisRepository(session)
            diagnosis = await repository.get(diagnosis_id)
            if diagnosis is None:
                raise DiagnosisNotFound(str(diagnosis_id))
            if diagnosis.status in {DiagnosisStatus.CREATED, DiagnosisStatus.INVESTIGATING}:
                expected_version = diagnosis.version
                diagnosis.cancel()
                await repository.save(diagnosis, expected_version=expected_version)
            elif diagnosis.status is not DiagnosisStatus.CANCELLED:
                raise DiagnosisRunConflict(
                    f"diagnosis cannot be cancelled from status {diagnosis.status.value}"
                )
            return diagnosis
