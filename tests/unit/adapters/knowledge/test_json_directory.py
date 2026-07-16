import json
from pathlib import Path

import pytest

from app_diagnosis.adapters.knowledge import JsonDirectoryKnowledgeSearch


async def test_search_returns_explained_deterministic_matches(tmp_path: Path) -> None:
    entries = [
        {
            "id": "npe",
            "title": "NullPointerException",
            "summary": "Check the first application stack frame.",
            "error_types": ["NPE"],
            "tags": ["java"],
            "source": "test",
            "status": "confirmed",
        },
        {
            "id": "timeout",
            "title": "Timeout",
            "summary": "Check downstream latency.",
            "error_types": ["ReadTimeout"],
            "tags": ["rpc"],
            "source": "test",
            "status": "confirmed",
        },
    ]
    (tmp_path / "entries.json").write_text(json.dumps(entries), encoding="utf-8")
    search = JsonDirectoryKnowledgeSearch(tmp_path)

    matches = await search.search("java NullPointerException", limit=5)

    assert [match.entry_id for match in matches] == ["npe"]
    assert matches[0].matched_terms == ("java", "nullpointerexception")
    assert matches[0].score > 0


def test_rejects_invalid_root_and_duplicate_ids(tmp_path: Path) -> None:
    (tmp_path / "invalid.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="root must be an array"):
        JsonDirectoryKnowledgeSearch(tmp_path)

    (tmp_path / "invalid.json").unlink()
    entry = {
        "id": "same",
        "title": "title",
        "summary": "summary",
        "source": "test",
        "status": "confirmed",
    }
    (tmp_path / "duplicates.json").write_text(json.dumps([entry, entry]), encoding="utf-8")
    with pytest.raises(ValueError, match="ids must be unique"):
        JsonDirectoryKnowledgeSearch(tmp_path)


def test_rejects_oversized_file(tmp_path: Path) -> None:
    (tmp_path / "large.json").write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="size limit"):
        JsonDirectoryKnowledgeSearch(tmp_path, max_file_bytes=1)
