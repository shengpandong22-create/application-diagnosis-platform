"""诊断计划领域模型。

Phase 3B 的 Plan 先采用规则生成，不改变 ToolLoopRunner 的执行顺序。
它的价值是解释“系统准备如何调查”，让 Agent 过程更容易被人接手、复盘和展示。
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from app_diagnosis.agent.strategies.base import DiagnosisStrategy
from app_diagnosis.domain.diagnosis import DiagnosisCase


class DiagnosisPlanStatus(StrEnum):
    PLANNED = "planned"


@dataclass(frozen=True, slots=True)
class PlanStep:
    order: int
    title: str
    description: str
    tool_name: str | None
    expected_evidence: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.order <= 0:
            raise ValueError("plan step order must be positive")
        if not self.title.strip():
            raise ValueError("plan step title must not be blank")
        if not self.description.strip():
            raise ValueError("plan step description must not be blank")


@dataclass(frozen=True, slots=True)
class DiagnosisPlan:
    id: UUID
    diagnosis_id: UUID
    agent_run_id: UUID
    summary: str
    hypotheses: tuple[str, ...]
    steps: tuple[PlanStep, ...]
    expected_evidence: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    status: DiagnosisPlanStatus
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.summary.strip():
            raise ValueError("plan summary must not be blank")
        if not self.steps:
            raise ValueError("plan must contain at least one step")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() != UTC.utcoffset(
            self.created_at
        ):
            raise ValueError("plan created_at must be timezone-aware UTC")

    @classmethod
    def create_rule_based(
        cls,
        *,
        diagnosis: DiagnosisCase,
        agent_run_id: UUID,
        strategy: DiagnosisStrategy,
        allowed_tools: frozenset[str],
        plan_id: UUID | None = None,
        now: datetime | None = None,
    ) -> "DiagnosisPlan":
        """按 Strategy 和工具白名单生成稳定可测试的诊断计划。

        第一版 Plan 不额外调用真实模型。它把当前诊断会如何利用用户事实、
        日志、知识库、源码、配置和健康检查表达清楚，帮助 Report/Trace 解释过程。
        """
        occurred_at = now or datetime.now(UTC)
        ordered_tools = tuple(sorted(allowed_tools))
        steps = [
            PlanStep(
                order=1,
                title="整理用户事实与初始日志",
                description="确认 symptom、submitted_log 和已有 Evidence，避免直接采信未脱敏原文。",
                tool_name=None,
                expected_evidence=("user_statement", "log_excerpt"),
            )
        ]
        next_order = 2
        tool_steps = {
            "knowledge__search": (
                "检索本地知识库",
                "查找与异常类型、错误码或症状相似的历史知识条目。",
                ("knowledge_entry",),
            ),
            "log__search": (
                "读取受限日志",
                "在配置的日志目录内提取最近一次相关异常上下文。",
                ("log_excerpt",),
            ),
            "code__search": (
                "搜索受限源码",
                "在授权源码工作区中定位异常类、方法名或关键调用点。",
                ("code_excerpt",),
            ),
            "code__read": (
                "读取关键源码片段",
                "读取搜索命中的源码片段，用日志证据和代码证据共同支撑根因判断。",
                ("code_excerpt",),
            ),
            "config__read": (
                "检查受限配置",
                "读取配置工作区内的配置片段，验证端口、连接串和开关项。",
                ("config_excerpt",),
            ),
            "health__check": (
                "执行健康检查",
                "对配置的本地目标进行健康探测，验证服务或下游是否可达。",
                ("health_check",),
            ),
        }
        for tool_name, (title, description, evidence) in tool_steps.items():
            if tool_name in allowed_tools:
                steps.append(
                    PlanStep(
                        order=next_order,
                        title=title,
                        description=description,
                        tool_name=tool_name,
                        expected_evidence=evidence,
                    )
                )
                next_order += 1
        steps.append(
            PlanStep(
                order=next_order,
                title="综合证据并生成可审核结论",
                description="最终结论必须通过结构化 schema 和 Evidence Citation Policy 校验。",
                tool_name=None,
                expected_evidence=("cited_evidence",),
            )
        )
        return cls(
            id=plan_id or uuid4(),
            diagnosis_id=diagnosis.id,
            agent_run_id=agent_run_id,
            summary=f"使用 {strategy.name} 对诊断进行有界调查，并按证据规则收敛结论。",
            hypotheses=_hypotheses(diagnosis, ordered_tools),
            steps=tuple(steps),
            expected_evidence=tuple(
                sorted({item for step in steps for item in step.expected_evidence})
            ),
            allowed_tools=ordered_tools,
            status=DiagnosisPlanStatus.PLANNED,
            created_at=occurred_at,
        )


def _hypotheses(diagnosis: DiagnosisCase, allowed_tools: tuple[str, ...]) -> tuple[str, ...]:
    values = [
        f"症状可能属于 {diagnosis.problem_type.value} 类型，需要结合用户事实和运行证据判断。",
    ]
    if "code__read" in allowed_tools:
        values.append("如果日志包含明确堆栈，应联合源码片段定位触发点。")
    if "config__read" in allowed_tools or "health__check" in allowed_tools:
        values.append("如果表现为连接失败或超时，应检查配置、健康状态和下游可达性。")
    if "knowledge__search" in allowed_tools:
        values.append("可用知识库结果作为候选方向，但不能单独支撑 probable 根因。")
    return tuple(values)
