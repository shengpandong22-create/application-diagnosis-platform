from dataclasses import dataclass

from app_diagnosis.domain.incident.models import IncidentAggregation


@dataclass(frozen=True, slots=True)
class TriggerDecision:
    should_trigger: bool
    reason: str


class DiagnosisTriggerPolicy:
    """只有尚未关联诊断的 Incident 才允许产生一次 Agent 运行。"""

    def decide(self, aggregation: IncidentAggregation) -> TriggerDecision:
        if aggregation.duplicate_event:
            return TriggerDecision(False, "duplicate_source_event")
        if aggregation.incident.diagnosis_id is not None:
            return TriggerDecision(False, "diagnosis_already_linked")
        return TriggerDecision(True, "incident_without_diagnosis")
