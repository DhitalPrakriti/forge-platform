import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from forge.core.errors import DomainError


async def check_database(engine: AsyncEngine, timeout_seconds: float) -> None:
    try:
        async with asyncio.timeout(timeout_seconds):
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise DomainError("DATABASE_UNAVAILABLE", "Database is unavailable.", 503) from exc
