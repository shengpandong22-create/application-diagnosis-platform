from app_diagnosis.domain.diagnosis.enums import DiagnosisStatus


class DiagnosisDomainError(ValueError):
    """Base error for a violated diagnosis-domain invariant."""


class InvalidDiagnosisValue(DiagnosisDomainError):
    """Raised when a diagnosis value does not satisfy domain invariants."""


class InvalidDiagnosisStateTransition(DiagnosisDomainError):
    def __init__(self, current: DiagnosisStatus, target: DiagnosisStatus) -> None:
        self.current = current
        self.target = target
        super().__init__(f"cannot transition diagnosis from {current.value} to {target.value}")
