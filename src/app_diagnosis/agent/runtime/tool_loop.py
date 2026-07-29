"""有界 tool-calling 诊断 Agent Runtime。

ToolLoopRunner 是概率性模型输出和确定性工程约束相遇的地方。
它负责多轮 LLM 调用、工具白名单、预算、工具契约、Evidence 落库、
引用校验和 AgentRun/ToolRun 持久化。后续扩展规划、记忆或新工具时，
优先保持这里“模型提议，系统校验后执行”的边界。
"""

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from time import perf_counter
from uuid import UUID, uuid4

from pydantic import ValidationError

from app_diagnosis.agent.policies import EvidenceCitationPolicy
from app_diagnosis.agent.runtime.models import AgentBudget, ToolLoopContext, ToolLoopResult
from app_diagnosis.agent.schemas.diagnosis import DiagnosisConclusion
from app_diagnosis.agent.strategies.base import DiagnosisStrategy, DiagnosisStrategyContext
from app_diagnosis.domain.diagnosis import (
    AgentTerminationReason,
    DiagnosisCase,
    DiagnosisStatus,
)
from app_diagnosis.domain.diagnosis_plan import DiagnosisPlan
from app_diagnosis.domain.execution import AgentRun, ToolRun, ToolRunStatus
from app_diagnosis.ports.diagnosis_plan_repository import DiagnosisPlanRepository
from app_diagnosis.ports.evidence_store import EvidenceCandidate, EvidenceStore
from app_diagnosis.ports.execution_repository import AgentExecutionRepository
from app_diagnosis.ports.llm import (
    ChatMessage,
    FinishReason,
    LLMCallOptions,
    LLMClient,
    LLMError,
    LLMRequest,
)
from app_diagnosis.tools import (
    DiagnosticToolRegistry,
    ToolExecutionContext,
    ToolExecutionResult,
    ToolExecutionStatus,
)
from app_diagnosis.tools.errors import ToolRegistryError


