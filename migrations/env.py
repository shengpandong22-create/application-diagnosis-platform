import asyncio
from logging.config import fileConfig
from os import getenv
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_engine_from_config

from app_diagnosis.adapters.persistence.audit_models import AuditEventRecord  # noqa: F401
from app_diagnosis.adapters.persistence.confirmation_models import ConfirmationRecord  # noqa: F401
from app_diagnosis.adapters.persistence.evidence_models import EvidenceRecord  # noqa: F401
from app_diagnosis.adapters.persistence.incident_models import (  # noqa: F401
    DeduplicationKeyRecord,
    IncidentRecord,
)
from app_diagnosis.adapters.persistence.knowledge_models import KnowledgeEntryRecord  # noqa: F401
from app_diagnosis.adapters.persistence.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = getenv("APP_DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

target_metadata = Base.metadata


def ensure_sqlite_parent_exists() -> None:
    url = make_url(config.get_main_option("sqlalchemy.url"))
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        return
    Path(url.database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: object) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    ensure_sqlite_parent_exists()
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
