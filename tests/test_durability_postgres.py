import asyncio
import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from test_runtime_postgres import client as runtime_client
from test_runtime_postgres import database_url as runtime_database_url
from test_runtime_postgres import setup_version

from forge.core.config import Settings
from forge.db.session import Database
from forge.durability.models import RunOutbox
from forge.durability.queue import RedisQueue
from forge.durability.worker import Worker
from forge.model_router.base import ModelFailure
from forge.model_router.fake import FakeAdapter
from forge.tools.models import DemoTicket

client = runtime_client
database_url = runtime_database_url
pytestmark = pytest.mark.integration


@pytest.fixture
def redis_url():
    url = os.environ.get("FORGE_TEST_REDIS_URL")
    if not url:
        pytest.skip("Set FORGE_TEST_REDIS_URL to a disposable Redis server")
    return url


def submit(client, message="Hi", tool=None, **changes):
    client.app.state.settings.execution_mode = "queued"
    client.app.state.settings.retry_base_seconds = 0.01
    headers, initial = setup_version(client)
    version = initial
    if tool:
        item = client.post("/api/v1/tools", headers=headers, json={"name": tool}).json()
        policies = []
        if tool == "issue_refund":
            policies = [client.post("/api/v1/policies", headers=headers).json()["id"]]
        response = client.post(
            f"/api/v1/agents/{initial['agent_id']}/versions",
            headers=headers,
            json={
                "version": "tools",
                "goal": "demo",
                "instructions": "demo",
                "primary_model": "fake",
                "tool_version_ids": [item["id"]],
                "policy_version_ids": policies,
                **changes,
            },
        )
        assert response.status_code == 201, response.text
        version = response.json()
    response = client.post(
        "/api/v1/runs",
        headers=headers,
        json={"agent_version_id": version["id"], "input": {"message": message}},
    )
    assert response.status_code == 202, response.text
    assert response.json()["status"] == "QUEUED"
    return headers, response.json()


async def resources(database_url, redis_url, adapter=None):
    db = Database(Settings(_env_file=None, database_url=database_url))
    queue = RedisQueue(redis_url, prefix="test:" + uuid4().hex, lease_seconds=2)
    return db, queue, Worker(db, queue, adapter or FakeAdapter())


def process(database_url, redis_url, run, adapter=None):
    async def execute():
        db, queue, worker = await resources(database_url, redis_url, adapter)
        try:
            return await worker.process(UUID(run["id"]))
        finally:
            await queue.close()
            await db.close()

    return asyncio.run(execute())


def get(client, headers, run):
    return client.get("/api/v1/runs/" + run["id"], headers=headers).json()


def test_queued_duplicate_delivery_and_notification_loss(client, database_url, redis_url):
    headers, run = submit(
        client,
        '/tool create_ticket {"customer_id":"cust_001","title":"x","details":"x"}',
        tool="create_ticket",
    )

    async def exercise():
        db, queue, worker = await resources(database_url, redis_url)
        try:
            await worker.publish()
            await queue.redis.delete(queue.prefix + ":ready")
            # Redis notification loss does not remove committed work.
            await worker.process(UUID(run["id"]))
            await worker.process(UUID(run["id"]))
            async with db.sessions() as s:
                count = await s.scalar(
                    select(func.count())
                    .select_from(DemoTicket)
                    .where(DemoTicket.organization_id == UUID(headers["X-Organization-ID"]))
                )
                assert count == 1
                outbox = await s.get(RunOutbox, UUID(run["id"]))
                assert outbox.completed
        finally:
            await queue.close()
            await db.close()

    asyncio.run(exercise())
    value = get(client, headers, run)
    assert value["status"] == "COMPLETED", value
    assert value["model_calls_count"] == 2 and value["tool_calls_count"] == 1


def test_retry_backoff_and_permanent_failure(client, database_url, redis_url):
    class Transient(FakeAdapter):
        calls = 0

        async def generate(self, request):
            self.calls += 1
            if self.calls < 3:
                raise ModelFailure("MODEL_PROVIDER_UNAVAILABLE")
            return await super().generate(request)

    headers, run = submit(client)
    adapter = Transient()
    for _ in range(3):
        process(database_url, redis_url, run, adapter)
        if get(client, headers, run)["status"] == "RETRYING":
            import time

            time.sleep(0.05)
    value = get(client, headers, run)
    assert value["status"] == "COMPLETED" and value["model_calls_count"] == 3, value

    class Permanent(FakeAdapter):
        async def generate(self, request):
            raise ModelFailure("MODEL_AUTH_FAILED")

    headers, run = submit(client)
    process(database_url, redis_url, run, Permanent())
    value = get(client, headers, run)
    assert value["status"] == "FAILED" and value["model_calls_count"] == 1, value
    retry = client.post(
        f"/api/v1/runs/{run['id']}/retry", headers={**headers, "Idempotency-Key": uuid4().hex}
    )
    assert retry.status_code == 202, retry.text
    assert retry.json()["retry_of_run_id"] == run["id"]


