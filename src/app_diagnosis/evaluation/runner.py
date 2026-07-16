from uuid import UUID

from pydantic import ValidationError

from app_diagnosis.agent.schemas import DiagnosisConclusion
from app_diagnosis.evaluation.models import EvaluationCase, EvaluationResult, EvaluationSuite


def evaluate_case(case: EvaluationCase) -> EvaluationResult:
    failures: list[str] = []
    conclusion = None
    if case.observation.conclusion is not None:
        try:
            conclusion = DiagnosisConclusion.model_validate(case.observation.conclusion)
        except ValidationError:
            failures.append("invalid_structured_output")
    structured = conclusion is not None
    evidence_ids = {UUID(item["id"]) for item in case.observation.evidence}
    evidence_types = {item["type"] for item in case.observation.evidence}
    citations_valid = structured
    if conclusion:
        cited = {
            evidence_id
            for finding in [*conclusion.facts, *conclusion.root_causes]
            for evidence_id in finding.evidence_ids
        }
        citations_valid = cited <= evidence_ids
        if not citations_valid:
            failures.append("invalid_evidence_citations")
    required = set(case.required_evidence_types) <= evidence_types
    if not required:
        failures.append("missing_required_evidence")
    termination = case.observation.termination_reason == case.expected_termination_reason
    if not termination:
        failures.append("unexpected_termination_reason")
    root_match = not case.allowed_root_cause_keywords
    if conclusion and case.allowed_root_cause_keywords:
        text = " ".join(item.statement for item in conclusion.root_causes).casefold()
        root_match = any(item.casefold() in text for item in case.allowed_root_cause_keywords)
    if not root_match:
        failures.append("root_cause_mismatch")
    statuses = case.observation.tool_statuses
    tool_rate = (
        round(sum(item == "success" for item in statuses) / len(statuses), 4) if statuses else 1.0
    )
    return EvaluationResult(
        case_id=case.id,
        passed=not failures,
        structured_output_valid=structured,
        citations_valid=citations_valid,
        required_evidence_present=required,
        termination_reason_matches=termination,
        root_cause_matches=root_match,
        tool_success_rate=tool_rate,
        failures=failures,
    )


def evaluate_suite(cases: list[EvaluationCase]) -> EvaluationSuite:
    results = [evaluate_case(case) for case in cases]
    total = len(results)

    def ratio(count: int) -> float:
        return round(count / total, 4) if total else 0.0

    return EvaluationSuite(
        total=total,
        passed=sum(item.passed for item in results),
        pass_rate=ratio(sum(item.passed for item in results)),
        structured_output_valid_rate=ratio(sum(item.structured_output_valid for item in results)),
        citation_valid_rate=ratio(sum(item.citations_valid for item in results)),
        tool_success_rate=(
            round(sum(item.tool_success_rate for item in results) / total, 4) if total else 0.0
        ),
        results=results,
    )
