"""Subprocess-only crash harness. Never imported by application code."""

import asyncio
import os
from pathlib import Path
from uuid import UUID

from forge.core.config import Settings
from forge.db.session import Database
from forge.durability.engine import DurableEngine
from forge.durability.queue import RedisQueue
from forge.durability.worker import Worker
from forge.model_router.fake import FakeAdapter
from forge.tools import hub


async def pause():
    await asyncio.to_thread(Path(os.environ["FORGE_TEST_MARKER"]).write_text, "boundary reached")
    await asyncio.sleep(60)


async def main():
    boundary = os.environ["FORGE_TEST_BOUNDARY"]
    original_save, original_handler, original_hub = (
        DurableEngine.save,
        hub.execute_builtin,
        hub.ToolHub.execute,
    )

    async def save(self, run, state, **kwargs):
        await original_save(self, run, state, **kwargs)
        if boundary == "model_saved" and state["phase"] == "TOOLS" and state["index"] == 0:
            await pause()

    async def handler(*args):
        result = await original_handler(*args)
        if boundary == "effect_uncommitted":
            await pause()
        return result

    async def execute(self, *args, **kwargs):
        result = await original_hub(self, *args, **kwargs)
        if boundary == "effect_committed" and result.status == "COMPLETED":
            await pause()
        return result

    class Adapter(FakeAdapter):
        async def generate(self, request):
            if boundary == "model_inflight":
                await pause()
            return await super().generate(request)

    DurableEngine.save, hub.execute_builtin, hub.ToolHub.execute = save, handler, execute
    db = Database(Settings(_env_file=None, database_url=os.environ["FORGE_TEST_DATABASE_URL"]))
    queue = RedisQueue(
        os.environ["FORGE_TEST_REDIS_URL"], prefix=os.environ["FORGE_TEST_PREFIX"], lease_seconds=2
    )
    try:
        await Worker(db, queue, Adapter()).process(UUID(os.environ["FORGE_TEST_RUN_ID"]))
    finally:
        await queue.close()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
