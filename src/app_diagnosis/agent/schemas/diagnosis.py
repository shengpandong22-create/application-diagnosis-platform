from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DiagnosisFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement: str = Field(min_length=1, max_length=2000)
    status: Literal["confirmed", "probable", "possible", "insufficient_evidence"]
    evidence_ids: list[UUID] = Field(default_factory=list)


class DiagnosisConclusion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symptom_summary: str = Field(min_length=1, max_length=4000)
    facts: list[DiagnosisFinding] = Field(default_factory=list, max_length=30)
    root_causes: list[DiagnosisFinding] = Field(default_factory=list, max_length=10)
    recommendations: list[str] = Field(default_factory=list, max_length=20)
    missing_information: list[str] = Field(default_factory=list, max_length=20)
