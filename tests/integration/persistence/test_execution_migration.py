import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config


def test_execution_tables_are_created_by_migrations(tmp_path: Path) -> None:
    database_path = tmp_path / "execution-migration.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path.as_posix()}")
    command.upgrade(config, "head")
    command.check(config)
    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    assert {
        "diagnoses",
        "agent_runs",
        "tool_runs",
        "evidence",
        "knowledge_entries",
        "confirmations",
        "audit_events",
        "alembic_version",
    } <= tables
    assert revision == "0012"
