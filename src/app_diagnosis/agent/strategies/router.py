"""诊断运行开始前的确定性 Strategy 路由。

Router 根据 title、symptom、submitted_log 中的关键词选择 Strategy。
它不调用 LLM，也不执行工具，只决定后续 ToolLoopRunner 使用哪套 prompt
和工具白名单。信号缺失或多条路线打平时会回退到 fallback，避免不确定路由。
"""

import re
from dataclasses import dataclass

from app_diagnosis.agent.strategies.base import DiagnosisStrategy
from app_diagnosis.domain.diagnosis import DiagnosisCase


@dataclass(frozen=True, slots=True)
class _Route:
    strategy: DiagnosisStrategy
    patterns: tuple[re.Pattern[str], ...]


class DiagnosisStrategyRouter:
    def __init__(
        self,
        *,
        application: DiagnosisStrategy,
        network: DiagnosisStrategy,
        configuration: DiagnosisStrategy,
        fallback: DiagnosisStrategy,
    ) -> None:
        self._routes = (
            _Route(
                application,
                _patterns(
                    (
                        r"nullpointerexception",
                        r"\bnpe\b",
                        r"stack\s*trace",
                    )
                ),
            ),
            _Route(
                network,
                _patterns(
                    (
                        r"connection\s*refused",
                        r"connectexception",
                    r"connect\s*timeout",
                    r"sockettimeout",
                    r"timeoutexception",
                    r"timeout",
                        r"unknownhost",
                        r"\bdns\b",
                        r"下游.*超时",
                        r"连接拒绝",
                    )
                ),
            ),
            _Route(
                configuration,
                _patterns(
                    (
                        r"missing\s+(?:property|configuration)",
                        r"missing\s+required\s+configuration",
                        r"invalid\s+(?:property|config)",
                        r"could\s+not\s+resolve\s+placeholder",
                        r"configuration\s+error",
                        r"配置缺失",
                        r"配置错误",
                        r"启动配置",
                    )
                ),
            ),
        )
        self._fallback = fallback

    def select(self, diagnosis: DiagnosisCase) -> DiagnosisStrategy:
        """选择唯一 Strategy；没有明确胜者时使用 fallback。

        当前实现是规则路由，优点是稳定、便宜、可测试。后续如果引入 LLM 分类，
        也建议保留“规则优先，低置信度再问模型”的边界。
        """
        text = "\n".join(
            part for part in (diagnosis.title, diagnosis.symptom, diagnosis.submitted_log) if part
        ).casefold()
        scores = [
            sum(bool(pattern.search(text)) for pattern in route.patterns) for route in self._routes
        ]
        highest = max(scores, default=0)
        if highest == 0 or scores.count(highest) != 1:
            return self._fallback
        return self._routes[scores.index(highest)].strategy


def _patterns(expressions: tuple[str, ...]) -> tuple[re.Pattern[str], ...]:
    """把关键词表达式编译为大小写不敏感的正则模式。"""
    return tuple(re.compile(item, re.IGNORECASE) for item in expressions)
