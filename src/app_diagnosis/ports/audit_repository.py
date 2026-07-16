from typing import Protocol

from app_diagnosis.domain.audit import AuditEvent


class AuditRepository(Protocol):
    async def add(self, event: AuditEvent) -> None: ...

    async def list_for_target(self, target_type: str, target_id: str) -> tuple[AuditEvent, ...]: ...
