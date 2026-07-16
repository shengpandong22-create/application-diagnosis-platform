from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_diagnosis.adapters.persistence.audit_repository import SqlAlchemyAuditRepository
from app_diagnosis.adapters.persistence.knowledge_repository import SqlAlchemyKnowledgeRepository
from app_diagnosis.domain.audit import AuditEvent
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
