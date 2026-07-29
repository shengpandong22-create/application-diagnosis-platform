from uuid import UUID

from app_diagnosis.adapters.persistence.service_profile_repository import (
    ServiceProfileAlreadyExists,
    SqlAlchemyServiceProfileRepository,
)
from app_diagnosis.application.evidence_diagnoses import (
    EvidenceAwareDiagnosisApplicationService as DiagnosisApplicationService,
)
from app_diagnosis.domain.diagnosis import DiagnosisCase
from app_diagnosis.domain.service_profile import ServiceProfile


class ServiceProfileNotFound(LookupError):
    pass


class ServiceProfileConflict(RuntimeError):
    pass


class ServiceCatalogApplicationService:
    def __init__(
        self,
        *,
        services: SqlAlchemyServiceProfileRepository,
        diagnoses: DiagnosisApplicationService,
    ) -> None:
        self._services = services
        self._diagnoses = diagnoses

    async def create(
        self,
        *,
        name: str,
        environment: str,
        description: str | None,
        code_workspace_path: str | None,
        log_directory: str | None,
        config_workspace_path: str | None,
        health_targets: tuple[str, ...],
        tags: tuple[str, ...],
    ) -> ServiceProfile:
        """创建服务档案，只保存用户显式传入的元数据。

        3C-1 不扫描路径、不校验远程健康检查，也不动态改工具上下文。
        """
        service = ServiceProfile.create(
            name=name,
            environment=environment,
            description=description,
            code_workspace_path=code_workspace_path,
            log_directory=log_directory,
            config_workspace_path=config_workspace_path,
            health_targets=health_targets,
            tags=tags,
        )
        try:
            await self._services.add(service)
        except ServiceProfileAlreadyExists as error:
            raise ServiceProfileConflict(str(error)) from error
        return service

    async def get(self, service_id: UUID) -> ServiceProfile:
        service = await self._services.get(service_id)
        if service is None:
            raise ServiceProfileNotFound(str(service_id))
        return service

    async def list(self) -> tuple[ServiceProfile, ...]:
        return await self._services.list()

    async def create_diagnosis(
        self,
        service_id: UUID,
        *,
        title: str,
        symptom: str,
        submitted_log: str | None,
    ) -> DiagnosisCase:
        """基于服务创建诊断，并在 DiagnosisCase 上记录 service_id。

        第一版只建立关联，不把 service 路径动态注入工具；这样普通诊断和现有
        Container 装配都保持稳定。
        """
        await self.get(service_id)
        return await self._diagnoses.create(
            title=title,
            symptom=symptom,
            submitted_log=submitted_log,
            service_id=service_id,
        )
