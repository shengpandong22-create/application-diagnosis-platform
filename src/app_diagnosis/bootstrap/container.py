"""应用依赖装配入口。

这个模块把 Settings、数据库、LLM Client、工具、Strategy、ApplicationService
组装起来。业务规则不应该写在这里；这里只决定“使用哪些实现”和“如何接线”。
后续替换模型、数据库、工具 Adapter 或 Strategy 时，优先从这里调整装配关系。
"""

from pathlib import Path

from app_diagnosis.adapters.code import LocalCodeRepository
from app_diagnosis.adapters.config import LocalConfigRepository
from app_diagnosis.adapters.health import HttpHealthCheckClient
from app_diagnosis.adapters.knowledge import JsonKnowledgeSeedLoader, SqliteKnowledgeSearch
from app_diagnosis.adapters.llm import OpenAICompatibleChatClient
from app_diagnosis.adapters.logs import LocalLogFileReader
from app_diagnosis.adapters.persistence import Database, SqlAlchemyAgentExecutionRepository
from app_diagnosis.adapters.persistence.diagnosis_plan_repository import (
    SqlAlchemyDiagnosisPlanRepository,
)
from app_diagnosis.adapters.persistence.evidence_store import SqlAlchemyEvidenceStore
from app_diagnosis.adapters.persistence.service_profile_repository import (
    SqlAlchemyServiceProfileRepository,
)
from app_diagnosis.adapters.redaction import LocalRuleRedactor
from app_diagnosis.agent.policies import EvidenceCitationPolicy
from app_diagnosis.agent.runtime import AgentBudget, ToolLoopRunner
from app_diagnosis.agent.strategies import (
    ApplicationErrorStrategy,
    ConfigurationStrategy,
    DiagnosisStrategyRouter,
    GenericApplicationErrorStrategy,
    NetworkStrategy,
)
from app_diagnosis.application import (
    DiagnosisApplicationService,
    DiagnosisPlanService,
    DiagnosisReportService,
    DiagnosisTraceService,
    KnowledgeApplicationService,
    ServiceCatalogApplicationService,
)
from app_diagnosis.application.diagnoses import build_service_tool_resource_resolver
from app_diagnosis.bootstrap.settings import Settings
from app_diagnosis.domain.code_workspace import CodeWorkspace
from app_diagnosis.ports.llm import LLMClient, LLMTransportError
from app_diagnosis.tools import DiagnosticToolRegistry
from app_diagnosis.tools.code import CodeReadTool, CodeSearchTool
from app_diagnosis.tools.config import ConfigReadTool
from app_diagnosis.tools.health import HealthCheckTool
from app_diagnosis.tools.knowledge_search import KnowledgeSearchTool
from app_diagnosis.tools.log_search import LogSearchTool


class UnconfiguredLLMClient(LLMClient):
    """未配置真实模型时的占位 LLM。

    这样应用可以正常启动，自动测试仍然可以通过注入 Fake LLM 运行；
    但如果误触发真实模型调用，会得到明确的配置错误。
    """

    async def complete(self, request):
        raise LLMTransportError("APP_LLM_MODEL is not configured")


