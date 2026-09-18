import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr
from test_durability_postgres import get, process
from test_durability_postgres import redis_url as test_redis_url
from test_runtime_postgres import client as runtime_client
from test_runtime_postgres import database_url as runtime_database_url
from test_runtime_postgres import post_run, setup_version

from forge.core.config import Settings
from forge.db.session import Database
from forge.model_router import health
from forge.model_router.base import ModelFailure, ModelResult
from forge.model_router.factory import adapter_for
from forge.model_router.gemini import GeminiAdapter
from forge.model_router.openai import OpenAIAdapter

client = runtime_client
database_url = runtime_database_url
redis_url = test_redis_url
pytestmark = pytest.mark.integration


def configure(client):
    settings = client.app.state.settings
    settings.execution_mode = "queued"
    settings.model_backend = "routed"
    settings.openai_api_key = settings.gemini_api_key = SecretStr("test-key")
    settings.model_max_attempts = 1
    return settings


def response(model="gemini-3.1-flash-lite", **changes):
    return ModelResult(
        text="Hello",
        actual_model=model,
        input_tokens=1000,
        output_tokens=100,
        finish_reason="STOP",
        **changes,
    )


@pytest.mark.parametrize(
    "failure,fallback",
    [
        ("MODEL_PROVIDER_UNAVAILABLE", True),
        ("MODEL_TIMEOUT", True),
        ("MODEL_AUTH_FAILED", False),
        ("MODEL_REQUEST_REJECTED", False),
    ],
)
def test_ordered_fallback_persists_across_workers(
    client, database_url, redis_url, monkeypatch, failure, fallback
):
    settings = configure(client)
    headers, version = setup_version(
        client, primary_model="gpt-4.1-mini", fallback_models=["gemini-3.1-flash-lite"]
    )
    called = []

    async def fail(self, request):
        called.append(request.model)
        raise ModelFailure(failure)

    async def succeed(self, request):
        called.append(request.model)
        return response()

    monkeypatch.setattr(OpenAIAdapter, "generate", fail)
    monkeypatch.setattr(GeminiAdapter, "generate", succeed)
    run = post_run(client, headers, version).json()
    process(database_url, redis_url, run, adapter_for(settings))
    value = get(client, headers, run)
    assert value["status"] == (
        "RETRYING" if fallback else "TIMED_OUT" if failure == "MODEL_TIMEOUT" else "FAILED"
    )
    if fallback:
        # Fresh worker and fresh router must restore the selected candidate.
        process(database_url, redis_url, run, adapter_for(settings))
        value = get(client, headers, run)
        assert value["status"] == "COMPLETED", value
        assert value["execution_config"]["requested_model"] == "gpt-4.1-mini"
        assert value["execution_config"]["active_model"] == "gemini-3.1-flash-lite"
        assert value["total_cost"] is None
        assert value["execution_config"]["cost_summary"] == {
            "known_cost_usd": "0.00040000",
            "unknown_calls": 1,
            "status": "INCOMPLETE",
        }
        assert called == ["gpt-4.1-mini", "gemini-3.1-flash-lite"]
        events = client.get(f"/api/v1/runs/{run['id']}/events", headers=headers).json()
        assert sum(e["event_type"] == "MODEL_FALLBACK" for e in events) == 1
    else:
        assert called == ["gpt-4.1-mini"]


def test_budget_stops_before_tools_and_prices_are_pinned(
    client, database_url, redis_url, monkeypatch
):
    settings = configure(client)
    headers, original = setup_version(client)
    tool = client.post("/api/v1/tools", headers=headers, json={"name": "create_ticket"}).json()
    version = client.post(
        f"/api/v1/agents/{original['agent_id']}/versions",
        headers=headers,
        json={
            "version": "budget",
            "goal": "test",
            "instructions": "test",
            "primary_model": "gpt-4.1-mini",
            "tool_version_ids": [tool["id"]],
            "budget_config": {"max_cost_per_run_usd": "0.000001"},
        },
    ).json()

    async def generate(self, request):
        return response(
            "gpt-4.1-mini",
            tool_requests=[
                {
                    "id": "a",
                    "name": "create_ticket",
                    "arguments": {"customer_id": "cust_001", "title": "x", "details": "x"},
                }
            ],
        )

    monkeypatch.setattr(OpenAIAdapter, "generate", generate)
    run = post_run(client, headers, version).json()
    settings.model_prices = {
        "gpt-4.1-mini": {"provider": "openai", "input": "0", "cached": "0", "output": "0"}
    }
    process(database_url, redis_url, run, adapter_for(settings))
    value = get(client, headers, run)
    assert value["error_code"] == "BUDGET_EXCEEDED", value
    assert value["tool_calls_count"] == 0
    assert value["total_cost"] == "0.00056000"


def test_no_provider_switch_after_tool_execution(client, database_url, redis_url, monkeypatch):
    settings = configure(client)
    headers, original = setup_version(client)
    tool = client.post("/api/v1/tools", headers=headers, json={"name": "create_ticket"}).json()
    version = client.post(
        f"/api/v1/agents/{original['agent_id']}/versions",
        headers=headers,
        json={
            "version": "pinned",
            "goal": "test",
            "instructions": "test",
            "primary_model": "gpt-4.1-mini",
            "fallback_models": ["gemini-3.1-flash-lite"],
            "tool_version_ids": [tool["id"]],
        },
    ).json()

    async def generate(self, request):
        if request.exchanges:
            raise ModelFailure("MODEL_PROVIDER_UNAVAILABLE")
        return response(
            "gpt-4.1-mini",
            tool_requests=[
                {
                    "id": "a",
                    "name": "create_ticket",
                    "arguments": {"customer_id": "cust_001", "title": "x", "details": "x"},
                }
            ],
        )

    async def forbidden(self, request):
        pytest.fail("Must not switch provider after a successful tool request")

    monkeypatch.setattr(OpenAIAdapter, "generate", generate)
    monkeypatch.setattr(GeminiAdapter, "generate", forbidden)
    run = post_run(client, headers, version).json()
    process(database_url, redis_url, run, adapter_for(settings))
    value = get(client, headers, run)
    assert value["status"] == "FAILED" and value["tool_calls_count"] == 1, value
    assert value["model_calls_count"] == 2


