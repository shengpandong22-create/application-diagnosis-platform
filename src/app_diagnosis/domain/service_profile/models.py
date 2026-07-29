"""最小服务目录领域模型。

Phase 3C-1 只保存用户显式配置的服务元数据，不扫描本机目录，也不动态改变工具
访问范围。真正按服务驱动工具上下文会放到 3C-2。
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PureWindowsPath
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class ServiceProfile:
    id: UUID
    name: str
    description: str | None
    environment: str
    code_workspace_path: str | None
    log_directory: str | None
    config_workspace_path: str | None
    health_targets: tuple[str, ...]
    tags: tuple[str, ...]
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("service name must not be blank")
        if not self.environment.strip():
            raise ValueError("service environment must not be blank")
        for field_name in ("created_at", "updated_at"):
            value = getattr(self, field_name)
            if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
                raise ValueError(f"{field_name} must be timezone-aware UTC")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not be earlier than created_at")
        for value in (
            self.code_workspace_path,
            self.log_directory,
            self.config_workspace_path,
        ):
            if value is not None:
                _validate_explicit_path(value)

    @classmethod
    def create(
        cls,
        *,
        name: str,
        environment: str,
        description: str | None = None,
        code_workspace_path: str | None = None,
        log_directory: str | None = None,
        config_workspace_path: str | None = None,
        health_targets: tuple[str, ...] = (),
        tags: tuple[str, ...] = (),
        service_id: UUID | None = None,
        now: datetime | None = None,
    ) -> "ServiceProfile":
        occurred_at = now or datetime.now(UTC)
        return cls(
            id=service_id or uuid4(),
            name=name.strip(),
            description=description.strip() if description else None,
            environment=environment.strip(),
            code_workspace_path=code_workspace_path.strip() if code_workspace_path else None,
            log_directory=log_directory.strip() if log_directory else None,
            config_workspace_path=(
                config_workspace_path.strip() if config_workspace_path else None
            ),
            health_targets=tuple(item.strip() for item in health_targets if item.strip()),
            tags=tuple(sorted({item.strip() for item in tags if item.strip()})),
            created_at=occurred_at,
            updated_at=occurred_at,
        )


def _validate_explicit_path(value: str) -> None:
    if not value.strip():
        raise ValueError("service path must not be blank")
    path = PureWindowsPath(value)
    if ".." in path.parts:
        raise ValueError("service path must not contain parent traversal")
