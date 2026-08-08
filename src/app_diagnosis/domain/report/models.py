from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app_diagnosis.agent.schemas import DiagnosisConclusion
from app_diagnosis.domain.confirmation import Confirmation
from app_diagnosis.domain.diagnosis import DiagnosisCase
from app_diagnosis.domain.diagnosis_plan import DiagnosisPlan
from app_diagnosis.domain.evidence import Evidence
from app_diagnosis.domain.incident import Incident
from app_diagnosis.domain.service_profile import ServiceProfile


@dataclass(frozen=True, slots=True)
class ReportRun:
    id: UUID
    status: str
    termination_reason: str | None
    model: str | None
    round_count: int
    tool_call_count: int
    started_at: datetime
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class DiagnosisReport:
    diagnosis: DiagnosisCase
    service: ServiceProfile | None
    incident: Incident | None
    conclusion: DiagnosisConclusion | None
    evidence: tuple[Evidence, ...]
    plans: tuple[DiagnosisPlan, ...]
    runs: tuple[ReportRun, ...]
    confirmations: tuple[Confirmation, ...]
    generated_at: datetime

    def __post_init__(self) -> None:
        if any(item.diagnosis_id != self.diagnosis.id for item in self.evidence):
            raise ValueError("report evidence must belong to the diagnosis")
        if any(item.diagnosis_id != self.diagnosis.id for item in self.plans):
            raise ValueError("report plans must belong to the diagnosis")
        if self.conclusion:
            available = {item.id for item in self.evidence}
            cited = {
                item
                for finding in [*self.conclusion.facts, *self.conclusion.root_causes]
                for item in finding.evidence_ids
            }
            if not cited <= available:
                raise ValueError("report conclusion contains foreign evidence IDs")
