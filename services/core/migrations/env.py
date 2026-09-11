import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config

from nevolium_core.config import settings
from nevolium_core.db import Base
from nevolium_core import autonomy_models, command_models, document_models, memory_models, models, tool_models, ui_models  # noqa: F401
from nevolium_core import work_capacity  # noqa: F401

migration_url = os.environ.get("NEVOLIUM_MIGRATION_DATABASE_URL") or settings.database_url
config = context.config
config.set_main_option("sqlalchemy.url", migration_url.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=migration_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()
        if connection.scalar(text("SELECT current_user")) == "nevolium_migrator":
            connection.execute(text("REVOKE ALL ON TABLE public.alembic_version FROM nevolium_app"))


async def run_async_migrations() -> None:
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
