from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvaluationObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    termination_reason: str
    tool_statuses: list[str] = Field(default_factory=list)
    evidence: list[dict[str, str]] = Field(default_factory=list)
    conclusion: dict[str, Any] | None = None


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    expected_termination_reason: str
    required_evidence_types: list[str] = Field(default_factory=list)
    allowed_root_cause_keywords: list[str] = Field(default_factory=list)
    observation: EvaluationObservation


class EvaluationResult(BaseModel):
    case_id: str
    passed: bool
    structured_output_valid: bool
    citations_valid: bool
    required_evidence_present: bool
    termination_reason_matches: bool
    root_cause_matches: bool
    tool_success_rate: float
    failures: list[str]


class EvaluationSuite(BaseModel):
    total: int
    passed: int
    pass_rate: float
    structured_output_valid_rate: float
    citation_valid_rate: float
    tool_success_rate: float
    results: list[EvaluationResult]
