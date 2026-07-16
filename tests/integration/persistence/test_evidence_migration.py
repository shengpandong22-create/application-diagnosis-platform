import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config


def test_evidence_migration_schema_and_downgrade(tmp_path: Path) -> None:
    database_path = tmp_path / "evidence-migration.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path.as_posix()}")

    command.upgrade(config, "head")
    with sqlite3.connect(database_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info('evidence')")}
        foreign_keys = list(connection.execute("PRAGMA foreign_key_list('evidence')"))
        indexes = list(connection.execute("PRAGMA index_list('evidence')"))

    assert columns == {
        "id",
        "diagnosis_id",
        "type",
        "source",
        "source_reference",
        "content",
        "content_hash",
        "reliability",
        "metadata_json",
        "redaction_status",
        "created_at",
    }
    assert any(row[2] == "diagnoses" and row[6] == "CASCADE" for row in foreign_keys)
    assert any(row[1] == "sqlite_autoindex_evidence_2" and row[2] == 1 for row in indexes)

    command.downgrade(config, "0002")
    with sqlite3.connect(database_path) as connection:
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='evidence'"
        ).fetchone()
    assert table is None