def build_diagnosis_service(
    *,
    settings: Settings,
    database: Database,
    llm_client: LLMClient | None = None,
) -> tuple[DiagnosisApplicationService, LLMClient]:
    """构建诊断主服务，并返回服务本身和最终使用的 LLM Client。

    这里集中完成三件事：注册当前环境启用的工具，组装 ToolLoopRunner，
    再把 Runner、StrategyRouter、预算和脱敏器交给 ApplicationService。
    后续新增工具时，通常需要在这里接入 Adapter、注册 Tool，并把启用状态
    传给 Strategy options。
    """
    resolved_llm = llm_client or _build_llm(settings)
    executions = SqlAlchemyAgentExecutionRepository(database.session_factory)
    registry = DiagnosticToolRegistry()
    knowledge = SqliteKnowledgeSearch(
        database.session_factory,
        JsonKnowledgeSeedLoader(Path(settings.knowledge_directory)),
    )
    registry.register(KnowledgeSearchTool(knowledge))
    code_tools_enabled = bool(settings.code_workspace_path.strip())
    if code_tools_enabled:
        # 源码工具只允许访问配置的 workspace，不扫描用户电脑上的任意目录。
        code = LocalCodeRepository(
            CodeWorkspace(
                name=settings.code_workspace_name,
                root=Path(settings.code_workspace_path),
            )
        )
    else:
        code = None
    registry.register(CodeSearchTool(code))
    registry.register(CodeReadTool(code))
    redactor = LocalRuleRedactor()
    config_tools_enabled = bool(settings.config_workspace_path.strip())
    if config_tools_enabled:
        registry.register(
            ConfigReadTool(
                LocalConfigRepository(Path(settings.config_workspace_path)),
                redactor,
            )
        )
    else:
        registry.register(ConfigReadTool(None, redactor))
    log_tools_enabled = bool(settings.log_directory.strip())
    if log_tools_enabled:
        # 日志工具只读取配置目录内的日志文件，避免 Agent 任意读取本机文件。
        registry.register(LogSearchTool(LocalLogFileReader(Path(settings.log_directory)), redactor))
    else:
        registry.register(LogSearchTool(None, redactor))
    health_tools_enabled = bool(settings.health_targets)
    if health_tools_enabled:
        registry.register(HealthCheckTool(HttpHealthCheckClient(settings.health_targets, redactor)))
    else:
        registry.register(HealthCheckTool(None))
    runner = ToolLoopRunner(
        llm_client=resolved_llm,
        registry=registry,
        execution_repository=executions,
        evidence_store=SqlAlchemyEvidenceStore(database.session_factory, redactor),
        citation_policy=EvidenceCitationPolicy(),
        plan_repository=SqlAlchemyDiagnosisPlanRepository(database.session_factory),
    )
    strategy_options = {
        "code_tools_enabled": code_tools_enabled,
        "config_tools_enabled": config_tools_enabled,
        "log_tools_enabled": log_tools_enabled,
        "health_tools_enabled": health_tools_enabled,
    }
    fallback_strategy = GenericApplicationErrorStrategy(**strategy_options)
    service = DiagnosisApplicationService(
        session_factory=database.session_factory,
        runner=runner,
        executions=executions,
        strategy=fallback_strategy,
        strategy_router=DiagnosisStrategyRouter(
            application=ApplicationErrorStrategy(**strategy_options),
            network=NetworkStrategy(**strategy_options),
            configuration=ConfigurationStrategy(**strategy_options),
            fallback=fallback_strategy,
        ),
        budget=AgentBudget(
            max_rounds=settings.agent_max_rounds,
            max_tool_calls=settings.agent_max_tool_calls,
            total_timeout_seconds=settings.agent_total_timeout_seconds,
        ),
        max_input_log_bytes=settings.input_log_max_bytes,
        redactor=redactor,
        tool_resource_resolver=build_service_tool_resource_resolver(
            session_factory=database.session_factory,
            redactor=redactor,
            default_code_workspace_name=settings.code_workspace_name,
            default_code_workspace_path=settings.code_workspace_path,
            default_log_directory=settings.log_directory,
            default_config_workspace_path=settings.config_workspace_path,
            default_health_targets=settings.health_targets,
        ),
    )
    return service, resolved_llm


def _build_llm(settings: Settings) -> LLMClient:
    """根据 Settings 创建真实 LLM Client；未配置模型时返回占位实现。"""
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
    """构建知识库管理用例服务。"""
    return KnowledgeApplicationService(database.session_factory, LocalRuleRedactor())


def build_plan_service(database: Database) -> DiagnosisPlanService:
    """构建诊断计划只读服务。"""
    return DiagnosisPlanService(database.session_factory)


def build_service_catalog(
    database: Database,
    diagnosis_service: DiagnosisApplicationService,
) -> ServiceCatalogApplicationService:
    """构建最小服务目录用例服务。"""
    return ServiceCatalogApplicationService(
        services=SqlAlchemyServiceProfileRepository(database.session_factory),
        diagnoses=diagnosis_service,
    )


def build_report_service(database: Database) -> DiagnosisReportService:
    """构建诊断报告只读服务。"""
    return DiagnosisReportService(
        database.session_factory,
        SqlAlchemyAgentExecutionRepository(database.session_factory),
    )


def build_trace_service(database: Database) -> DiagnosisTraceService:
    """构建 Agent Trace 只读服务。"""
    return DiagnosisTraceService(
        database.session_factory,
        SqlAlchemyAgentExecutionRepository(database.session_factory),
    )
