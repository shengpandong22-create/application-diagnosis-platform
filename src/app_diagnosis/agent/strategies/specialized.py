from app_diagnosis.agent.strategies.base import DiagnosisStrategyContext
from app_diagnosis.agent.strategies.generic_application_error import GenericApplicationErrorStrategy


class ApplicationErrorStrategy(GenericApplicationErrorStrategy):
    name = "application_error_v1"

    def system_prompt(self, context: DiagnosisStrategyContext) -> str:
        return super().system_prompt(context) + (
            " Prioritize runtime exception frames, then inspect the smallest relevant source or "
            "configuration excerpt."
        )

    def allowed_tool_names(self, context: DiagnosisStrategyContext) -> frozenset[str]:
        return super().allowed_tool_names(context) - {"health__check"}


class NetworkStrategy(GenericApplicationErrorStrategy):
    name = "network_diagnosis_v1"

    def system_prompt(self, context: DiagnosisStrategyContext) -> str:
        return super().system_prompt(context) + (
            " Prioritize the observed network error, configured endpoint, and preconfigured health "
            "target. Distinguish connection refusal, timeout, and application HTTP error."
        )

    def allowed_tool_names(self, context: DiagnosisStrategyContext) -> frozenset[str]:
        return super().allowed_tool_names(context) - {"code__search", "code__read"}


class ConfigurationStrategy(GenericApplicationErrorStrategy):
    name = "configuration_diagnosis_v1"

    def system_prompt(self, context: DiagnosisStrategyContext) -> str:
        return super().system_prompt(context) + (
            " Prioritize bounded configuration evidence and startup logs. Static configuration "
            "does not prove the final runtime value, and secrets must never be repeated."
        )

    def allowed_tool_names(self, context: DiagnosisStrategyContext) -> frozenset[str]:
        return super().allowed_tool_names(context) - {"code__search", "code__read"}
