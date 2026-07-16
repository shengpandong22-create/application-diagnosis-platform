import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config


def test_upgrade_from_empty_database(tmp_path: Path) -> None:
    database_path = tmp_path / "migration.db"
    config = Config("alembic.ini")
    config.set_main_option(
        "sqlalchemy.url",
        f"sqlite+aiosqlite:///{database_path.as_posix()}",
    )

    command.upgrade(config, "head")
    command.check(config)

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        columns = {row[1] for row in connection.execute("PRAGMA table_info('diagnoses')")}
    assert {"alembic_version", "diagnoses"} <= tables
    assert {
        "id",
        "title",
        "problem_type",
        "status",
        "symptom",
        "submitted_log",
        "conclusion_json",
        "version",
        "created_at",
        "updated_at",
    } == columns
