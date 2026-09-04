from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ConfigExcerpt:
    path: str
    start_line: int
    end_line: int
    content: str


class ConfigRepository(Protocol):
    async def read(self, path: str, *, start_line: int, end_line: int) -> ConfigExcerpt: ...

    def list_candidate_paths(self, *, limit: int = 20) -> tuple[str, ...]: ...
