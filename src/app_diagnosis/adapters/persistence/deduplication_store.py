import asyncio
from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_diagnosis.adapters.persistence.incident_models import DeduplicationKeyRecord


class InMemoryDeduplicationStore:
    def __init__(self) -> None:
        self._entries: dict[str, datetime] = {}
        self._lock = asyncio.Lock()

    async def claim(self, key: str, *, expires_at: datetime) -> bool:
        now = datetime.now(UTC)
        async with self._lock:
            current = self._entries.get(key)
            if current is not None and current > now:
                return False
            self._entries[key] = expires_at
            return True


class SqlAlchemyDeduplicationStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def claim(self, key: str, *, expires_at: datetime) -> bool:
        now = datetime.now(UTC)
        async with self._sessions.begin() as session:
            await session.execute(
                delete(DeduplicationKeyRecord).where(
                    DeduplicationKeyRecord.key == key,
                    DeduplicationKeyRecord.expires_at <= now,
                )
            )
            try:
                async with session.begin_nested():
                    session.add(
                        DeduplicationKeyRecord(key=key, expires_at=expires_at, created_at=now)
                    )
                    await session.flush()
                return True
            except IntegrityError:
                return False
