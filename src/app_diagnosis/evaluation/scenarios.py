from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvaluationScenario(BaseModel):
    """Input and ground truth used to produce, but not impersonate, a model observation."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=100)
    base_case_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    source: str = Field(default="java-lab", min_length=1, max_length=100)
    trigger_path: str = Field(pattern=r"^/lab/")
    keyword: str = Field(min_length=1, max_length=200)
    symptom: str = Field(min_length=1, max_length=2000)
    expected_category: str = Field(min_length=1, max_length=100)
    expected_context_depth: str = Field(min_length=1, max_length=100)
    expected_code_paths: list[str] = Field(min_length=1)
    required_evidence_types: list[str] = Field(min_length=1)
    expected_tool_names: list[str] = Field(min_length=1)
    allowed_root_cause_keywords: list[str] = Field(min_length=1)
    forbidden_root_cause_keywords: list[str] = Field(default_factory=list)


class EvaluationScenarioDataset(BaseModel):
    """Versioned definitions kept separate from generated observations and scores."""

    model_config = ConfigDict(extra="forbid")

    dataset_version: str = Field(min_length=1, max_length=100)
    annotation_policy: dict[str, str]
    scenarios: list[EvaluationScenario] = Field(min_length=1)

    @model_validator(mode="after")
    def scenario_ids_are_unique(self) -> "EvaluationScenarioDataset":
        ids = [item.id for item in self.scenarios]
        if len(ids) != len(set(ids)):
            raise ValueError("scenario ids must be unique")
        return self
