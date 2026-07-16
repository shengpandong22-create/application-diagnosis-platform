from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_diagnosis.adapters.persistence.audit_repository import SqlAlchemyAuditRepository
from app_diagnosis.adapters.persistence.confirmation_repository import (
    SqlAlchemyConfirmationRepository,
)
from app_diagnosis.adapters.persistence.diagnosis_repository import SqlAlchemyDiagnosisRepository
from app_diagnosis.adapters.persistence.evidence_repository import SqlAlchemyEvidenceRepository
from app_diagnosis.application.diagnoses import DiagnosisApplicationService as BaseService
from app_diagnosis.application.diagnoses import DiagnosisNotFound, DiagnosisRunConflict
from app_diagnosis.domain.audit import AuditEvent
from app_diagnosis.domain.confirmation import Confirmation, ConfirmationAction
from app_diagnosis.domain.diagnosis import (
    DiagnosisCase,
    DiagnosisStatus,
    InvalidDiagnosisValue,
)
from app_diagnosis.domain.evidence import (
    Evidence,
    EvidenceReliability,
    EvidenceSource,
    EvidenceType,
)
from app_diagnosis.ports.redaction import Redactor


class EvidenceAwareDiagnosisApplicationService(BaseService):
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        redactor: Redactor,
        **kwargs: object,
    ) -> None:
        super().__init__(session_factory=session_factory, **kwargs)  # type: ignore[arg-type]
        self._redactor = redactor

    async def create(
        self,
        *,
        title: str,
        symptom: str,
        submitted_log: str | None,
    ) -> DiagnosisCase:
        if submitted_log and len(submitted_log.encode("utf-8")) > self._max_input_log_bytes:
            raise InvalidDiagnosisValue("submitted_log exceeds configured byte limit")

        safe_symptom = self._redactor.redact(symptom)
        safe_log = self._redactor.redact(submitted_log) if submitted_log else None
        diagnosis = DiagnosisCase.create(
            title=title,
            symptom=safe_symptom.content,
            submitted_log=safe_log.content if safe_log else None,
        )
        evidence = [
            Evidence.create(
                diagnosis_id=diagnosis.id,
                type=EvidenceType.USER_STATEMENT,
                source=EvidenceSource.USER_INPUT,
                content=safe_symptom.content,
                reliability=EvidenceReliability.MEDIUM,
                metadata={
                    "untrusted_input": True,
                    "redaction_count": safe_symptom.redaction_count,
                    "redaction_categories": list(safe_symptom.matched_categories),
                },
                redaction_status=safe_symptom.status,
                now=diagnosis.created_at,
            )
        ]
        if safe_log and safe_log.content.strip():
            chunks = _split_utf8(safe_log.content, Evidence.MAX_CONTENT_BYTES)
            for index, chunk in enumerate(chunks, start=1):
                evidence.append(
                    Evidence.create(
                        diagnosis_id=diagnosis.id,
                        type=EvidenceType.LOG_EXCERPT,
                        source=EvidenceSource.USER_INPUT,
                        source_reference=f"submitted_log:{index}/{len(chunks)}",
                        content=chunk,
                        reliability=EvidenceReliability.HIGH,
                        metadata={
                            "untrusted_input": True,
                            "chunk_index": index,
                            "chunk_count": len(chunks),
                            "redaction_count": safe_log.redaction_count,
                            "redaction_categories": list(safe_log.matched_categories),
                        },
                        redaction_status=safe_log.status,
                        now=diagnosis.created_at + timedelta(microseconds=index),
                    )
                )

        unique_evidence: dict[str, Evidence] = {}
        for item in evidence:
            unique_evidence.setdefault(item.content_hash, item)
        async with self._sessions.begin() as session:
            await SqlAlchemyDiagnosisRepository(session).add(diagnosis)
            repository = SqlAlchemyEvidenceRepository(session)
            for item in unique_evidence.values():
                await repository.add(item)
                await SqlAlchemyAuditRepository(session).add(
                    AuditEvent.create(
                        actor="local-api-user",
                        action="evidence.created",
                        target_type="evidence",
                        target_id=str(item.id),
                        summary=f"Created {item.type.value} evidence for diagnosis {diagnosis.id}",
                    )
                )
        return diagnosis

    async def list_evidence(self, diagnosis_id):
        await self.get(diagnosis_id)
        async with self._sessions() as session:
            return tuple(
                await SqlAlchemyEvidenceRepository(session).list_by_diagnosis(diagnosis_id)
            )

    async def supplement(self, diagnosis_id, *, content: str, evidence_type: EvidenceType):
        safe = self._redactor.redact(content)
        evidence = Evidence.create(
            diagnosis_id=diagnosis_id,
            type=evidence_type,
            source=EvidenceSource.USER_INPUT,
            source_reference="user_supplement",
            content=safe.content,
            reliability=(
                EvidenceReliability.HIGH
                if evidence_type is EvidenceType.LOG_EXCERPT
                else EvidenceReliability.MEDIUM
            ),
            metadata={
                "untrusted_input": True,
                "supplement": True,
                "redaction_count": safe.redaction_count,
                "redaction_categories": list(safe.matched_categories),
            },
            redaction_status=safe.status,
        )
        async with self._sessions.begin() as session:
            diagnoses = SqlAlchemyDiagnosisRepository(session)
            diagnosis = await diagnoses.get(diagnosis_id)
            if diagnosis is None:
                raise DiagnosisNotFound(str(diagnosis_id))
            if diagnosis.status is not DiagnosisStatus.WAITING_FOR_INPUT:
                raise DiagnosisRunConflict(
                    f"diagnosis cannot accept supplements from status {diagnosis.status.value}"
                )
            repository = SqlAlchemyEvidenceRepository(session)
            existing = await repository.find_by_hash(diagnosis_id, evidence.content_hash)
            if existing is None:
                await repository.add(evidence)
            else:
                evidence = existing
            expected_version = diagnosis.version
            diagnosis.reopen_investigation()
            await diagnoses.save(diagnosis, expected_version=expected_version)
            audits = SqlAlchemyAuditRepository(session)
            if existing is None:
                await audits.add(
                    AuditEvent.create(
                        actor="local-api-user",
                        action="evidence.created",
                        target_type="evidence",
                        target_id=str(evidence.id),
                        summary=f"Created supplemental {evidence.type.value} evidence",
                    )
                )
            await audits.add(
                AuditEvent.create(
                    actor="local-api-user",
                    action="diagnosis.supplemented",
                    target_type="diagnosis",
                    target_id=str(diagnosis.id),
                    summary="User supplied additional diagnostic evidence",
                )
            )
        return diagnosis, evidence

    async def confirm_action(
        self,
        diagnosis_id,
        *,
        action: ConfirmationAction,
        actor: str,
        comment: str | None,
    ):
        safe_comment = self._redactor.redact(comment).content if comment else None
        confirmation = Confirmation.create(
            diagnosis_id=diagnosis_id,
            action=action,
            actor=actor,
            comment=safe_comment,
        )
        async with self._sessions.begin() as session:
            diagnoses = SqlAlchemyDiagnosisRepository(session)
            diagnosis = await diagnoses.get(diagnosis_id)
            if diagnosis is None:
                raise DiagnosisNotFound(str(diagnosis_id))
            if diagnosis.status is not DiagnosisStatus.WAITING_FOR_CONFIRMATION:
                raise DiagnosisRunConflict(
                    f"diagnosis cannot be confirmed from status {diagnosis.status.value}"
                )
            expected_version = diagnosis.version
            if action is ConfirmationAction.CONFIRM:
                diagnosis.confirm()
            elif action is ConfirmationAction.REJECT:
                diagnosis.reject()
            else:
                diagnosis.reopen_investigation()
            await diagnoses.save(diagnosis, expected_version=expected_version)
            await SqlAlchemyConfirmationRepository(session).add(confirmation)
            action_name = {
                ConfirmationAction.CONFIRM: "diagnosis.confirmed",
                ConfirmationAction.REJECT: "diagnosis.rejected",
                ConfirmationAction.CONTINUE_INVESTIGATION: "diagnosis.reopened",
            }[action]
            await SqlAlchemyAuditRepository(session).add(
                AuditEvent.create(
                    actor=actor,
                    action=action_name,
                    target_type="diagnosis",
                    target_id=str(diagnosis.id),
                    summary=f"Human action recorded: {action.value}",
                )
            )
        return diagnosis, confirmation


def _split_utf8(content: str, max_bytes: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_bytes = 0
    for character in content:
        size = len(character.encode("utf-8"))
        if current and current_bytes + size > max_bytes:
            chunks.append("".join(current))
            current = []
            current_bytes = 0
        current.append(character)
        current_bytes += size
    if current:
        chunks.append("".join(current))
    return chunks
