from pydantic import BaseModel

from app_diagnosis.api.schemas.incidents import IncidentResponse
from app_diagnosis.application.discovery import DiscoveryResult


class DiscoveryResponse(BaseModel):
    incident: IncidentResponse
    diagnosis_id: str | None
    triggered: bool
    trigger_reason: str
    termination_reason: str | None
    error_code: str | None

    @classmethod
    def from_domain(cls, result: DiscoveryResult) -> "DiscoveryResponse":
        return cls(
            incident=IncidentResponse.from_domain(result.incident),
            diagnosis_id=str(result.diagnosis_id) if result.diagnosis_id else None,
            triggered=result.triggered,
            trigger_reason=result.trigger_reason,
            termination_reason=result.termination_reason,
            error_code=result.error_code,
        )
