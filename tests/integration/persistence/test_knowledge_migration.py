import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config


def test_knowledge_migration_upgrade_and_downgrade(tmp_path: Path) -> None:
    database_path = tmp_path / "knowledge-migration.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path.as_posix()}")
    command.upgrade(config, "head")
    command.check(config)
    with sqlite3.connect(database_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info('knowledge_entries')")}
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    assert columns == {
        "id",
        "title",
        "summary",
        "error_types_json",
        "tags_json",
        "source",
        "status",
        "created_at",
        "updated_at",
    }
    assert revision == "0008"
    command.downgrade(config, "0003")
    with sqlite3.connect(database_path) as connection:
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='knowledge_entries'"
            ).fetchone()
            is None
        )
