import asyncio
from contextlib import asynccontextmanager, suppress
from typing import Protocol
from uuid import uuid4

from redis.asyncio import Redis


class Queue(Protocol):
    async def publish(self, run_id: str) -> None: ...
    async def receive(self) -> str | None: ...
    async def close(self) -> None: ...


class RedisQueue:
    def __init__(self, url: str, *, prefix="forge", lease_seconds=15):
        self.redis = Redis.from_url(
            url, decode_responses=True, socket_timeout=3, socket_connect_timeout=3
        )
        self.prefix, self.lease_seconds = prefix, lease_seconds

    async def publish(self, run_id):
        # Notifications are bounded hints; PostgreSQL polling recovers lost/trimmed messages.
        async with self.redis.pipeline(transaction=True) as pipe:
            await (
                pipe.lpush(f"{self.prefix}:ready", run_id)
                .ltrim(f"{self.prefix}:ready", 0, 9999)
                .execute()
            )

    async def receive(self):
        value = await self.redis.brpop(f"{self.prefix}:ready", timeout=1)
        return value[1] if value else None

    async def close(self):
        await self.redis.aclose()

    @asynccontextmanager
    async def lease(self, run_id):
        key, token = f"{self.prefix}:run:{run_id}", uuid4().hex
        acquired = await self.redis.set(key, token, nx=True, ex=self.lease_seconds)
        if not acquired:
            yield False
            return

        # PostgreSQL session lock remains the execution fence if renewal is lost.
        async def renew():
            while True:
                await asyncio.sleep(self.lease_seconds / 3)
                if not await self.redis.eval(
                    "if redis.call('get',KEYS[1]) == ARGV[1] then "
                    "return redis.call('expire',KEYS[1],ARGV[2]) else return 0 end",
                    1,
                    key,
                    token,
                    self.lease_seconds,
                ):
                    return

        task = asyncio.create_task(renew())
        try:
            yield True
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await task
            with suppress(Exception):
                await self.redis.eval(
                    "if redis.call('get',KEYS[1]) == ARGV[1] then "
                    "return redis.call('del',KEYS[1]) else return 0 end",
                    1,
                    key,
                    token,
                )
