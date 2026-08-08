import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config


def test_incident_migration_creates_required_tables(tmp_path: Path) -> None:
    path = tmp_path / "migration.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{path.as_posix()}")
    command.upgrade(config, "head")
    command.check(config)
    with sqlite3.connect(path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    assert {"incidents", "deduplication_keys"} <= tables
    assert revision == "0013"
