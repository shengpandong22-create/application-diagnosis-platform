import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config


def test_diagnosis_plan_migration_creates_table(tmp_path: Path) -> None:
    database_path = tmp_path / "plan-migration.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path.as_posix()}")

    command.upgrade(config, "head")
    command.check(config)

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info('diagnosis_plans')")
        }
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]

    assert revision == "0011"
    assert {
        "id",
        "diagnosis_id",
        "agent_run_id",
        "summary",
        "hypotheses_json",
        "steps_json",
        "expected_evidence_json",
        "allowed_tools_json",
        "status",
        "created_at",
    } == columns
