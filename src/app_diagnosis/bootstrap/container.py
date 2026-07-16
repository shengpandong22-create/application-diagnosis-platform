from pathlib import Path

from app_diagnosis.adapters.knowledge import JsonKnowledgeSeedLoader, SqliteKnowledgeSearch
from app_diagnosis.adapters.llm import OpenAICompatibleChatClient
from app_diagnosis.adapters.persistence import Database, SqlAlchemyAgentExecutionRepository
from app_diagnosis.adapters.persistence.evidence_store import SqlAlchemyEvidenceStore
from app_diagnosis.adapters.redaction import LocalRuleRedactor
from app_diagnosis.agent.policies import EvidenceCitationPolicy
from app_diagnosis.agent.runtime import AgentBudget, ToolLoopRunner
from app_diagnosis.agent.strategies import GenericApplicationErrorStrategy
from app_diagnosis.application import (
    DiagnosisApplicationService,
    DiagnosisReportService,
    KnowledgeApplicationService,
)
from app_diagnosis.bootstrap.settings import Settings
from app_diagnosis.ports.llm import LLMClient, LLMTransportError
from app_diagnosis.tools import DiagnosticToolRegistry
from app_diagnosis.tools.knowledge_search import KnowledgeSearchTool


class UnconfiguredLLMClient(LLMClient):
    async def complete(self, request):
        raise LLMTransportError("APP_LLM_MODEL is not configured")


def build_diagnosis_service(
    *,
    settings: Settings,
    database: Database,
    llm_client: LLMClient | None = None,
) -> tuple[DiagnosisApplicationService, LLMClient]:
    resolved_llm = llm_client or _build_llm(settings)
    executions = SqlAlchemyAgentExecutionRepository(database.session_factory)
    registry = DiagnosticToolRegistry()
    knowledge = SqliteKnowledgeSearch(
        database.session_factory,
        JsonKnowledgeSeedLoader(Path(settings.knowledge_directory)),
    )
    registry.register(KnowledgeSearchTool(knowledge))
    redactor = LocalRuleRedactor()
    runner = ToolLoopRunner(
        llm_client=resolved_llm,
        registry=registry,
        execution_repository=executions,
        evidence_store=SqlAlchemyEvidenceStore(database.session_factory, redactor),
        citation_policy=EvidenceCitationPolicy(),
    )
    service = DiagnosisApplicationService(
        session_factory=database.session_factory,
        runner=runner,
        executions=executions,
        strategy=GenericApplicationErrorStrategy(),
        budget=AgentBudget(
            max_rounds=settings.agent_max_rounds,
            max_tool_calls=settings.agent_max_tool_calls,
            total_timeout_seconds=settings.agent_total_timeout_seconds,
        ),
        max_input_log_bytes=settings.input_log_max_bytes,
        redactor=redactor,
    )
    return service, resolved_llm


def _build_llm(settings: Settings) -> LLMClient:
    if not settings.llm_model.strip():
        return UnconfiguredLLMClient()
    return OpenAICompatibleChatClient(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key.get_secret_value(),
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        response_format_mode=settings.resolved_llm_response_format,
    )


def build_knowledge_service(database: Database) -> KnowledgeApplicationService:
    return KnowledgeApplicationService(database.session_factory, LocalRuleRedactor())


def build_report_service(database: Database) -> DiagnosisReportService:
    return DiagnosisReportService(
        database.session_factory,
        SqlAlchemyAgentExecutionRepository(database.session_factory),
    )
