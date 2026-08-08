import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config


def test_service_profile_migration_creates_table_and_diagnosis_link(tmp_path: Path) -> None:
    database_path = tmp_path / "service-profile-migration.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path.as_posix()}")

    command.upgrade(config, "head")
    command.check(config)

    with sqlite3.connect(database_path) as connection:
        service_columns = {
            row[1] for row in connection.execute("PRAGMA table_info('service_profiles')")
        }
        diagnosis_columns = {row[1] for row in connection.execute("PRAGMA table_info('diagnoses')")}
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]

    assert revision == "0012"
    assert {
        "id",
        "name",
        "description",
        "environment",
        "code_workspace_path",
        "log_directory",
        "config_workspace_path",
        "health_targets_json",
        "tags_json",
        "created_at",
        "updated_at",
    } == service_columns
    assert "service_id" in diagnosis_columns
