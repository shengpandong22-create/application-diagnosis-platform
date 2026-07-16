from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CodeWorkspace:
    name: str
    root: Path
    revision: str = "working-tree"
    allowed_extensions: frozenset[str] = frozenset(
        {".java", ".yml", ".yaml", ".properties", ".xml"}
    )

    def __post_init__(self) -> None:
        root = self.root.expanduser().resolve(strict=True)
        if not root.is_dir():
            raise ValueError("code workspace root must be a directory")
        if not self.name.strip():
            raise ValueError("code workspace name must not be blank")
        object.__setattr__(self, "root", root)
