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
