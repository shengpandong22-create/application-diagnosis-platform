"""判断模型结论是否可以采信 Evidence 引用的确定性策略。"""

from dataclasses import dataclass
from uuid import UUID

from app_diagnosis.agent.schemas import DiagnosisConclusion, DiagnosisFinding
from app_diagnosis.domain.evidence import Evidence, EvidenceType


@dataclass(frozen=True, slots=True)
class CitationViolation:
    code: str
    message: str


class EvidenceCitationPolicy:
    def validate(
        self,
        conclusion: DiagnosisConclusion,
        evidence: tuple[Evidence, ...],
    ) -> tuple[CitationViolation, ...]:
        """校验一份模型结论，并返回所有引用违规项。

        Policy 只做判断，不修改 conclusion 或 Evidence。这样 Runner 可以根据
        违规结果决定让模型修正、降级为 inconclusive，或继续完成。
        """
        by_id = {item.id: item for item in evidence}
        violations: list[CitationViolation] = []
        findings = [*conclusion.facts, *conclusion.root_causes]
        for finding in conclusion.facts:
            violations.extend(self._validate_finding(finding, by_id, require_evidence=True))
        for finding in conclusion.root_causes:
            violations.extend(self._validate_finding(finding, by_id, require_evidence=False))
        if any(item.status == "possible" for item in findings) and not conclusion.recommendations:
            violations.append(
                CitationViolation(
                    "possible_requires_verification",
                    "possible findings require at least one verification recommendation",
                )
            )
        return tuple(violations)

    @staticmethod
    def _validate_finding(
        finding: DiagnosisFinding,
        by_id: dict[UUID, Evidence],
        *,
        require_evidence: bool,
    ) -> list[CitationViolation]:
        """校验单条 fact/root-cause 是否满足 Evidence 规则。

        probable 需要用户事实或日志证据；insufficient_evidence 不能伪造引用；
        confirmed 只能来自人工确认，模型不能直接声明。
        """
        violations: list[CitationViolation] = []
        referenced = [by_id.get(item) for item in finding.evidence_ids]
        if any(item is None for item in referenced):
            violations.append(
                CitationViolation(
                    "foreign_or_unknown_evidence",
                    "all cited evidence IDs must belong to the current diagnosis",
                )
            )
        valid = [item for item in referenced if item is not None]
        if finding.status == "confirmed":
            violations.append(
                CitationViolation(
                    "model_cannot_confirm",
                    "confirmed status is reserved for human confirmation in Phase 0",
                )
            )
        if finding.status == "probable" and not any(
            item.type in {EvidenceType.USER_STATEMENT, EvidenceType.LOG_EXCERPT} for item in valid
        ):
            violations.append(
                CitationViolation(
                    "probable_requires_direct_evidence",
                    "probable findings require user or log evidence",
                )
            )
        if finding.status == "insufficient_evidence" and finding.evidence_ids:
            violations.append(
                CitationViolation(
                    "insufficient_must_not_cite",
                    "insufficient_evidence findings must not cite evidence IDs",
                )
            )
        if (
            require_evidence
            and finding.status != "insufficient_evidence"
            and not finding.evidence_ids
        ):
            violations.append(
                CitationViolation(
                    "finding_requires_evidence",
                    "facts and hypotheses require at least one evidence ID",
                )
            )
        return violations
