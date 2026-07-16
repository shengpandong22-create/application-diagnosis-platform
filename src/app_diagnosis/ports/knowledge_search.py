from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class KnowledgeSearchMatch:
    entry_id: str
    title: str
    summary: str
    matched_terms: tuple[str, ...]
    score: float
    source: str


class KnowledgeSearchPort(Protocol):
    async def search(self, query: str, *, limit: int) -> tuple[KnowledgeSearchMatch, ...]: ...
