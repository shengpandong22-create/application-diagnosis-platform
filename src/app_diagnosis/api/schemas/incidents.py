from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app_diagnosis.domain.incident import Incident, IncidentAggregation


class StackFrameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    class_name: str = Field(min_length=1, max_length=500)
    method_name: str = Field(min_length=1, max_length=300)
    file_name: str | None = Field(default=None, max_length=300)
    line_number: int | None = Field(default=None, ge=0)
    is_business_frame: bool = True


class IngestLogEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service_id: UUID
    environment: str = Field(min_length=1, max_length=64)
    occurred_at: datetime
    severity: str = Field(default="ERROR", min_length=1, max_length=32)
    message: str = Field(min_length=1, max_length=64_000)
    exception_type: str = Field(min_length=1, max_length=300)
    stack_frames: list[StackFrameRequest] = Field(default_factory=list, max_length=100)
    source_event_id: str | None = Field(default=None, max_length=300)


class IncidentResponse(BaseModel):
    id: UUID
    service_id: UUID
    environment: str
    fingerprint: str
    fingerprint_version: str
    diagnosis_id: UUID | None
    status: str
    exception_type: str
    sample_message: str
    occurrence_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    window_started_at: datetime
    window_ends_at: datetime
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, incident: Incident) -> "IncidentResponse":
        return cls.model_validate(incident, from_attributes=True)


class IncidentAggregationResponse(BaseModel):
    incident: IncidentResponse
    is_novel: bool
    duplicate_event: bool

    @classmethod
    def from_domain(cls, result: IncidentAggregation) -> "IncidentAggregationResponse":
        return cls(
            incident=IncidentResponse.from_domain(result.incident),
            is_novel=result.is_novel,
            duplicate_event=result.duplicate_event,
        )
