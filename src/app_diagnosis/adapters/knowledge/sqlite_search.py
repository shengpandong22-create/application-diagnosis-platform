import asyncio
import re

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_diagnosis.adapters.knowledge.json_seeds import JsonKnowledgeSeedLoader
from app_diagnosis.adapters.persistence.knowledge_repository import (
    SqlAlchemyKnowledgeRepository,
)
from app_diagnosis.domain.knowledge import KnowledgeStatus
from app_diagnosis.ports.knowledge_search import KnowledgeSearchMatch

_TOKEN = re.compile(r"[a-zA-Z0-9_.-]+|[\u4e00-\u9fff]+")


class SqliteKnowledgeSearch:
    """SQLite-backed search with one-time, idempotent JSON seed import."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seed_loader: JsonKnowledgeSeedLoader,
    ) -> None:
        self._sessions = session_factory
        self._seed_loader = seed_loader
        self._initialized = False
        self._initialize_lock = asyncio.Lock()

    async def search(self, query: str, *, limit: int) -> tuple[KnowledgeSearchMatch, ...]:
        await self._ensure_seeded()
        terms = self._tokenize(query)
        if not terms:
            return ()
        async with self._sessions() as session:
            entries = await SqlAlchemyKnowledgeRepository(session).list_by_status(
                KnowledgeStatus.CONFIRMED
            )
        matches: list[KnowledgeSearchMatch] = []
        for entry in entries:
            title = entry.title.casefold()
            error_types = " ".join(entry.error_types).casefold()
            searchable = " ".join(
                [entry.title, entry.summary, *entry.error_types, *entry.tags]
            ).casefold()
            matched = tuple(term for term in terms if term in searchable)
            if not matched:
                continue
            weighted = sum(
                3 if term in title else 2 if term in error_types else 1 for term in matched
            )
            score = round(min(1.0, weighted / max(1, len(terms) * 3)), 4)
            matches.append(
                KnowledgeSearchMatch(
                    entry_id=entry.id,
                    title=entry.title,
                    summary=entry.summary,
                    matched_terms=matched,
                    score=score,
                    source=entry.source,
                )
            )
        matches.sort(key=lambda item: (-item.score, item.entry_id))
        return tuple(matches[:limit])

    async def _ensure_seeded(self) -> None:
        if self._initialized:
            return
        async with self._initialize_lock:
            if self._initialized:
                return
            seeds = await asyncio.to_thread(self._seed_loader.load)
            async with self._sessions.begin() as session:
                repository = SqlAlchemyKnowledgeRepository(session)
                for seed in seeds:
                    if await repository.get(seed.id) is None:
                        await repository.add(seed)
            self._initialized = True

    @staticmethod
    def _tokenize(value: str) -> tuple[str, ...]:
        return tuple(dict.fromkeys(token.casefold() for token in _TOKEN.findall(value)))
