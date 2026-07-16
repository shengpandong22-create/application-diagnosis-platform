import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config


def test_confirmation_migration_upgrade_and_downgrade(tmp_path: Path) -> None:
    database_path = tmp_path / "confirmation-migration.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path.as_posix()}")
    command.upgrade(config, "head")
    command.check(config)
    with sqlite3.connect(database_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info('confirmations')")}
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    assert columns == {"id", "diagnosis_id", "action", "actor", "comment", "created_at"}
    assert revision == "0006"
    command.downgrade(config, "0004")
    with sqlite3.connect(database_path) as connection:
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='confirmations'"
        ).fetchone()
    assert table is None
