from pathlib import Path

import pytest

from app_diagnosis.adapters.config import LocalConfigRepository


async def test_reads_bounded_config_excerpt(tmp_path: Path) -> None:
    (tmp_path / "application.yml").write_text("server:\n  port: 8080\n", encoding="utf-8")
    excerpt = await LocalConfigRepository(tmp_path).read(
        "application.yml", start_line=1, end_line=2
    )
    assert excerpt.path == "application.yml"
    assert "port: 8080" in excerpt.content


@pytest.mark.parametrize("path", ["../secret.yml", "C:/secret.yml", "script.py"])
async def test_rejects_unsafe_config_paths(tmp_path: Path, path: str) -> None:
    with pytest.raises((PermissionError, FileNotFoundError)):
        await LocalConfigRepository(tmp_path).read(path, start_line=1, end_line=2)


async def test_rejects_excessive_line_range(tmp_path: Path) -> None:
    (tmp_path / "application.yml").write_text("key: value\n", encoding="utf-8")
    with pytest.raises(ValueError):
        await LocalConfigRepository(tmp_path).read("application.yml", start_line=1, end_line=121)
