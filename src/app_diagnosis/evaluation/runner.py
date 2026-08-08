from collections.abc import Iterable
from uuid import UUID

from pydantic import ValidationError

from app_diagnosis.agent.schemas import DiagnosisConclusion
from app_diagnosis.evaluation.models import EvaluationCase, EvaluationResult, EvaluationSuite


def _ratio(numerator: float, denominator: int, *, empty: float = 0.0) -> float:
    return round(numerator / denominator, 4) if denominator else empty


def _optional_rate(values: Iterable[bool | None]) -> float | None:
    applicable = [item for item in values if item is not None]
    return _ratio(sum(applicable), len(applicable)) if applicable else None


def _contains_any(text: str, keywords: list[str]) -> bool:
    folded = text.casefold()
    return any(keyword.casefold() in folded for keyword in keywords)


def evaluate_case(case: EvaluationCase) -> EvaluationResult:
    failures: list[str] = []
    conclusion = None
    if case.observation.conclusion is not None:
        try:
            conclusion = DiagnosisConclusion.model_validate(case.observation.conclusion)
        except ValidationError:
            failures.append("invalid_structured_output")
    structured = conclusion is not None

    evidence_ids: set[UUID] = set()
    evidence_types: set[str] = set()
    for item in case.observation.evidence:
        try:
            evidence_ids.add(UUID(item["id"]))
            evidence_types.add(item["type"])
        except (KeyError, TypeError, ValueError):
            failures.append("invalid_evidence_record")

    findings = [*conclusion.facts, *conclusion.root_causes] if conclusion else []
    cited = {evidence_id for finding in findings for evidence_id in finding.evidence_ids}
    valid_cited = cited & evidence_ids
    invalid_cited = cited - evidence_ids
    citations_valid = structured and not invalid_cited
    if not citations_valid:
        failures.append("invalid_evidence_citations")

    required_types_present = set(case.required_evidence_types) <= evidence_types
    required_ids_present = set(case.required_evidence_ids) <= evidence_ids
    required = required_types_present and required_ids_present
    if not required:
        failures.append("missing_required_evidence")

    citation_precision = _ratio(len(valid_cited), len(cited), empty=1.0)
    expected_citations = set(case.required_evidence_ids)
    citation_recall = _ratio(
        len(cited & expected_citations), len(expected_citations), empty=1.0
    )
    if citation_recall < 1.0:
        failures.append("missing_required_evidence_citations")

    supported_statuses = {"confirmed", "probable", "possible"}
    unsupported = [
        finding
        for finding in findings
        if finding.status in supported_statuses and not finding.evidence_ids
    ]
    unsupported_claim_rate = _ratio(len(unsupported), len(findings), empty=0.0)
    if unsupported:
        failures.append("unsupported_claims")

    termination = case.observation.termination_reason == case.expected_termination_reason
    if not termination:
        failures.append("unexpected_termination_reason")

    category_matches = None
    if case.expected_category is not None:
        category_matches = case.observation.observed_category == case.expected_category
        if not category_matches:
            failures.append("category_mismatch")

    root_statements = [item.statement for item in conclusion.root_causes] if conclusion else []
    root_top1 = not case.allowed_root_cause_keywords
    root_top3 = not case.allowed_root_cause_keywords
    if case.allowed_root_cause_keywords:
        root_top1 = bool(root_statements) and _contains_any(
            root_statements[0], case.allowed_root_cause_keywords
        )
        root_top3 = _contains_any(
            " ".join(root_statements[:3]), case.allowed_root_cause_keywords
        )
    root_match = root_top3
    if not root_match:
        failures.append("root_cause_mismatch")

    all_root_text = " ".join(root_statements)
    if case.forbidden_root_cause_keywords and _contains_any(
        all_root_text, case.forbidden_root_cause_keywords
    ):
        failures.append("forbidden_root_cause")

    information_sufficiency_matches = None
    if case.expected_information_sufficient is not None:
        observed_sufficient = bool(conclusion and conclusion.root_causes) and not any(
            finding.status == "insufficient_evidence" for finding in findings
        )
        information_sufficiency_matches = (
            observed_sufficient == case.expected_information_sufficient
        )
        if not information_sufficiency_matches:
            failures.append("information_sufficiency_mismatch")

    tool_selection_matches = None
    if case.expected_tool_names:
        tool_selection_matches = set(case.expected_tool_names) <= set(case.observation.tool_names)
        if not tool_selection_matches:
            failures.append("tool_selection_mismatch")

    statuses = case.observation.tool_statuses
    tool_rate = _ratio(sum(item == "success" for item in statuses), len(statuses), empty=1.0)
    incorrect = any(
        item is False
        for item in (category_matches, root_match, information_sufficiency_matches)
    )
    high_confidence_error = bool(
        incorrect
        and case.observation.confidence is not None
        and case.observation.confidence >= 0.8
    )

    return EvaluationResult(
        case_id=case.id,
        versions=case.versions,
        passed=not failures,
        structured_output_valid=structured,
        citations_valid=citations_valid,
        required_evidence_present=required,
        termination_reason_matches=termination,
        category_matches=category_matches,
        root_cause_matches=root_match,
        root_cause_top1_matches=root_top1,
        root_cause_top3_matches=root_top3,
        information_sufficiency_matches=information_sufficiency_matches,
        tool_selection_matches=tool_selection_matches,
        citation_precision=citation_precision,
        citation_recall=citation_recall,
        unsupported_claim_rate=unsupported_claim_rate,
        high_confidence_error=high_confidence_error,
        tool_success_rate=tool_rate,
        latency_ms=case.observation.latency_ms,
        total_tokens=case.observation.prompt_tokens + case.observation.completion_tokens,
        estimated_cost_usd=case.observation.estimated_cost_usd,
        failures=list(dict.fromkeys(failures)),
    )