def test_circuit_persistence_probe_fencing_and_scope(client, database_url):
    headers, _ = setup_version(client)
    other, _ = setup_version(client)
    org = UUID(headers["X-Organization-ID"])

    async def exercise():
        db = Database(Settings(_env_file=None, database_url=database_url))
        try:
            async with db.sessions() as session:
                for _ in range(3):
                    generation = await health.acquire(session, org, "openai", "gpt-test", 1)
                    await health.observe(
                        session, org, "openai", "gpt-test", generation, "MODEL_TIMEOUT"
                    )
                    await session.commit()
            async with db.sessions() as session:
                assert await health.acquire(session, org, "openai", "gpt-test", 1) is None
                row = await health.locked(session, org, "openai", "gpt-test")
                assert row.state == "OPEN"
                row.open_until = datetime.now(UTC) - timedelta(seconds=1)
                await session.commit()
                probe = await health.acquire(session, org, "openai", "gpt-test", 1)
                await session.commit()
            async with db.sessions() as session:
                assert await health.acquire(session, org, "openai", "gpt-test", 1) is None
                await health.observe(session, org, "openai", "gpt-test", 0, None)
                row = await health.locked(session, org, "openai", "gpt-test")
                assert row.state == "HALF_OPEN"
                await health.observe(session, org, "openai", "gpt-test", probe, None)
                await session.commit()
                assert await health.acquire(session, org, "openai", "gpt-test", 1) is not None
                await session.commit()
        finally:
            await db.close()

    asyncio.run(exercise())
    items = client.get("/api/v1/models/health", headers=headers).json()
    assert len(items) == 1 and items[0]["state"] == "CLOSED"
    assert items[0]["failures"] == 0
    assert client.get("/api/v1/models/health", headers=other).json() == []


def test_open_circuit_skips_paid_call_and_uses_fallback(
    client, database_url, redis_url, monkeypatch
):
    settings = configure(client)
    headers, version = setup_version(
        client, primary_model="gpt-4.1-mini", fallback_models=["gemini-3.1-flash-lite"]
    )
    attempts = []

    async def fail(self, request):
        attempts.append(request.model)
        raise ModelFailure("MODEL_PROVIDER_UNAVAILABLE")

    async def succeed(self, request):
        return response()

    monkeypatch.setattr(OpenAIAdapter, "generate", fail)
    monkeypatch.setattr(GeminiAdapter, "generate", succeed)
    for _ in range(4):
        headers["Idempotency-Key"] = str(uuid4())
        run = post_run(client, headers, version).json()
        process(database_url, redis_url, run, adapter_for(settings))
        assert get(client, headers, run)["status"] == "RETRYING"
        process(database_url, redis_url, run, adapter_for(settings))
        assert get(client, headers, run)["status"] == "COMPLETED"
    assert len(attempts) == 3
    calls = client.get(f"/api/v1/runs/{run['id']}/model-calls", headers=headers).json()
    assert calls[0]["status"] == "SKIPPED"
    assert calls[0]["error_type"] == "MODEL_CIRCUIT_OPEN"
    assert calls[0]["estimated_cost"] == "0.00000000"
    assert get(client, headers, run)["total_cost"] == "0.00040000"


def test_exhausted_fallback_list_terminates(client, database_url, redis_url, monkeypatch):
    settings = configure(client)
    headers, version = setup_version(
        client, primary_model="gpt-4.1-mini", fallback_models=["gemini-3.1-flash-lite", "gpt-last"]
    )
    attempts = []

    async def fail(self, request):
        attempts.append(request.model)
        raise ModelFailure("MODEL_PROVIDER_UNAVAILABLE")

    monkeypatch.setattr(OpenAIAdapter, "generate", fail)
    monkeypatch.setattr(GeminiAdapter, "generate", fail)
    run = post_run(client, headers, version).json()
    for _ in range(4):
        process(database_url, redis_url, run, adapter_for(settings))
    assert get(client, headers, run)["status"] == "FAILED"
    assert attempts == ["gpt-4.1-mini", "gemini-3.1-flash-lite", "gpt-last"]


def test_incomplete_response_does_not_fallback(client, database_url, redis_url, monkeypatch):
    settings = configure(client)
    headers, version = setup_version(
        client, primary_model="gpt-4.1-mini", fallback_models=["gemini-3.1-flash-lite"]
    )

    async def blocked(self, request):
        return ModelResult(text="", actual_model="gpt-4.1-mini", finish_reason="SAFETY")

    monkeypatch.setattr(OpenAIAdapter, "generate", blocked)
    run = post_run(client, headers, version).json()
    process(database_url, redis_url, run, adapter_for(settings))
    value = get(client, headers, run)
    assert value["error_code"] == "MODEL_RESPONSE_INCOMPLETE"
    assert value["model_calls_count"] == 1
