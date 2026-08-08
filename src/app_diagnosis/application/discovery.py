import asyncio
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_diagnosis.adapters.persistence.audit_repository import SqlAlchemyAuditRepository
from app_diagnosis.application.evidence_diagnoses import (
    EvidenceAwareDiagnosisApplicationService,
)
from app_diagnosis.application.incidents import IncidentApplicationService
from app_diagnosis.domain.audit import AuditEvent
from app_diagnosis.domain.incident import DiagnosisTriggerPolicy, Incident
from app_diagnosis.ports.evidence_store import EvidenceCandidate, EvidenceStore
from app_diagnosis.ports.incident_repository import IncidentRepository
from app_diagnosis.ports.log_event_source import DiscoveredLogEvent, LogEventSource


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    incident: Incident
    diagnosis_id: UUID | None
    triggered: bool
    trigger_reason: str
    termination_reason: str | None = None
    error_code: str | None = None


class ActiveDiscoveryApplicationService:
    """编排确定性发现与 Agent 诊断；模型失败不会抹除已写入的事实。"""

    def __init__(
        self,
        *,
        sessions: async_sessionmaker[AsyncSession],
        incidents: IncidentApplicationService,
        incident_repository: IncidentRepository,
        diagnoses: EvidenceAwareDiagnosisApplicationService,
        evidence_store: EvidenceStore,
        trigger_policy: DiagnosisTriggerPolicy,
        max_tool_output_bytes: int,
    ) -> None:
        self._sessions = sessions
        self._incidents = incidents
        self._incident_repository = incident_repository
        self._diagnoses = diagnoses
        self._evidence_store = evidence_store
        self._trigger_policy = trigger_policy
        self._max_tool_output_bytes = max_tool_output_bytes
        self._lock = asyncio.Lock()

    async def discover(self, source: LogEventSource) -> tuple[DiscoveryResult, ...]:
        return tuple([await self.process(event) for event in await source.collect()])

    async def process(self, event: DiscoveredLogEvent) -> DiscoveryResult:
        # Phase 4C 是单机编排；锁避免同进程内聚合与关联之间的竞态。
        async with self._lock:
            aggregation = await self._incidents.ingest(
                service_id=event.service_id,
                environment=event.environment,
                occurred_at=event.occurred_at,
                severity=event.severity,
                message=event.message,
                exception_type=event.exception_type,
                stack_frames=event.stack_frames,
                source_event_id=event.source_event_id,
            )
            current = await self._incident_repository.get(aggregation.incident.id)
            if current is None:
                raise RuntimeError("aggregated incident disappeared")
            aggregation = type(aggregation)(
                incident=current,
                is_novel=aggregation.is_novel,
                duplicate_event=aggregation.duplicate_event,
            )
            decision = self._trigger_policy.decide(aggregation)
            if not decision.should_trigger:
                return DiscoveryResult(
                    incident=current,
                    diagnosis_id=current.diagnosis_id,
                    triggered=False,
                    trigger_reason=decision.reason,
                )

            diagnosis = await self._diagnoses.create(
                service_id=event.service_id,
                title=f"Auto-discovered {event.exception_type}",
                symptom=(
                    f"Incident {current.id} detected for service {event.service_id}; "
                    f"fingerprint={current.fingerprint[:12]}"
                ),
                submitted_log=current.sample_message,
            )
            current = await self._incident_repository.link_diagnosis(current.id, diagnosis.id)
            await self._evidence_store.add_candidates(
                diagnosis.id,
                (
                    EvidenceCandidate(
                        type="user_statement",
                        source="local_service",
                        source_reference=event.source_reference or f"incident:{current.id}",
                        content=(
                            f"Automatically triggered from incident {current.id}; "
                            f"fingerprint version {current.fingerprint_version}; "
                            f"occurrence count {current.occurrence_count}."
                        ),
                        metadata={
                            "incident_id": str(current.id),
                            "automatic_trigger": True,
                            "trigger_reason": decision.reason,
                        },
                    ),
                ),
            )
            async with self._sessions.begin() as session:
                await SqlAlchemyAuditRepository(session).add(
                    AuditEvent.create(
                        actor="active-discovery",
                        action="diagnosis.auto_triggered",
                        target_type="diagnosis",
                        target_id=str(diagnosis.id),
                        correlation_id=str(current.id),
                        summary=f"Diagnosis triggered by incident {current.id}",
                    )
                )

        try:
            run = await self._diagnoses.run(
                diagnosis.id,
                actor="active-discovery",
                environment=event.environment,
                correlation_id=str(current.id),
                max_tool_output_bytes=self._max_tool_output_bytes,
            )
            return DiscoveryResult(
                incident=current,
                diagnosis_id=diagnosis.id,
                triggered=True,
                trigger_reason=decision.reason,
                termination_reason=run.termination_reason.value,
            )
        except Exception as error:
            # AgentRun/ToolRun 由 Runner 自己持久化；这里返回安全错误码以便后续重放检查。
            return DiscoveryResult(
                incident=current,
                diagnosis_id=diagnosis.id,
                triggered=True,
                trigger_reason=decision.reason,
                error_code=type(error).__name__,
            )
