from datetime import UTC, datetime
from uuid import UUID

from app_diagnosis.agent.policies import EvidenceCitationPolicy
from app_diagnosis.agent.schemas import DiagnosisConclusion, DiagnosisFinding
from app_diagnosis.domain.evidence import (
    Evidence,
    EvidenceReliability,
    EvidenceSource,
    EvidenceType,
)

DIAGNOSIS_ID = UUID("11111111-1111-1111-1111-111111111111")
OTHER_ID = UUID("22222222-2222-2222-2222-222222222222")
NOW = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)


def evidence(type: EvidenceType, content: str) -> Evidence:
    return Evidence.create(
        diagnosis_id=DIAGNOSIS_ID,
        type=type,
        source=EvidenceSource.USER_INPUT
        if type is not EvidenceType.KNOWLEDGE_ENTRY
        else EvidenceSource.LOCAL_KNOWLEDGE,
        content=content,
        reliability=EvidenceReliability.MEDIUM,
        now=NOW,
    )


def conclusion(
    finding: DiagnosisFinding, *, recommendations: list[str] | None = None, as_fact: bool = False
) -> DiagnosisConclusion:
    return DiagnosisConclusion(
        symptom_summary="HTTP 500",
        facts=[finding] if as_fact else [],
        root_causes=[] if as_fact else [finding],
        recommendations=recommendations or [],
        missing_information=[],
    )


def codes(result) -> set[str]:
    return {item.code for item in result}


def test_probable_requires_direct_evidence_not_only_knowledge() -> None:
    knowledge = evidence(EvidenceType.KNOWLEDGE_ENTRY, "Known NPE pattern")
    result = EvidenceCitationPolicy().validate(
        conclusion(
            DiagnosisFinding(statement="NPE", status="probable", evidence_ids=[knowledge.id])
        ),
        (knowledge,),
    )
    assert "probable_requires_direct_evidence" in codes(result)


def test_probable_accepts_log_evidence() -> None:
    log = evidence(EvidenceType.LOG_EXCERPT, "NullPointerException")
    result = EvidenceCitationPolicy().validate(
        conclusion(DiagnosisFinding(statement="NPE", status="probable", evidence_ids=[log.id])),
        (log,),
    )
    assert result == ()


def test_confirmed_is_reserved_for_human_and_foreign_ids_are_rejected() -> None:
    result = EvidenceCitationPolicy().validate(
        conclusion(DiagnosisFinding(statement="NPE", status="confirmed", evidence_ids=[OTHER_ID])),
        (),
    )
    assert {"model_cannot_confirm", "foreign_or_unknown_evidence"} <= codes(result)


def test_possible_requires_verification_recommendation_but_may_lack_evidence() -> None:
    result = EvidenceCitationPolicy().validate(
        conclusion(DiagnosisFinding(statement="Maybe NPE", status="possible", evidence_ids=[])), ()
    )
    assert codes(result) == {"possible_requires_verification"}


def test_fact_requires_evidence_id() -> None:
    result = EvidenceCitationPolicy().validate(
        conclusion(
            DiagnosisFinding(statement="Observed NPE", status="possible", evidence_ids=[]),
            recommendations=["Verify stack"],
            as_fact=True,
        ),
        (),
    )
    assert "finding_requires_evidence" in codes(result)


def test_insufficient_evidence_cannot_invent_ids() -> None:
    result = EvidenceCitationPolicy().validate(
        conclusion(
            DiagnosisFinding(
                statement="Need logs", status="insufficient_evidence", evidence_ids=[OTHER_ID]
            )
        ),
        (),
    )
    assert "insufficient_must_not_cite" in codes(result)
