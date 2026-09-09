"""Run with python -m forge.durability.worker. No HTTP request owns execution."""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from forge.core.config import Settings
from forge.db.session import Database
from forge.durability.engine import DurableEngine
from forge.durability.models import RunOutbox
from forge.durability.queue import RedisQueue
from forge.model_router.fake import FakeAdapter
from forge.model_router.gemini import GeminiAdapter
from forge.runtime.models import Run
from forge.runtime.state import TERMINAL, RunState

logger = logging.getLogger("forge.worker")


def adapter_for(settings):
    if settings.model_backend == "fake":
        return FakeAdapter()
    return GeminiAdapter(
        settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None
    )


class Worker:
    def __init__(self, database, queue, adapter):
        self.database, self.queue, self.adapter = database, queue, adapter

    async def publish(self):
        async with self.database.sessions() as session:
            rows = list(
                await session.scalars(
                    select(RunOutbox)
                    .where(
                        RunOutbox.completed.is_(False),
                        RunOutbox.published_at.is_(None),
                        RunOutbox.available_at <= datetime.now(UTC),
                    )
                    .order_by(RunOutbox.available_at)
                    .limit(50)
                    .with_for_update(skip_locked=True)
                )
            )
            for row in rows:
                await self.queue.publish(str(row.run_id))
                row.published_at = datetime.now(UTC)
            # If killed after Redis publish but before commit, publishing again is harmless.
            await session.commit()

    async def process(self, run_id):
        # Session-level PostgreSQL ownership spans every transaction on this same connection.
        # A lost Redis lease cannot let another executor write under a different connection.
        lock_id = int.from_bytes(run_id.bytes[:8], "big", signed=True)
        async with self.database.engine.connect() as connection:
            acquired = await connection.scalar(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": lock_id}
            )
            await connection.commit()
            if not acquired:
                return False
            try:
                async with self.queue.lease(str(run_id)) as leased:
                    if not leased:
                        return False
                    async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                        task = await session.get(RunOutbox, run_id)
                        if task is None or task.completed or task.available_at > datetime.now(UTC):
                            return False
                        run = await session.get(Run, run_id)
                        if RunState(run.status) in TERMINAL:
                            task.completed = True
                            await session.commit()
                            return True
                        await DurableEngine(session, self.adapter).execute(run)
                        return True
            finally:
                if not connection.invalidated:
                    await connection.rollback()
                    await connection.execute(
                        text("SELECT pg_advisory_unlock(:key)"), {"key": lock_id}
                    )
                    await connection.commit()

    async def tick(self):
        await self.publish()
        async with self.database.sessions() as session:
            ids = list(
                await session.scalars(
                    select(RunOutbox.run_id)
                    .where(
                        RunOutbox.completed.is_(False), RunOutbox.available_at <= datetime.now(UTC)
                    )
                    .order_by(RunOutbox.available_at)
                    .limit(20)
                )
            )
        for run_id in ids:
            await self.process(run_id)
        return bool(ids)


async def main():
    settings = Settings()
    database = Database(settings)
    queue = RedisQueue(settings.redis_url.get_secret_value())
    worker = Worker(database, queue, adapter_for(settings))
    try:
        while True:
            try:
                await worker.tick()
                # Notifications reduce idle waiting; due retries still come from PostgreSQL.
                await queue.receive()
            except Exception:
                # Credentials, provider payloads, and raw database exceptions stay out of logs.
                logger.error("WORKER_CYCLE_FAILED; durable work remains pending")
            await asyncio.sleep(settings.worker_poll_seconds)
    finally:
        await queue.close()
        await database.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
