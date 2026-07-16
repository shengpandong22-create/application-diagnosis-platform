from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CodeMatch:
    path: str
    line: int
    preview: str


@dataclass(frozen=True, slots=True)
class CodeExcerpt:
    workspace: str
    revision: str
    path: str
    start_line: int
    end_line: int
    content: str


class CodeRepository(Protocol):
    async def search(self, query: str, *, limit: int) -> tuple[CodeMatch, ...]: ...

    async def read(self, path: str, *, start_line: int, end_line: int) -> CodeExcerpt: ...
