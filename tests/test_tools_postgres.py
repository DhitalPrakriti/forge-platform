import asyncio
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from test_runtime_postgres import client as runtime_client
from test_runtime_postgres import database_url as runtime_database_url
from test_runtime_postgres import post_run, setup_version

from forge.api.runs import get_adapter
from forge.core.config import Settings
from forge.db.session import Database
from forge.model_router.fake import FakeAdapter
from forge.runtime.models import Run
from forge.tools import builtins
from forge.tools.hub import ToolHub
from forge.tools.models import DemoTicket, Tool

client = runtime_client
database_url = runtime_database_url
pytestmark = pytest.mark.integration


def setup_tools(
    client, names=("lookup_customer", "lookup_transactions", "create_ticket"), **config
):
    headers, initial = setup_version(client)
    tools = []
    for name in names:
        response = client.post("/api/v1/tools", headers=headers, json={"name": name})
        assert response.status_code == 201, response.text
        tools.append(response.json())
    response = client.post(
        f"/api/v1/agents/{initial['agent_id']}/versions",
        headers=headers,
        json={
            "version": "with-tools",
            "goal": "Demo",
            "instructions": "Use permitted tools.",
            "primary_model": "local-test-model",
            "tool_version_ids": [tool["id"] for tool in tools],
            **config,
        },
    )
    assert response.status_code == 201, response.text
    return headers, response.json(), tools


def ticket_count(database_url, organization_id):
    async def count():
        db = Database(Settings(_env_file=None, database_url=database_url))
        try:
            async with db.sessions() as session:
                return await session.scalar(
                    select(func.count())
                    .select_from(DemoTicket)
                    .where(
                        DemoTicket.organization_id == UUID(organization_id),
                    )
                )
        finally:
            await db.close()

    return asyncio.run(count())


@pytest.mark.parametrize("name", ["lookup_customer", "lookup_transactions", "create_ticket"])
def test_model_tool_model_loop_records_exact_revision(client, database_url, name):
    headers, version, tools = setup_tools(client)
    arguments = (
        '{"customer_id":"cust_001"}'
        if name != "create_ticket"
        else ('{"customer_id":"cust_001","title":" Help ","details":"Explain my plan."}')
    )
    response = post_run(client, headers, version, f"/tool {name} {arguments}")
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["status"] == "COMPLETED", run
    assert run["model_calls_count"] == 2 and run["tool_calls_count"] == 1
    assert run["current_step"] == 2
    assert "[FAKE MODEL" in run["output"]["message"]
    path = f"/api/v1/runs/{run['id']}"
    calls = client.get(path + "/tool-calls", headers=headers).json()
    assert len(calls) == 1
    call = calls[0]
    assert call["status"] == "COMPLETED" and call["decision"] == "ALLOW"
    assert call["tool_id"] == next(t["id"] for t in tools if t["name"] == name)
    assert call["result"]["demo"] is True
    assert call["idempotency_key"] == f"forge:{run['id']}:{call['id']}"
    events = client.get(path + "/events", headers=headers).json()
    assert [e["sequence_number"] for e in events] == list(range(len(events)))
    assert "WAITING_FOR_TOOL" in [e["event_type"] for e in events]
    assert events[-1]["event_type"] == "COMPLETED"
    model_calls = client.get(path + "/model-calls", headers=headers).json()
    assert len(model_calls) == 2 and all(c["status"] == "COMPLETED" for c in model_calls)
    assert post_run(client, headers, version, f"/tool {name} {arguments}").json()["id"] == run["id"]
    assert ticket_count(database_url, headers["X-Organization-ID"]) == (
        1 if name == "create_ticket" else 0
    )
    if name == "create_ticket":
        assert call["arguments"]["title"] == "Help"


