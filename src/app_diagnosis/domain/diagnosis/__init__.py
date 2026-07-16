"""Diagnosis aggregate and its domain types."""

from app_diagnosis.domain.diagnosis.case import DiagnosisCase
from app_diagnosis.domain.diagnosis.enums import (
    AgentTerminationReason,
    DiagnosisStatus,
    FindingStatus,
    ProblemType,
)
from app_diagnosis.domain.diagnosis.errors import (
    DiagnosisDomainError,
    InvalidDiagnosisStateTransition,
    InvalidDiagnosisValue,
)

__all__ = [
    "AgentTerminationReason",
    "DiagnosisCase",
    "DiagnosisDomainError",
    "DiagnosisStatus",
    "FindingStatus",
    "InvalidDiagnosisStateTransition",
    "InvalidDiagnosisValue",
    "ProblemType",
]
