import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config


def test_phase2_evidence_constraints_upgrade_from_0007(tmp_path: Path) -> None:
    database_path = tmp_path / "phase2-migration.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path.as_posix()}")
    command.upgrade(config, "0007")
    command.upgrade(config, "0008")
    with sqlite3.connect(database_path) as connection:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        table_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='evidence'"
        ).fetchone()[0]
    assert revision == "0008"
    assert "config_excerpt" in table_sql
    assert "health_check" in table_sql
    assert "local_log" in table_sql
