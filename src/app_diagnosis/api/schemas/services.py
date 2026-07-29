from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app_diagnosis.domain.service_profile import ServiceProfile


class CreateServiceProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    environment: str = Field(default="local", min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=2000)
    code_workspace_path: str | None = Field(default=None, max_length=2000)
    log_directory: str | None = Field(default=None, max_length=2000)
    config_workspace_path: str | None = Field(default=None, max_length=2000)
    health_targets: list[str] = Field(default_factory=list, max_length=20)
    tags: list[str] = Field(default_factory=list, max_length=20)


class ServiceProfileResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    environment: str
    code_workspace_path: str | None
    log_directory: str | None
    config_workspace_path: str | None
    health_targets: list[str]
    tags: list[str]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, service: ServiceProfile) -> "ServiceProfileResponse":
        return cls.model_validate(service, from_attributes=True)
