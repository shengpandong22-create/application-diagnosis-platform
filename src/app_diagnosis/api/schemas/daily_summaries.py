from datetime import date
from uuid import UUID

from pydantic import BaseModel

from app_diagnosis.application.daily_summaries import DailyServiceSummary


class HighFrequencyIncidentResponse(BaseModel):
    id: UUID
    fingerprint: str
    occurrence_count: int


class DailyServiceSummaryResponse(BaseModel):
    service_id: UUID
    service_name: str
    environment: str
    day: date
    incident_count: int
    new_fingerprint_count: int
    occurrence_count: int
    high_frequency_incidents: list[HighFrequencyIncidentResponse]
    waiting_for_confirmation: int
    rejected: int

    @classmethod
    def from_domain(cls, value: DailyServiceSummary) -> "DailyServiceSummaryResponse":
        return cls(
            service_id=value.service.id,
            service_name=value.service.name,
            environment=value.service.environment,
            day=value.day,
            incident_count=value.incident_count,
            new_fingerprint_count=value.new_fingerprint_count,
            occurrence_count=value.occurrence_count,
            high_frequency_incidents=[
                HighFrequencyIncidentResponse(
                    id=item.id,
                    fingerprint=item.fingerprint,
                    occurrence_count=item.occurrence_count,
                )
                for item in value.high_frequency_incidents
            ],
            waiting_for_confirmation=value.waiting_for_confirmation,
            rejected=value.rejected,
        )