class ToolLoopRunner:
    def __init__(
        self,
        *,
        llm_client: LLMClient,
        registry: DiagnosticToolRegistry,
        execution_repository: AgentExecutionRepository,
        evidence_store: EvidenceStore | None = None,
        citation_policy: EvidenceCitationPolicy | None = None,
        plan_repository: DiagnosisPlanRepository | None = None,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._llm = llm_client
        self._registry = registry
        self._executions = execution_repository
        self._evidence = evidence_store
        self._citation_policy = citation_policy
        self._plans = plan_repository
        self._id_factory = id_factory
        self._clock = clock

    async def run(
        self,
        *,
        diagnosis: DiagnosisCase,
        strategy: DiagnosisStrategy,
        context: ToolLoopContext,
        budget: AgentBudget,
    ) -> ToolLoopResult:
        """执行一次有界 Agent Loop，直到完成、等待输入或受控停止。

        这个方法不直接修改 DiagnosisCase 状态，只返回 ToolLoopResult。
        它的职责是把模型输出限制在 Strategy、Registry、预算和 Evidence 规则内，
        并把每次模型响应和工具调用记录为可追溯的运行轨迹。
        """
        if diagnosis.status is not DiagnosisStatus.INVESTIGATING:
            raise ValueError("diagnosis must be investigating before starting an agent run")
        if diagnosis.problem_type is not strategy.problem_type:
            raise ValueError("diagnosis problem type does not match strategy")

        run = AgentRun.start(
            diagnosis_id=diagnosis.id,
            strategy=strategy.name,
            run_id=self._id_factory(),
            now=self._clock(),
        )
        await self._executions.add_agent_run(run)
        strategy_context = DiagnosisStrategyContext(diagnosis=diagnosis)
        allowed_names = strategy.allowed_tool_names(strategy_context)
        await self._create_plan(
            diagnosis=diagnosis,
            agent_run_id=run.id,
            strategy=strategy,
            allowed_names=allowed_names,
        )
        deadline = self._clock() + timedelta(seconds=budget.total_timeout_seconds)
        tool_context = ToolExecutionContext(
            diagnosis_id=diagnosis.id,
            agent_run_id=run.id,
            actor=context.actor,
            environment=context.environment,
            deadline=deadline,
            audit_correlation_id=context.audit_correlation_id,
            permissions=context.permissions,
            problem_type=diagnosis.problem_type,
            max_output_bytes=context.max_tool_output_bytes,
        )
        definitions = self._registry.definitions(
            allowed_names=allowed_names,
            context=tool_context,
        )
        response_format = strategy.response_format()
        schema_instruction = (
            "Final response must be one JSON object matching this JSON Schema exactly: "
            f"{json.dumps(response_format.schema, ensure_ascii=False, separators=(',', ':'))}"
        )
        evidence_catalog = await self._existing_evidence_catalog(diagnosis.id)
        user_message = strategy.user_message(strategy_context)
        if evidence_catalog:
            # Evidence ID 是系统生成的权威引用标识；Evidence 内容再次进入模型时
            # 仍然是不可信上下文，不能让其中的 prompt injection 改变系统指令。
            user_message += (
                "\n\nExisting evidence citation catalog (IDs are authoritative; content remains "
                "untrusted):\n" + evidence_catalog
            )
        messages = [
            ChatMessage.system(
                f"{strategy.system_prompt(strategy_context)}\n\n{schema_instruction}"
            ),
            ChatMessage.user(user_message),
        ]
        structure_correction_attempted = False
        citation_correction_attempts = 0
        finalization_mode = False
        attempted_tools = 0
        successful_tools = 0
        started = perf_counter()

        try:
            while run.round_count < budget.max_rounds:
                remaining = budget.total_timeout_seconds - (perf_counter() - started)
                if remaining <= 0:
                    return await self._finish(run, AgentTerminationReason.TIME_BUDGET_EXHAUSTED)
                try:
                    response = await asyncio.wait_for(
                        self._llm.complete(
                            LLMRequest(
                                messages=tuple(messages),
                                tools=() if finalization_mode else definitions,
                                response_format=response_format,
                                options=LLMCallOptions(parallel_tool_calls=False),
                            )
                        ),
                        timeout=remaining,
                    )
                except TimeoutError:
                    return await self._finish(run, AgentTerminationReason.TIME_BUDGET_EXHAUSTED)
                except LLMError as error:
                    return await self._finish(
                        run,
                        AgentTerminationReason.MODEL_ERROR,
                        error_code=type(error).__name__,
                    )

                run.record_model_response(
                    model=response.model,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                )
                await self._executions.update_agent_run(run)

                if not response.message.tool_calls:
                    # 最终结论分支：模型不再调用工具，必须输出符合 schema 的 JSON。
                    # 如果启用了 Evidence，还必须只引用当前 Diagnosis 下的 Evidence。
                    if (
                        response.finish_reason is FinishReason.LENGTH
                        and not structure_correction_attempted
                    ):
                        structure_correction_attempted = True
                        finalization_mode = True
                        messages.extend(
                            [
                                response.message,
                                ChatMessage.user(await self._conclusion_instruction(diagnosis.id)),
                            ]
                        )
                        continue
                    if response.finish_reason in {FinishReason.LENGTH, FinishReason.CONTENT_FILTER}:
                        return await self._finish(
                            run,
                            AgentTerminationReason.INCONCLUSIVE,
                            error_code=f"model_finish_{response.finish_reason.value}",
                        )
                    conclusion = self._parse_conclusion(response.message.content)
                    if conclusion is None and not structure_correction_attempted:
                        structure_correction_attempted = True
                        finalization_mode = True
                        messages.extend(
                            [
                                response.message,
                                ChatMessage.user(
                                    "The previous response did not match the required JSON schema. "
                                    + await self._conclusion_instruction(diagnosis.id)
                                    + " "
                                    f"{schema_instruction}"
                                ),
                            ]
                        )
                        continue
                    if conclusion is None:
                        return await self._finish(
                            run,
                            AgentTerminationReason.INCONCLUSIVE,
                            error_code="invalid_structured_output",
                        )
                    citation_errors = await self._validate_citations(diagnosis.id, conclusion)
                    if citation_errors and citation_correction_attempts < 2:
                        citation_correction_attempts += 1
                        finalization_mode = True
                        messages.extend(
                            [
                                response.message,
                                ChatMessage.user(
                                    await self._citation_correction_instruction(
                                        diagnosis.id,
                                        citation_errors,
                                    )
                                ),
                            ]
                        )
                        continue
                    if citation_errors:
                        return await self._finish(
                            run,
                            AgentTerminationReason.INCONCLUSIVE,
                            error_code="invalid_evidence_citations",
                        )
                    if attempted_tools > 0 and successful_tools == 0:
                        return await self._finish(
                            run,
                            AgentTerminationReason.INCONCLUSIVE,
                            conclusion=conclusion,
                            error_code="all_tools_failed",
                        )
                    return await self._finish(
                        run,
                        AgentTerminationReason.COMPLETED,
                        conclusion=conclusion,
                    )

                messages.append(response.message)
                calls = response.message.tool_calls
                if finalization_mode:
                    return await self._finish(
                        run,
                        AgentTerminationReason.INCONCLUSIVE,
                        error_code="tool_call_after_finalization",
                    )
                if run.tool_call_count + len(calls) > budget.max_tool_calls:
                    return await self._finish(run, AgentTerminationReason.TOOL_BUDGET_EXHAUSTED)
                run.record_tool_calls(len(calls))
                await self._executions.update_agent_run(run)
                attempted_tools += len(calls)
                should_finalize = False

                for call in calls:
                    # 工具调用分支：模型只能提出调用意图；Registry 和 Tool Contract
                    # 决定这个调用能否被解析、授权、限时执行。
                    result, arguments = await self._execute_tool(
                        call_name=call.name,
                        arguments_json=call.arguments_json,
                        allowed_names=allowed_names,
                        context=tool_context,
                        remaining_seconds=budget.total_timeout_seconds - (perf_counter() - started),
                    )
                    if result.status is ToolExecutionStatus.SUCCESS:
                        successful_tools += 1
                        if call.name == "code__read":
                            should_finalize = True
                    evidence_ids = await self._persist_evidence(diagnosis.id, result)
                    await self._record_tool_run(
                        run_id=run.id,
                        tool_call_id=call.id,
                        tool_name=call.name,
                        arguments=arguments,
                        result=result,
                        evidence_ids=evidence_ids,
                    )
                    tool_message = self._tool_message(result.model_summary, evidence_ids)
                    messages.append(ChatMessage.tool(tool_message, tool_call_id=call.id))

                if should_finalize:
                    finalization_mode = True
                    messages.append(
                        ChatMessage.user(await self._conclusion_instruction(diagnosis.id))
                    )

            return await self._finish(run, AgentTerminationReason.MAX_ROUNDS_REACHED)
        except asyncio.CancelledError:
            await self._finish(run, AgentTerminationReason.CANCELLED)
            raise
        except Exception as error:
            return await self._finish(
                run,
                AgentTerminationReason.INTERNAL_ERROR,
                error_code=type(error).__name__,
            )

    async def _execute_tool(
        self,
        *,
        call_name: str,
        arguments_json: str,
        allowed_names: frozenset[str],
        context: ToolExecutionContext,
        remaining_seconds: float,
    ) -> tuple[ToolExecutionResult, dict | None]:
        """解析、校验并限时执行一次模型请求的工具调用。

        工具名不存在、不在白名单、缺少权限或参数不合法时，都不会真正执行工具。
        这些失败会变成 ToolExecutionResult 返回给上层记录，而不是抛到循环外。
        """
        try:
            tool = self._registry.resolve(
                call_name,
                allowed_names=allowed_names,
                context=context,
            )
            arguments = self._registry.parse_arguments(tool, arguments_json)
        except ToolRegistryError as error:
            return (
                ToolExecutionResult(
                    status=ToolExecutionStatus.FAILED,
                    data=None,
                    model_summary=json.dumps(
                        {"ok": False, "error": type(error).__name__},
                        separators=(",", ":"),
                    ),
                    error_code=type(error).__name__,
                ),
                None,
            )
        timeout = min(tool.timeout_seconds, max(0, remaining_seconds))
        if timeout <= 0:
            return (
                ToolExecutionResult(
                    status=ToolExecutionStatus.TIMEOUT,
                    data=None,
                    model_summary='{"ok":false,"error":"tool_timeout"}',
                    error_code="tool_timeout",
                ),
                arguments.model_dump(mode="json"),
            )
        try:
            result = await asyncio.wait_for(tool.execute(arguments, context), timeout=timeout)
        except TimeoutError:
            result = ToolExecutionResult(
                status=ToolExecutionStatus.TIMEOUT,
                data=None,
                model_summary='{"ok":false,"error":"tool_timeout"}',
                error_code="tool_timeout",
            )
        return result, arguments.model_dump(mode="json")

    async def _create_plan(
        self,
        *,
        diagnosis: DiagnosisCase,
        agent_run_id: UUID,
        strategy: DiagnosisStrategy,
        allowed_names: frozenset[str],
    ) -> None:
        """为本次 AgentRun 创建规则版 DiagnosisPlan。

        Plan 是解释性资产，不参与工具调度决策。这里把它放在 AgentRun 创建之后，
        是为了让 Plan 能准确关联到本次运行，同时不改变后续 LLM 循环行为。
        """
        if self._plans is None:
            return
        plan = DiagnosisPlan.create_rule_based(
            diagnosis=diagnosis,
            agent_run_id=agent_run_id,
            strategy=strategy,
            allowed_tools=allowed_names,
            plan_id=self._id_factory(),
            now=self._clock(),
        )
        await self._plans.add(plan)

    async def _record_tool_run(
        self,
        *,
        run_id: UUID,
        tool_call_id: str,
        tool_name: str,
        arguments: dict | None,
        result: ToolExecutionResult,
        evidence_ids: tuple[UUID, ...],
    ) -> None:
        """持久化一次工具调用尝试，包括失败和关联 Evidence ID。

        ToolRun 是 Trace 的基础。即使工具失败，也应记录工具名、参数解析结果、
        错误码和耗时，方便之后复盘模型是否选错工具或参数。
        """
        status = ToolRunStatus(result.status.value)
        await self._executions.add_tool_run(
            ToolRun(
                id=self._id_factory(),
                agent_run_id=run_id,
                tool_call_id=tool_call_id[:200],
                tool_name=tool_name[:64],
                arguments_json=arguments,
                status=status,
                result_json=(
                    {
                        **result.data.model_dump(mode="json"),
                        "evidence_ids": [str(item) for item in evidence_ids],
                    }
                    if result.data
                    else None
                ),
                duration_ms=result.duration_ms,
                error_code=result.error_code,
                created_at=self._clock(),
            )
        )

    async def _persist_evidence(
        self, diagnosis_id: UUID, result: ToolExecutionResult
    ) -> tuple[UUID, ...]:
        """落库工具产生的 EvidenceDraft，并返回正式 Evidence ID。

        模型不能自己发明 Evidence ID。只有工具结果经过 EvidenceStore 持久化后，
        才会拿到可用于最终结论引用的权威 ID。
        """
        if self._evidence is None or not result.evidence_drafts:
            return ()
        candidates = tuple(
            EvidenceCandidate(
                type=item.type,
                source=item.source,
                source_reference=item.source_reference,
                content=item.content,
                metadata=item.metadata,
            )
            for item in result.evidence_drafts
        )
        stored = await self._evidence.add_candidates(diagnosis_id, candidates)
        return tuple(item.id for item in stored)

    async def _validate_citations(
        self, diagnosis_id: UUID, conclusion: DiagnosisConclusion
    ) -> tuple[str, ...]:
        """校验最终结论只能引用当前诊断下真实存在的 Evidence。

        这里是防止模型伪造引用、跨诊断引用或把知识条目当作直接事实的关键防线。
        返回错误文本而不是直接抛异常，是为了允许有限次数的模型修正。
        """
        if self._evidence is None or self._citation_policy is None:
            return ()
        evidence = await self._evidence.list_by_diagnosis(diagnosis_id)
        violations = self._citation_policy.validate(conclusion, evidence)
        return tuple(item.message for item in violations)

    async def _existing_evidence_catalog(self, diagnosis_id: UUID) -> str:
        """构造发送给模型的紧凑 Evidence 目录。

        目录只包含 ID、类型、来源引用和可信度，不把完整内容重复塞给模型。
        这样既能指导模型引用，也能控制上下文长度和敏感信息暴露面。
        """
        if self._evidence is None:
            return ""
        evidence = await self._evidence.list_by_diagnosis(diagnosis_id)
        if not evidence:
            return ""
        return json.dumps(
            [
                {
                    "id": str(item.id),
                    "type": item.type.value,
                    "source_reference": item.source_reference,
                    "reliability": item.reliability.value,
                }
                for item in evidence
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )

    @staticmethod
    def _tool_message(summary: str, evidence_ids: tuple[UUID, ...]) -> str:
        """把工具结果和正式 Evidence ID 一起反馈给下一轮模型。

        如果工具没有产生 Evidence，就保持原始摘要；如果产生了 Evidence，
        则显式告诉模型后续结论应引用这些 ID。
        """
        if not evidence_ids:
            return summary
        try:
            tool_result = json.loads(summary)
        except json.JSONDecodeError:
            tool_result = summary
        return json.dumps(
            {
                "tool_result": tool_result,
                "evidence_ids": [str(item) for item in evidence_ids],
                "citation_instruction": "Cite these IDs for claims supported by this result.",
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )

    async def _conclusion_instruction(self, diagnosis_id: UUID) -> str:
        """要求模型停止调用工具并输出最终 JSON 结论。

        进入 finalization_mode 后，Runner 不再把工具定义暴露给模型。
        这个提示词负责压缩最终输出规模，并要求源码诊断同时引用日志和代码 Evidence。
        """
        instruction = (
            "Tool investigation is complete. Do not call more tools. Return only the final JSON "
            "object: at most 2 facts, 1 root cause, 3 recommendations, and 2 missing-information "
            "items. Keep every string under 300 characters. Cite the supplied runtime-log and "
            "code Evidence IDs for a source-based root cause."
        )
        evidence_catalog = await self._existing_evidence_catalog(diagnosis_id)
        if evidence_catalog:
            instruction += (
                "\n\nCurrent authoritative Evidence catalog for citation:\n" + evidence_catalog
            )
        return instruction

    async def _citation_correction_instruction(
        self,
        diagnosis_id: UUID,
        citation_errors: tuple[str, ...],
    ) -> str:
        """当引用校验失败时，请求模型进行有限次数的结构化修正。

        这里不是无限重试。调用方会限制修正次数，避免模型在错误引用上反复消耗预算。
        """
        instruction = await self._conclusion_instruction(diagnosis_id)
        return (
            "The conclusion violated evidence citation rules: "
            + "; ".join(citation_errors)
            + ". Return a corrected final JSON object only. Every fact must cite at least one "
            "Evidence ID. A probable root cause must cite user_statement or log_excerpt evidence; "
            "for source-based diagnosis, cite both the runtime log_excerpt ID and the relevant "
            "code_excerpt ID in the same root cause when both are available.\n\n" + instruction
        )

    async def _finish(
        self,
        run: AgentRun,
        reason: AgentTerminationReason,
        *,
        conclusion: DiagnosisConclusion | None = None,
        error_code: str | None = None,
    ) -> ToolLoopResult:
        """结束 AgentRun 并返回不可变的 ToolLoopResult。

        这个方法只负责运行记录和返回值，不负责修改 DiagnosisCase。
        状态收敛统一交给 ApplicationService._apply_result。
        """
        run.finish(reason, now=self._clock(), error_code=error_code)
        await self._executions.update_agent_run(run)
        return ToolLoopResult(
            agent_run_id=run.id,
            termination_reason=reason,
            conclusion=conclusion,
        )

    @staticmethod
    def _parse_conclusion(content: str | None) -> DiagnosisConclusion | None:
        """解析模型最终 JSON，失败时返回 None 进入受控修正或降级。

        这里不直接抛 ValidationError，是为了让主循环可以决定是否给模型一次
        schema 修正机会，或者收敛为 INCONCLUSIVE。
        """
        if content is None:
            return None
        try:
            return DiagnosisConclusion.model_validate_json(content)
        except ValidationError:
            return None
