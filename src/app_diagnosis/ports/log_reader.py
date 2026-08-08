from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LogExcerpt:
    content: str
    source_reference: str
    matched_line: int


class LogReader(Protocol):
    def read_latest(self, *, relative_path: str, keyword: str) -> LogExcerpt: ...

    def query_related(
        self,
        *,
        relative_path: str,
        trace_id: str,
        started_at: datetime,
        ended_at: datetime,
        limit: int,
    ) -> tuple[LogExcerpt, ...]: ...