def test_cancel_queued_and_scope(client, database_url, redis_url):
    headers, run = submit(client)
    other, _ = setup_version(client)
    assert client.post(f"/api/v1/runs/{run['id']}/cancel", headers=other).status_code == 404
    assert client.post(f"/api/v1/runs/{run['id']}/cancel", headers=headers).status_code == 202
    process(database_url, redis_url, run)
    value = get(client, headers, run)
    assert value["status"] == "CANCELLED" and value["model_calls_count"] == 0, value
    process(database_url, redis_url, run)
    assert get(client, headers, run) == value


def test_redis_lease_loss_cannot_create_second_executor(client, database_url, redis_url):
    headers, run = submit(client)

    async def exercise():
        started, release = asyncio.Event(), asyncio.Event()

        class Slow(FakeAdapter):
            async def generate(self, request):
                started.set()
                await release.wait()
                return await super().generate(request)

        db, queue, worker = await resources(database_url, redis_url, Slow())
        try:
            task = asyncio.create_task(worker.process(UUID(run["id"])))
            await asyncio.wait_for(started.wait(), 5)
            await queue.redis.delete(f"{queue.prefix}:run:{run['id']}")
            assert await worker.process(UUID(run["id"])) is False
            release.set()
            await task
        finally:
            await queue.close()
            await db.close()

    asyncio.run(exercise())
    assert get(client, headers, run)["model_calls_count"] == 1


def test_cancel_during_model_prevents_tool_execution(client, database_url, redis_url):
    headers, run = submit(
        client,
        '/tool create_ticket {"customer_id":"cust_001","title":"x","details":"x"}',
        tool="create_ticket",
    )

    class Cancel(FakeAdapter):
        async def generate(self, request):
            response = await asyncio.to_thread(
                client.post, f"/api/v1/runs/{run['id']}/cancel", headers=headers
            )
            assert response.status_code == 202
            return await super().generate(request)

    process(database_url, redis_url, run, Cancel())
    value = get(client, headers, run)
    assert value["status"] == "CANCELLED" and value["tool_calls_count"] == 0, value


