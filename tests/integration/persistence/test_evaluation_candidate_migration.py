import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config


def test_evaluation_candidate_migration_matches_metadata(tmp_path: Path) -> None:
    path = tmp_path / "evaluation-candidates.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{path.as_posix()}")
    command.upgrade(config, "head")
    command.check(config)
    with sqlite3.connect(path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info('evaluation_candidates')")
        }
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    assert {
        "id", "diagnosis_id", "source_action", "status", "feedback_summary",
        "expected_category", "expected_root_cause", "required_evidence_ids_json",
        "prompt_version", "created_at", "updated_at",
    } == columns
    assert revision == "0013"
