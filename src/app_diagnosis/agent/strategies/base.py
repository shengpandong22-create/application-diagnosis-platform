from dataclasses import dataclass
from typing import Protocol

from app_diagnosis.domain.diagnosis import DiagnosisCase, ProblemType
from app_diagnosis.ports.llm import ResponseFormat


@dataclass(frozen=True, slots=True)
class DiagnosisStrategyContext:
    diagnosis: DiagnosisCase
    available_tool_names: frozenset[str] = frozenset({"knowledge__search"})


class DiagnosisStrategy(Protocol):
    name: str
    problem_type: ProblemType

    def system_prompt(self, context: DiagnosisStrategyContext) -> str: ...

    def user_message(self, context: DiagnosisStrategyContext) -> str: ...

    def allowed_tool_names(self, context: DiagnosisStrategyContext) -> frozenset[str]: ...

    def response_format(self) -> ResponseFormat: ...