@pytest.mark.parametrize(
    "boundary", ["model_inflight", "model_saved", "effect_uncommitted", "effect_committed"]
)
def test_sigkill_worker_recovery_never_duplicates_ticket(
    client, database_url, redis_url, tmp_path, boundary
):
    import subprocess
    import sys
    import time

    headers, run = submit(
        client,
        '/tool create_ticket {"customer_id":"cust_001","title":"crash","details":"recover"}',
        tool="create_ticket",
    )
    marker = tmp_path / "boundary"
    prefix = "crash:" + uuid4().hex
    child = subprocess.Popen(
        [sys.executable, "tests/worker_crash_driver.py"],
        env={
            **os.environ,
            "FORGE_TEST_DATABASE_URL": database_url,
            "FORGE_TEST_REDIS_URL": redis_url,
            "FORGE_TEST_RUN_ID": run["id"],
            "FORGE_TEST_PREFIX": prefix,
            "FORGE_TEST_BOUNDARY": boundary,
            "FORGE_TEST_MARKER": str(marker),
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 10
        while not marker.exists() and time.monotonic() < deadline and child.poll() is None:
            time.sleep(0.03)
        assert marker.exists(), "Worker did not reach the requested crash boundary"
        child.kill()
        child.wait(timeout=5)
        time.sleep(2.1)  # Old Redis lease expires; PostgreSQL releases ownership on disconnect.

        async def restart():
            db = Database(Settings(_env_file=None, database_url=database_url))
            queue = RedisQueue(redis_url, prefix=prefix, lease_seconds=2)
            try:
                worker = Worker(db, queue, FakeAdapter())
                await worker.process(UUID(run["id"]))
                if boundary == "model_inflight":
                    await asyncio.sleep(0.05)
                    await worker.process(UUID(run["id"]))
                async with db.sessions() as s:
                    count = await s.scalar(
                        select(func.count())
                        .select_from(DemoTicket)
                        .where(DemoTicket.organization_id == UUID(headers["X-Organization-ID"]))
                    )
                    assert count == 1
            finally:
                await queue.close()
                await db.close()

        asyncio.run(restart())
        result = get(client, headers, run)
        assert result["status"] == "COMPLETED", result
        assert result["tool_calls_count"] == 1
        assert result["model_calls_count"] == (3 if boundary == "model_inflight" else 2)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        child.stderr.close()


def test_queued_approval_and_background_expiry(client, database_url, redis_url):
    import time

    from pydantic import SecretStr

    token = "disposable-test-reviewer-token-1234567"
    client.app.state.settings.approval_reviewer_token = SecretStr(token)
    client.app.state.settings.approval_reviewer_id = uuid4()
    headers, run = submit(
        client,
        '/tool issue_refund {"customer_id":"cust_001","amount_usd":"425.00"}',
        tool="issue_refund",
    )
    process(database_url, redis_url, run)
    assert get(client, headers, run)["status"] == "WAITING_FOR_APPROVAL"
    approval = client.get(f"/api/v1/approvals?run_id={run['id']}", headers=headers).json()[0]
    response = client.post(
        f"/api/v1/approvals/{approval['id']}/approve",
        headers={**headers, "Authorization": "Bearer " + token},
        json={"reason": "Verified"},
    )
    assert response.status_code == 200, response.text
    # No explicit resume HTTP call: the decision enqueues continuation atomically.
    process(database_url, redis_url, run)
    assert get(client, headers, run)["status"] == "COMPLETED"
    headers, run = submit(
        client,
        '/tool issue_refund {"customer_id":"cust_001","amount_usd":"425.00"}',
        tool="issue_refund",
        runtime_config={"max_steps": 4, "max_runtime_seconds": 1},
    )
    process(database_url, redis_url, run)
    assert get(client, headers, run)["status"] == "WAITING_FOR_APPROVAL"
    time.sleep(1.1)
    process(database_url, redis_url, run)
    value = get(client, headers, run)
    assert value["status"] == "CANCELLED" and value["error_code"] == "APPROVAL_EXPIRED", value


def test_retry_cap_and_runtime_timeout(client, database_url, redis_url):
    import time

    class Broken(FakeAdapter):
        async def generate(self, request):
            raise ModelFailure("MODEL_PROVIDER_UNAVAILABLE")

    headers, run = submit(client)
    for _ in range(4):
        process(database_url, redis_url, run, Broken())
        time.sleep(0.05)
    value = get(client, headers, run)
    assert value["status"] == "FAILED" and value["model_calls_count"] == 3, value
    headers, run = submit(
        client, tool="lookup_customer", runtime_config={"max_steps": 4, "max_runtime_seconds": 1}
    )
    time.sleep(1.1)
    process(database_url, redis_url, run)
    value = get(client, headers, run)
    assert value["status"] == "TIMED_OUT" and value["model_calls_count"] == 0, value


def test_outbox_rollback_and_publish_failure_keep_work_durable(client, database_url, redis_url):
    headers, run = submit(client)

    async def exercise():
        db, queue, worker = await resources(database_url, redis_url)
        try:

            class Unavailable:
                async def publish(self, run_id):
                    raise ConnectionError("unavailable")

            with pytest.raises(ConnectionError):
                await Worker(db, Unavailable(), FakeAdapter()).publish()
            async with db.sessions() as s:
                row = await s.get(RunOutbox, UUID(run["id"]))
                assert row.published_at is None and not row.completed
            await worker.publish()
            await worker.process(UUID(run["id"]))
        finally:
            await queue.close()
            await db.close()

    asyncio.run(exercise())
    assert get(client, headers, run)["status"] == "COMPLETED"


def test_failed_model_after_ticket_cannot_retry_side_effect(client, database_url, redis_url):
    class FailAfterEffect(FakeAdapter):
        async def generate(self, request):
            if request.exchanges:
                raise ModelFailure("MODEL_AUTH_FAILED")
            return await super().generate(request)

    headers, run = submit(
        client,
        '/tool create_ticket {"customer_id":"cust_001","title":"x","details":"x"}',
        tool="create_ticket",
    )
    process(database_url, redis_url, run, FailAfterEffect())
    assert get(client, headers, run)["status"] == "FAILED"
    retry = client.post(
        f"/api/v1/runs/{run['id']}/retry", headers={**headers, "Idempotency-Key": uuid4().hex}
    )
    assert (
        retry.status_code == 409
        and retry.json()["error"]["code"] == "RETRY_REQUIRES_RECONCILIATION"
    )


def test_incompatible_checkpoint_fails_visibly(client, database_url, redis_url):
    from forge.approvals.models import RunCheckpoint

    headers, run = submit(client)

    async def insert():
        db = Database(Settings(_env_file=None, database_url=database_url))
        try:
            async with db.sessions() as s:
                s.add(
                    RunCheckpoint(
                        run_id=UUID(run["id"]),
                        state_version=999,
                        checkpoint_schema_version=999,
                        runtime_build_version="unknown",
                        last_event_sequence=999,
                        runtime_state={"phase": "MODEL"},
                    )
                )
                await s.commit()
        finally:
            await db.close()

    asyncio.run(insert())
    process(database_url, redis_url, run)
    value = get(client, headers, run)
    assert value["status"] == "FAILED" and value["error_code"] == "CHECKPOINT_INCOMPATIBLE", value
