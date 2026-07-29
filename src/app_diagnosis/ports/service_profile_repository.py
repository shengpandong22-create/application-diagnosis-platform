from typing import Protocol
from uuid import UUID

from app_diagnosis.domain.service_profile import ServiceProfile


class ServiceProfileRepository(Protocol):
    async def add(self, service: ServiceProfile) -> None: ...

    async def get(self, service_id: UUID) -> ServiceProfile | None: ...

    async def list(self) -> tuple[ServiceProfile, ...]: ...
