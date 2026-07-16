from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app_diagnosis.domain.knowledge import KnowledgeEntry, KnowledgeStatus


class CreateKnowledgeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=4000)
    error_types: list[str] = Field(default_factory=list, max_length=20)
    tags: list[str] = Field(default_factory=list, max_length=30)
    source: str = Field(default="user", min_length=1, max_length=100)


class ChangeKnowledgeStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: KnowledgeStatus


class KnowledgeResponse(BaseModel):
    id: str
    title: str
    summary: str
    error_types: list[str]
    tags: list[str]
    source: str
    status: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, entry: KnowledgeEntry) -> "KnowledgeResponse":
        return cls(
            id=entry.id,
            title=entry.title,
            summary=entry.summary,
            error_types=list(entry.error_types),
            tags=list(entry.tags),
            source=entry.source,
            status=entry.status.value,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
        )
