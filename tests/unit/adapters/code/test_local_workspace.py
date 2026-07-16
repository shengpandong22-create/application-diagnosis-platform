from pathlib import Path

import pytest

from app_diagnosis.adapters.code import LocalCodeRepository
from app_diagnosis.domain.code_workspace import CodeWorkspace


async def test_search_and_bounded_read(tmp_path: Path) -> None:
    source = tmp_path / "src" / "OrderService.java"
    source.parent.mkdir()
    source.write_text("class OrderService {\n  void createOrder() {}\n}\n", encoding="utf-8")
    repository = LocalCodeRepository(CodeWorkspace(name="lab", root=tmp_path))

    matches = await repository.search("createOrder", limit=5)
    excerpt = await repository.read(matches[0].path, start_line=1, end_line=3)

    assert matches[0].path == "src/OrderService.java"
    assert "createOrder" in excerpt.content


async def test_read_rejects_path_escape(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "secret.java"
    outside.write_text("secret", encoding="utf-8")
    repository = LocalCodeRepository(CodeWorkspace(name="lab", root=workspace))

    with pytest.raises(PermissionError):
        await repository.read("../secret.java", start_line=1, end_line=1)


async def test_search_ignores_build_output(tmp_path: Path) -> None:
    generated = tmp_path / "target" / "Secret.java"
    generated.parent.mkdir()
    generated.write_text("class Secret {}", encoding="utf-8")
    repository = LocalCodeRepository(CodeWorkspace(name="lab", root=tmp_path))

    assert await repository.search("Secret", limit=5) == ()
