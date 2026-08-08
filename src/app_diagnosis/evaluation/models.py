from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EvaluationVersionSet(BaseModel):
    """Identifies every version that can materially affect an evaluation result."""

    model_config = ConfigDict(extra="forbid")

    dataset_version: str = Field(default="unspecified", min_length=1, max_length=100)
    model_id: str = Field(default="unspecified", min_length=1, max_length=200)
    prompt_version: str = Field(default="unspecified", min_length=1, max_length=100)
    strategy_version: str = Field(default="unspecified", min_length=1, max_length=100)
    tool_schema_version: str = Field(default="unspecified", min_length=1, max_length=100)
    citation_policy_version: str = Field(default="unspecified", min_length=1, max_length=100)
    code_revision: str = Field(default="unspecified", min_length=1, max_length=100)


class EvaluationObservation(BaseModel):
    """A safe, deterministic snapshot of one completed diagnostic run."""

    model_config = ConfigDict(extra="forbid")

    termination_reason: str
    tool_statuses: list[str] = Field(default_factory=list)
    tool_names: list[str] = Field(default_factory=list)
    evidence: list[dict[str, str]] = Field(default_factory=list)
    conclusion: dict[str, Any] | None = None
    observed_category: str | None = Field(default=None, max_length=100)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    latency_ms: int = Field(default=0, ge=0)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)


class EvaluationCase(BaseModel):
    """Versioned ground truth plus the observation evaluated against it."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    source: str = Field(default="synthetic", min_length=1, max_length=100)
    versions: EvaluationVersionSet = Field(default_factory=EvaluationVersionSet)
    expected_termination_reason: str
    expected_category: str | None = Field(default=None, max_length=100)
    expected_information_sufficient: bool | None = None
    expected_tool_names: list[str] = Field(default_factory=list)
    required_evidence_types: list[str] = Field(default_factory=list)
    required_evidence_ids: list[UUID] = Field(default_factory=list)
    allowed_root_cause_keywords: list[str] = Field(default_factory=list)
    forbidden_root_cause_keywords: list[str] = Field(default_factory=list)
    observation: EvaluationObservation


class EvaluationResult(BaseModel):
    case_id: str
    versions: EvaluationVersionSet
    passed: bool
    structured_output_valid: bool
    citations_valid: bool
    required_evidence_present: bool
    termination_reason_matches: bool
    category_matches: bool | None
    root_cause_matches: bool
    root_cause_top1_matches: bool
    root_cause_top3_matches: bool
    information_sufficiency_matches: bool | None
    tool_selection_matches: bool | None
    citation_precision: float
    citation_recall: float
    unsupported_claim_rate: float
    high_confidence_error: bool
    tool_success_rate: float
    latency_ms: int
    total_tokens: int
    estimated_cost_usd: float
    failures: list[str]


class EvaluationSuite(BaseModel):
    total: int
    passed: int
    pass_rate: float
    dataset_versions: list[str]
    structured_output_valid_rate: float
    citation_valid_rate: float
    required_evidence_rate: float
    termination_reason_match_rate: float
    category_accuracy: float | None
    category_confusion_matrix: dict[str, dict[str, int]]
    root_cause_top1_rate: float
    root_cause_top3_rate: float
    information_sufficiency_accuracy: float | None
    tool_selection_accuracy: float | None
    citation_precision: float
    citation_recall: float
    unsupported_claim_rate: float
    high_confidence_error_rate: float
    tool_success_rate: float
    average_latency_ms: float
    total_tokens: int
    estimated_cost_usd: float
    results: list[EvaluationResult]
