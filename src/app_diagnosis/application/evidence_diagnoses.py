"""带 Evidence、脱敏和人工反馈的诊断用例层。

这个模块扩展基础 DiagnosisApplicationService，承接 Phase 0B 的闭环能力：
入库前脱敏、创建用户/日志 Evidence、接受补充信息、记录人工确认。
后续改造时要守住一条原则：原始敏感文本不能先入库再脱敏，人工反馈也不能
覆盖模型原始结论，只能追加 Confirmation 和 Audit。
"""

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
        service_id=None,
    ) -> DiagnosisCase:
        """创建诊断，并把初始用户输入转换为已脱敏 Evidence。

        symptom 和 submitted_log 都先经过 Redactor，再写入 DiagnosisCase 和 Evidence。
        submitted_log 会按 Evidence 最大字节数切片，避免单条证据过大。
        """
        if submitted_log and len(submitted_log.encode("utf-8")) > self._max_input_log_bytes:
            raise InvalidDiagnosisValue("submitted_log exceeds configured byte limit")

        # 敏感文本必须在持久化和进入模型前完成脱敏，不能依赖事后清理。
        safe_symptom = self._redactor.redact(symptom)
        safe_log = self._redactor.redact(submitted_log) if submitted_log else None
        diagnosis = DiagnosisCase.create(
            title=title,
            symptom=safe_symptom.content,
            submitted_log=safe_log.content if safe_log else None,
            service_id=service_id,
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
        """查询诊断下的 Evidence，并先确认父 Diagnosis 存在。

        这是只读查询，不改变状态，也不触发 Agent 重新运行。
        """
        await self.get(diagnosis_id)
        async with self._sessions() as session:
            return tuple(
                await SqlAlchemyEvidenceRepository(session).list_by_diagnosis(diagnosis_id)
            )

    async def supplement(self, diagnosis_id, *, content: str, evidence_type: EvidenceType):
        """追加已脱敏补充 Evidence，并把诊断重新打开到 INVESTIGATING。

        只有 WAITING_FOR_INPUT 状态可以补充信息。相同 Diagnosis 下会按 content_hash
        去重，避免用户重复提交相同日志片段导致证据膨胀。
        """
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
        """记录人工决策，并推动确认、驳回或继续调查状态。

        人工确认是独立事实：它追加 Confirmation 和 AuditEvent，不覆盖
        DiagnosisCase.conclusion 中保存的模型初始结论。
        """
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
    """按字节上限切分文本，且不截断中文等多字节字符。

        Evidence 的大小限制按 UTF-8 字节计算；逐字符累加可以避免把一个字符
        切成非法字节序列。
        """
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
