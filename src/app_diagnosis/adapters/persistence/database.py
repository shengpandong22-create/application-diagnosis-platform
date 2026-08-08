from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy import event, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class Database:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.engine: AsyncEngine = create_async_engine(database_url, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        self._configure_sqlite()

    async def start(self) -> None:
        self._ensure_sqlite_parent_exists()

    async def dispose(self) -> None:
        await self.engine.dispose()

    async def is_ready(self) -> bool:
        try:
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError:
            return False

    async def sessions(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            yield session

    def _configure_sqlite(self) -> None:
        if make_url(self.database_url).get_backend_name() != "sqlite":
            return

        @event.listens_for(self.engine.sync_engine, "connect")
        def set_sqlite_pragmas(dbapi_connection: object, _: object) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    def _ensure_sqlite_parent_exists(self) -> None:
        url = make_url(self.database_url)
        if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
            return
        Path(url.database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
