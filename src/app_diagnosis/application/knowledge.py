from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_diagnosis.adapters.persistence.audit_repository import SqlAlchemyAuditRepository
from app_diagnosis.adapters.persistence.diagnosis_repository import SqlAlchemyDiagnosisRepository
from app_diagnosis.adapters.persistence.knowledge_repository import SqlAlchemyKnowledgeRepository
from app_diagnosis.agent.schemas import DiagnosisConclusion
from app_diagnosis.application.diagnoses import DiagnosisNotFound
from app_diagnosis.domain.audit import AuditEvent
from app_diagnosis.domain.diagnosis import DiagnosisStatus
from app_diagnosis.domain.knowledge import (
    InvalidKnowledgeStatusTransition,
    KnowledgeEntry,
    KnowledgeStatus,
)
from app_diagnosis.ports.knowledge_repository import KnowledgeAlreadyExists
from app_diagnosis.ports.redaction import Redactor


class KnowledgeConflict(RuntimeError):
    pass


class KnowledgeNotFound(LookupError):
    pass


class KnowledgeStatusConflict(RuntimeError):
    pass


class KnowledgeCandidateNotAllowed(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class KnowledgeCandidateResult:
    entry: KnowledgeEntry
    created: bool


class KnowledgeApplicationService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        redactor: Redactor,
    ) -> None:
        self._sessions = session_factory
        self._redactor = redactor

    async def create(
        self,
        *,
        entry_id: str,
        title: str,
        summary: str,
        source: str,
        error_types: tuple[str, ...],
        tags: tuple[str, ...],
    ) -> KnowledgeEntry:
        entry = KnowledgeEntry.create(
            entry_id=entry_id,
            title=self._redactor.redact(title).content,
            summary=self._redactor.redact(summary).content,
            source=source,
            error_types=error_types,
            tags=tags,
            status=KnowledgeStatus.CANDIDATE,
        )
        try:
            async with self._sessions.begin() as session:
                await SqlAlchemyKnowledgeRepository(session).add(entry)
                await SqlAlchemyAuditRepository(session).add(
                    AuditEvent.create(
                        actor="local-api-user",
                        action="knowledge.created",
                        target_type="knowledge",
                        target_id=entry.id,
                        summary="Created candidate knowledge entry",
                    )
                )
        except KnowledgeAlreadyExists as error:
            raise KnowledgeConflict(str(error)) from error
        return entry

    async def list(self, status: KnowledgeStatus | None) -> tuple[KnowledgeEntry, ...]:
        statuses = (status,) if status else tuple(KnowledgeStatus)
        async with self._sessions() as session:
            repository = SqlAlchemyKnowledgeRepository(session)
            entries = [
                item for value in statuses for item in await repository.list_by_status(value)
            ]
        return tuple(sorted(entries, key=lambda item: item.id))

    async def change_status(
        self,
        *,
        entry_id: str,
        status: KnowledgeStatus,
        actor: str,
        correlation_id: str,
    ) -> KnowledgeEntry:
        async with self._sessions.begin() as session:
            repository = SqlAlchemyKnowledgeRepository(session)
            entry = await repository.get(entry_id)
            if entry is None:
                raise KnowledgeNotFound(entry_id)
            previous_status = entry.status
            try:
                updated = entry.with_status(status)
            except InvalidKnowledgeStatusTransition as error:
                raise KnowledgeStatusConflict(str(error)) from error
            if updated is entry:
                return entry
            await repository.save(updated)
            await SqlAlchemyAuditRepository(session).add(
                AuditEvent.create(
                    actor=actor,
                    action="knowledge.status_changed",
                    target_type="knowledge",
                    target_id=entry.id,
                    summary=(
                        "Knowledge status changed from "
                        f"{previous_status.value} to {updated.status.value}"
                    ),
                    correlation_id=correlation_id,
                )
            )
            return updated

    async def create_from_confirmed_diagnosis(
        self,
        *,
        diagnosis_id: UUID,
        actor: str,
        correlation_id: str,
    ) -> KnowledgeCandidateResult:
        """从人工确认诊断生成可审核的知识候选。

        该用例不调用 LLM，也不会直接生成 confirmed 知识。确定性 ID 让重复请求
        返回同一条候选，避免同一 Diagnosis 反复污染知识库。
        """
        entry_id = f"diagnosis-{diagnosis_id}"
        source = f"diagnosis:{diagnosis_id}"
        async with self._sessions.begin() as session:
            diagnosis = await SqlAlchemyDiagnosisRepository(session).get(diagnosis_id)
            if diagnosis is None:
                raise DiagnosisNotFound(str(diagnosis_id))
            if diagnosis.status is not DiagnosisStatus.CONFIRMED or not diagnosis.conclusion:
                raise KnowledgeCandidateNotAllowed(
                    "knowledge candidate requires a confirmed diagnosis with a conclusion"
                )

            repository = SqlAlchemyKnowledgeRepository(session)
            existing = await repository.get(entry_id)
            if existing is not None:
                if existing.source != source:
                    raise KnowledgeConflict(f"knowledge id is already used: {entry_id}")
                return KnowledgeCandidateResult(entry=existing, created=False)

            conclusion = DiagnosisConclusion.model_validate(diagnosis.conclusion)
            title = self._redactor.redact(f"已确认诊断：{diagnosis.title}").content[:200]
            summary = self._redactor.redact(_candidate_summary(conclusion)).content[:4000]
            entry = KnowledgeEntry.create(
                entry_id=entry_id,
                title=title,
                summary=summary,
                source=source,
                error_types=(diagnosis.problem_type.value,),
                tags=("diagnosis-derived", "human-confirmed"),
                status=KnowledgeStatus.CANDIDATE,
            )
            try:
                await repository.add(entry)
            except KnowledgeAlreadyExists as error:
                # 确定性 ID 同时承担幂等键。并发请求竞争时，唯一约束是最后防线；
                # 若冲突记录确实来自同一 Diagnosis，则返回已有候选而不是暴露 500。
                existing = await repository.get(entry_id)
                if existing is not None and existing.source == source:
                    return KnowledgeCandidateResult(entry=existing, created=False)
                raise KnowledgeConflict(str(error)) from error
            await SqlAlchemyAuditRepository(session).add(
                AuditEvent.create(
                    actor=actor,
                    action="knowledge.created_from_diagnosis",
                    target_type="knowledge",
                    target_id=entry.id,
                    summary=f"Created candidate knowledge from diagnosis {diagnosis_id}",
                    correlation_id=correlation_id,
                )
            )
            return KnowledgeCandidateResult(entry=entry, created=True)


def _candidate_summary(conclusion: DiagnosisConclusion) -> str:
    """把已确认结论确定性投影为知识摘要，不重新请求模型。"""
    lines = [f"症状：{conclusion.symptom_summary}"]
    if conclusion.root_causes:
        lines.append("根因：")
        lines.extend(f"- {item.statement}" for item in conclusion.root_causes)
    if conclusion.recommendations:
        lines.append("建议：")
        lines.extend(f"- {item}" for item in conclusion.recommendations)
    evidence_ids = tuple(
        dict.fromkeys(
            str(evidence_id)
            for finding in (*conclusion.facts, *conclusion.root_causes)
            for evidence_id in finding.evidence_ids
        )
    )
    if evidence_ids:
        lines.append("来源 Evidence：" + ", ".join(evidence_ids))
    return "\n".join(lines)
