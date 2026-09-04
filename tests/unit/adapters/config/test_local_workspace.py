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


def test_lists_candidate_paths_with_common_application_config_first(tmp_path: Path) -> None:
    (tmp_path / "src" / "main" / "resources").mkdir(parents=True)
    (tmp_path / "src" / "main" / "resources" / "application.yml").write_text(
        "server:\n  port: 8080\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "main" / "resources" / "custom.properties").write_text(
        "feature=true\n",
        encoding="utf-8",
    )
    (tmp_path / "target").mkdir()
    (tmp_path / "target" / "application.yml").write_text("ignored=true\n", encoding="utf-8")

    candidates = LocalConfigRepository(tmp_path).list_candidate_paths()

    assert candidates[0] == "src/main/resources/application.yml"
    assert "src/main/resources/custom.properties" in candidates
    assert "target/application.yml" not in candidates


def test_candidate_paths_ignore_directory_names_inside_workspace_only(tmp_path: Path) -> None:
    root = tmp_path / "build"
    root.mkdir()
    (root / "application.yml").write_text("server:\n  port: 8080\n", encoding="utf-8")
    (root / "target").mkdir()
    (root / "target" / "application.properties").write_text("ignored=true\n", encoding="utf-8")

    candidates = LocalConfigRepository(root).list_candidate_paths()

    assert candidates == ("application.yml",)


@pytest.mark.parametrize("path", ["../secret.yml", "C:/secret.yml", "script.py"])
async def test_rejects_unsafe_config_paths(tmp_path: Path, path: str) -> None:
    with pytest.raises((PermissionError, FileNotFoundError)):
        await LocalConfigRepository(tmp_path).read(path, start_line=1, end_line=2)


async def test_rejects_excessive_line_range(tmp_path: Path) -> None:
    (tmp_path / "application.yml").write_text("key: value\n", encoding="utf-8")
    with pytest.raises(ValueError):
        await LocalConfigRepository(tmp_path).read("application.yml", start_line=1, end_line=121)
