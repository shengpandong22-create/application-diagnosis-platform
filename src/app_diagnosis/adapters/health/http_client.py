from time import perf_counter
from urllib.parse import urlparse

import httpx

from app_diagnosis.ports.health_check import HealthCheckResult
from app_diagnosis.ports.redaction import Redactor


class HttpHealthCheckClient:
    _LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})

    def __init__(
        self,
        targets: dict[str, str],
        redactor: Redactor,
        *,
        timeout_seconds: float = 5.0,
    ) -> None:
        if timeout_seconds <= 0 or timeout_seconds > 5:
            raise ValueError("health timeout must be between 0 and 5 seconds")
        self._targets = {name: self._validate_url(url) for name, url in targets.items()}
        self._redactor = redactor
        self._timeout = timeout_seconds

    async def check(self, target: str) -> HealthCheckResult:
        try:
            url = self._targets[target]
        except KeyError as error:
            raise ValueError("health target is not configured") from error
        started = perf_counter()
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=False,
            ) as client:
                response = await client.get(url)
            duration = int((perf_counter() - started) * 1000)
            raw = response.text[:4096]
            safe = self._redactor.redact(raw).content
            return HealthCheckResult(
                target=target,
                reachable=True,
                status_code=response.status_code,
                duration_ms=duration,
                summary=safe,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            return HealthCheckResult(
                target=target,
                reachable=False,
                status_code=None,
                duration_ms=int((perf_counter() - started) * 1000),
                summary=type(error).__name__,
                error_code=type(error).__name__,
            )

    @classmethod
    def _validate_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme != "http" or parsed.hostname not in cls._LOOPBACK:
            raise ValueError("health targets must use http loopback URLs")
        if parsed.username or parsed.password or parsed.fragment:
            raise ValueError("health target URL contains forbidden components")
        return value
