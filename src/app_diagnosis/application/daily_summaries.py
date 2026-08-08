from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from app_diagnosis.application.diagnoses import DiagnosisApplicationService
from app_diagnosis.application.services import ServiceProfileNotFound
from app_diagnosis.domain.incident import Incident
from app_diagnosis.domain.service_profile import ServiceProfile
from app_diagnosis.ports.incident_repository import IncidentRepository
from app_diagnosis.ports.service_profile_repository import ServiceProfileRepository


@dataclass(frozen=True, slots=True)
class DailyServiceSummary:
    service: ServiceProfile
    day: date
    incident_count: int
    new_fingerprint_count: int
    occurrence_count: int
    high_frequency_incidents: tuple[Incident, ...]
    waiting_for_confirmation: int
    rejected: int


class DailyServiceSummaryService:
    def __init__(
        self,
        *,
        services: ServiceProfileRepository,
        incidents: IncidentRepository,
        diagnoses: DiagnosisApplicationService,
    ) -> None:
        self._services = services
        self._incidents = incidents
        self._diagnoses = diagnoses

    async def generate(self, service_id: UUID, day: date) -> DailyServiceSummary:
        service = await self._services.get(service_id)
        if service is None:
            raise ServiceProfileNotFound(str(service_id))
        start = datetime.combine(day, time.min, tzinfo=UTC)
        end = start + timedelta(days=1)
        incidents = tuple(
            item
            for item in await self._incidents.list(service_id=service_id)
            if start <= item.last_seen_at < end
        )
        diagnoses = tuple(
            item
            for item in await self._diagnoses.list_by_service(service_id)
            if start <= item.created_at < end
        )
        return DailyServiceSummary(
            service=service,
            day=day,
            incident_count=len(incidents),
            new_fingerprint_count=len(
                {item.fingerprint for item in incidents if start <= item.first_seen_at < end}
            ),
            occurrence_count=sum(item.occurrence_count for item in incidents),
            high_frequency_incidents=tuple(
                sorted(incidents, key=lambda item: item.occurrence_count, reverse=True)[:5]
            ),
            waiting_for_confirmation=sum(
                item.status.value == "waiting_for_confirmation" for item in diagnoses
            ),
            rejected=sum(item.status.value == "rejected" for item in diagnoses),
        )


def render_daily_markdown(summary: DailyServiceSummary) -> str:
    lines = [
        f"# {summary.service.name} · {summary.day.isoformat()} 诊断摘要",
        "",
        f"- 环境: `{summary.service.environment}`",
        f"- Incident 数量: `{summary.incident_count}`",
        f"- 新指纹数量: `{summary.new_fingerprint_count}`",
        f"- 总发生次数: `{summary.occurrence_count}`",
        f"- 待人工确认: `{summary.waiting_for_confirmation}`",
        f"- 已驳回: `{summary.rejected}`",
        "",
        "## 高频 Incident",
        "",
    ]
    lines += [
        f"- `{item.id}` · occurrences={item.occurrence_count} · "
        f"fingerprint=`{item.fingerprint[:16]}`"
        for item in summary.high_frequency_incidents
    ] or ["- 无"]
    return "\n".join(lines) + "\n"
