import asyncio

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from forge.agents import models  # noqa: F401 -- register domain metadata
from forge.approvals import models as approval_models  # noqa: F401
from forge.core.config import Settings
from forge.db.base import Base
from forge.durability import models as durability_models  # noqa: F401
from forge.runtime import models as runtime_models  # noqa: F401 -- register runtime metadata
from forge.tools import models as tool_models  # noqa: F401 -- register tool metadata


def migrate(connection):
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


async def online():
    engine = create_async_engine(
        Settings().database_url.get_secret_value(),
        poolclass=pool.NullPool,
        hide_parameters=True,
    )
    try:
        async with engine.connect() as connection:
            await connection.run_sync(migrate)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    context.configure(
        url=Settings().database_url.get_secret_value(),
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(online())
