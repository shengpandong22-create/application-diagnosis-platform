from typing import Protocol

from app_diagnosis.domain.knowledge import KnowledgeEntry, KnowledgeStatus


class KnowledgeRepositoryError(RuntimeError):
    """Base error exposed by the knowledge repository port."""


class KnowledgeAlreadyExists(KnowledgeRepositoryError):
    def __init__(self, entry_id: str) -> None:
        self.entry_id = entry_id
        super().__init__(f"knowledge entry already exists: {entry_id}")


class KnowledgeRepository(Protocol):
    async def add(self, entry: KnowledgeEntry) -> None: ...

    async def get(self, entry_id: str) -> KnowledgeEntry | None: ...

    async def save(self, entry: KnowledgeEntry) -> None: ...

    async def list_by_status(self, status: KnowledgeStatus) -> tuple[KnowledgeEntry, ...]: ...