@pytest.mark.parametrize(
    "message, expected",
    [
        ('/tool issue_refund {"amount":5000}', "TOOL_NOT_ALLOWED"),
        (
            '/tool create_ticket {"customer_id":"cust_001","title":"X","details":"X"}',
            "TOOL_NOT_ALLOWED",
        ),
        ('/tool lookup_customer {"customer_id":123}', "TOOL_VALIDATION_FAILED"),
        (
            '/tool lookup_customer {"customer_id":"cust_001","authorization":"ALLOW"}',
            "TOOL_VALIDATION_FAILED",
        ),
        ("/tool lookup_customer []", "TOOL_VALIDATION_FAILED"),
        ('/tool lookup_customer {"customer_id":NaN}', "TOOL_VALIDATION_FAILED"),
        ('/tool lookup_customer {"customer_id":"cust_999"}', "DEMO_CUSTOMER_NOT_FOUND"),
    ],
)
def test_invalid_or_unpermitted_requests_never_create_ticket(
    client, database_url, message, expected
):
    headers, version, _ = setup_tools(client, names=("lookup_customer",))
    response = post_run(client, headers, version, message)
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["status"] == "FAILED" and run["error_code"] == expected, run
    assert run["output"] is None and run["model_calls_count"] == 1
    call = client.get(f"/api/v1/runs/{run['id']}/tool-calls", headers=headers).json()[0]
    assert call["result"] is None and call["error"]["code"] == expected
    assert ticket_count(database_url, headers["X-Organization-ID"]) == 0


def test_registration_is_idempotent_scoped_and_not_arbitrary_code(client):
    headers, version, tools = setup_tools(client)
    other, other_version = setup_version(client)
    first = tools[0]
    again = client.post("/api/v1/tools", headers=headers, json={"name": first["name"]})
    assert again.status_code == 200 and again.json() == first
    assert len(client.get("/api/v1/tools?limit=1", headers=headers).json()) == 1
    assert client.get("/api/v1/tools", headers=other).json() == []
    assert client.get(f"/api/v1/tools/{first['id']}", headers=other).status_code == 404
    assert (
        client.patch(
            f"/api/v1/tools/{first['id']}", headers=other, json={"status": "INACTIVE"}
        ).status_code
        == 404
    )
    assert (
        client.post("/api/v1/tools", headers=headers, json={"name": "arbitrary_python"}).status_code
        == 422
    )
    assert (
        client.patch(
            f"/api/v1/tools/{first['id']}", headers=headers, json={"input_schema": {}}
        ).status_code
        == 422
    )
    for ids in ([first["id"]], [str(uuid4())]):
        rejected = client.post(
            f"/api/v1/agents/{other_version['agent_id']}/versions",
            headers=other,
            json={
                "version": "x",
                "goal": "x",
                "instructions": "x",
                "primary_model": "x",
                "tool_version_ids": ids,
            },
        )
        assert rejected.status_code == 404 and rejected.json()["error"]["code"] == "TOOL_NOT_FOUND"
    path = f"/api/v1/runs/{post_run(client, headers, version).json()['id']}/tool-calls"
    assert client.get(path, headers=other).status_code == 404
    client.app.state.settings.environment = "production"
    assert client.get("/api/v1/tools", headers=headers).status_code == 503


def test_tool_disabled_after_model_request_is_denied(client, database_url):
    headers, version, tools = setup_tools(client)

    class Adapter(FakeAdapter):
        async def generate(self, request):
            response = await asyncio.to_thread(
                client.patch,
                f"/api/v1/tools/{tools[2]['id']}",
                headers=headers,
                json={"status": "INACTIVE"},
            )
            assert response.status_code == 200
            return await super().generate(request)

    client.app.dependency_overrides[get_adapter] = lambda: Adapter()
    result = post_run(
        client,
        headers,
        version,
        '/tool create_ticket {"customer_id":"cust_001","title":"x","details":"x"}',
    ).json()
    assert result["error_code"] == "POLICY_DENIED", result
    assert ticket_count(database_url, headers["X-Organization-ID"]) == 0