def evaluate_suite(cases: list[EvaluationCase]) -> EvaluationSuite:
    results = [evaluate_case(case) for case in cases]
    total = len(results)

    confusion: dict[str, dict[str, int]] = {}
    for case in cases:
        if case.expected_category is None:
            continue
        actual = case.observation.observed_category or "unclassified"
        row = confusion.setdefault(case.expected_category, {})
        row[actual] = row.get(actual, 0) + 1

    return EvaluationSuite(
        total=total,
        passed=sum(item.passed for item in results),
        pass_rate=_ratio(sum(item.passed for item in results), total),
        dataset_versions=sorted({item.versions.dataset_version for item in results}),
        structured_output_valid_rate=_ratio(
            sum(item.structured_output_valid for item in results), total
        ),
        citation_valid_rate=_ratio(sum(item.citations_valid for item in results), total),
        required_evidence_rate=_ratio(
            sum(item.required_evidence_present for item in results), total
        ),
        termination_reason_match_rate=_ratio(
            sum(item.termination_reason_matches for item in results), total
        ),
        category_accuracy=_optional_rate(item.category_matches for item in results),
        category_confusion_matrix=confusion,
        root_cause_top1_rate=_ratio(
            sum(item.root_cause_top1_matches for item in results), total
        ),
        root_cause_top3_rate=_ratio(
            sum(item.root_cause_top3_matches for item in results), total
        ),
        information_sufficiency_accuracy=_optional_rate(
            item.information_sufficiency_matches for item in results
        ),
        tool_selection_accuracy=_optional_rate(item.tool_selection_matches for item in results),
        citation_precision=(
            round(sum(item.citation_precision for item in results) / total, 4)
            if total
            else 0.0
        ),
        citation_recall=(
            round(sum(item.citation_recall for item in results) / total, 4)
            if total
            else 0.0
        ),
        unsupported_claim_rate=(
            round(sum(item.unsupported_claim_rate for item in results) / total, 4)
            if total
            else 0.0
        ),
        high_confidence_error_rate=_ratio(
            sum(item.high_confidence_error for item in results), total
        ),
        tool_success_rate=(
            round(sum(item.tool_success_rate for item in results) / total, 4)
            if total
            else 0.0
        ),
        average_latency_ms=(
            round(sum(item.latency_ms for item in results) / total, 2) if total else 0.0
        ),
        total_tokens=sum(item.total_tokens for item in results),
        estimated_cost_usd=round(sum(item.estimated_cost_usd for item in results), 8),
        results=results,
    )
