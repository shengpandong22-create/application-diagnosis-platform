from enum import StrEnum


class ProblemType(StrEnum):
    GENERIC_APPLICATION_ERROR = "generic_application_error"


class DiagnosisStatus(StrEnum):
    CREATED = "created"
    INVESTIGATING = "investigating"
    WAITING_FOR_INPUT = "waiting_for_input"
    WAITING_FOR_CONFIRMATION = "waiting_for_confirmation"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in {
            DiagnosisStatus.CONFIRMED,
            DiagnosisStatus.REJECTED,
            DiagnosisStatus.INCONCLUSIVE,
            DiagnosisStatus.CANCELLED,
        }


class FindingStatus(StrEnum):
    CONFIRMED = "confirmed"
    PROBABLE = "probable"
    POSSIBLE = "possible"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class AgentTerminationReason(StrEnum):
    COMPLETED = "completed"
    WAITING_FOR_INPUT = "waiting_for_input"
    INCONCLUSIVE = "inconclusive"
    MAX_ROUNDS_REACHED = "max_rounds_reached"
    TOOL_BUDGET_EXHAUSTED = "tool_budget_exhausted"
    TIME_BUDGET_EXHAUSTED = "time_budget_exhausted"
    CANCELLED = "cancelled"
    MODEL_ERROR = "model_error"
    INTERNAL_ERROR = "internal_error"
