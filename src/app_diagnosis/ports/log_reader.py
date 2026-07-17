from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LogExcerpt:
    content: str
    source_reference: str
    matched_line: int


class LogReader(Protocol):
    def read_latest(self, *, relative_path: str, keyword: str) -> LogExcerpt: ...
