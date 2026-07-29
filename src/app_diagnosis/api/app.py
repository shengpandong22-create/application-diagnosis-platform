from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app_diagnosis.adapters.persistence import Database
from app_diagnosis.api.errors import install_exception_handlers
from app_diagnosis.api.middleware import install_request_context_middleware
from app_diagnosis.api.routes.diagnoses import router as diagnoses_router
from app_diagnosis.api.routes.health import router as health_router
from app_diagnosis.api.routes.knowledge import router as knowledge_router
from app_diagnosis.api.routes.plans import router as plans_router
from app_diagnosis.api.routes.reports import router as reports_router
from app_diagnosis.api.routes.services import router as services_router
from app_diagnosis.api.routes.traces import router as traces_router
from app_diagnosis.api.routes.ui import router as ui_router
from app_diagnosis.application import DiagnosisApplicationService
from app_diagnosis.bootstrap.container import (
    build_diagnosis_service,
    build_knowledge_service,
    build_plan_service,
    build_report_service,
    build_service_catalog,
    build_trace_service,
)
from app_diagnosis.bootstrap.settings import Settings, get_settings
from app_diagnosis.observability import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    database: Database = app.state.database
    await database.start()
    try:
        yield
    finally:
        llm_client = getattr(app.state, "llm_client", None)
        close = getattr(llm_client, "aclose", None)
        if close is not None:
            await close()
        await database.dispose()


def create_app(
    *,
    settings: Settings | None = None,
    database: Database | None = None,
    diagnosis_service: DiagnosisApplicationService | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    resolved_database = database or Database(resolved_settings.database_url)
    app = FastAPI(
        title="Application Diagnosis Platform",
        version="0.1.0",
        docs_url="/docs" if resolved_settings.docs_enabled else None,
        lifespan=lifespan,
    )
    if diagnosis_service is None:
        diagnosis_service, llm_client = build_diagnosis_service(
            settings=resolved_settings,
            database=resolved_database,
        )
        app.state.llm_client = llm_client
    app.state.database = resolved_database
    app.state.settings = resolved_settings
    app.state.diagnosis_service = diagnosis_service
    app.state.knowledge_service = build_knowledge_service(resolved_database)
    app.state.plan_service = build_plan_service(resolved_database)
    app.state.service_catalog = build_service_catalog(resolved_database, diagnosis_service)
    app.state.report_service = build_report_service(resolved_database)
    app.state.trace_service = build_trace_service(resolved_database)
    install_request_context_middleware(app)
    install_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(diagnoses_router)
    app.include_router(knowledge_router)
    app.include_router(plans_router)
    app.include_router(reports_router)
    app.include_router(services_router)
    app.include_router(traces_router)
    app.include_router(ui_router)
    return app


app = create_app()
