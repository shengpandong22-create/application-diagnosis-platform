from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class HealthCheckResult:
    target: str
    reachable: bool
    status_code: int | None
    duration_ms: int
    summary: str
    error_code: str | None = None


class HealthCheckClient(Protocol):
    async def check(self, target: str) -> HealthCheckResult: ...
