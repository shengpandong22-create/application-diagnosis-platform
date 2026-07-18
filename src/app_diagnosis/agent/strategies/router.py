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
                        r"exception",
                        r"http\s*500",
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
    return tuple(re.compile(item, re.IGNORECASE) for item in expressions)