@pytest.mark.parametrize(
    "failure, code",
    [
        ("output", "TOOL_OUTPUT_INVALID"),
        ("exception", "TOOL_INTERNAL_ERROR"),
        ("timeout", "TOOL_TIMEOUT"),
    ],
)
def test_local_effect_rolls_back_when_handler_or_output_fails(
    client, database_url, monkeypatch, failure, code
):
    headers, version, _ = setup_tools(
        client, runtime_config={"max_steps": 4, "max_runtime_seconds": 1}
    )

    async def handler(*args):
        await builtins.execute_builtin(*args)
        if failure == "exception":
            raise RuntimeError("private secret diagnostics")
        if failure == "timeout":
            await asyncio.sleep(2)
        return {"invalid": True}

    monkeypatch.setattr("forge.tools.hub.execute_builtin", handler)
    result = post_run(
        client,
        headers,
        version,
        '/tool create_ticket {"customer_id":"cust_001","title":"x","details":"x"}',
    )
    assert result.status_code == 201, result.text
    assert result.json()["error_code"] == code, result.text
    assert "private secret" not in result.text
    assert ticket_count(database_url, headers["X-Organization-ID"]) == 0


def test_step_and_batch_limits_stop_before_side_effect(client, database_url):
    headers, version, _ = setup_tools(
        client, runtime_config={"max_steps": 1, "max_runtime_seconds": 10}
    )
    result = post_run(
        client,
        headers,
        version,
        '/tool create_ticket {"customer_id":"cust_001","title":"x","details":"x"}',
    ).json()
    assert result["error_code"] == "STEP_LIMIT_EXCEEDED"
    assert result["tool_calls_count"] == 0
    headers, version, _ = setup_tools(client)

    class Adapter(FakeAdapter):
        async def generate(self, request):
            response = await super().generate(
                replace(request, message='/tool lookup_customer {"customer_id":"cust_001"}')
            )
            return replace(response, tool_requests=response.tool_requests * 9)

    client.app.dependency_overrides[get_adapter] = lambda: Adapter()
    result = post_run(client, headers, version).json()
    assert result["error_code"] == "TOOL_CALL_LIMIT_EXCEEDED"
    assert result["tool_calls_count"] == 0
    assert ticket_count(database_url, headers["X-Organization-ID"]) == 0


def test_database_guards_and_tool_result_reuse(client, database_url):
    headers, version, tools = setup_tools(client)
    result = post_run(
        client,
        headers,
        version,
        '/tool create_ticket {"customer_id":"cust_001","title":"x","details":"x"}',
    ).json()
    call = client.get(f"/api/v1/runs/{result['id']}/tool-calls", headers=headers).json()[0]

    async def verify():
        db = Database(Settings(_env_file=None, database_url=database_url))
        try:
            for statement in [
                "UPDATE tools SET description='changed' WHERE id=:id",
                "DELETE FROM tools WHERE id=:id",
                "UPDATE agent_tools SET tool_id=:id WHERE tool_id=:id",
            ]:
                async with db.sessions() as session:
                    with pytest.raises(DBAPIError):
                        await session.execute(text(statement), {"id": tools[0]["id"]})
                    await session.rollback()
            async with db.sessions() as session:
                run = await session.get(Run, UUID(result["id"]))
                bound = list(
                    await session.scalars(
                        select(Tool).where(Tool.organization_id == run.organization_id)
                    )
                )
                existing = await ToolHub(session).execute(
                    run,
                    UUID(call["model_call_id"]),
                    0,
                    {"name": "create_ticket", "arguments": call["arguments"]},
                    bound,
                    5,
                )
                assert str(existing.id) == call["id"]
                assert existing.result == call["result"]
        finally:
            await db.close()

    asyncio.run(verify())
    assert ticket_count(database_url, headers["X-Organization-ID"]) == 1
