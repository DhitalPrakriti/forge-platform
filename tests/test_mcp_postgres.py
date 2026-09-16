from uuid import uuid4

import pytest
from pydantic import SecretStr
from test_runtime_postgres import client as runtime_client
from test_runtime_postgres import database_url as runtime_database_url
from test_runtime_postgres import post_run, setup_version

from forge.tools import mcp_client
from forge.tools.builtins import ToolFailure

client = runtime_client
database_url = runtime_database_url
pytestmark = pytest.mark.integration
REMOTE = {
    "name": "inspect",
    "description": "Inspect code without executing it",
    "inputSchema": {
        "type": "object",
        "properties": {"code": {"type": "string"}},
        "required": ["code"],
        "additionalProperties": False,
    },
}
TOKEN = "test-reviewer-token-with-at-least-32-characters"


def setup(client, monkeypatch):
    monkeypatch.setenv(
        "FORGE_MCP_SERVERS", '{"code":{"url":"https://example.com/mcp","token":"secret-test"}}'
    )

    async def discover(key):
        assert key == "code"
        return [REMOTE]

    monkeypatch.setattr(mcp_client, "discover", discover)
    headers, version = setup_version(client)
    catalog = client.get("/api/v1/mcp/servers/code/tools", headers=headers)
    assert catalog.status_code == 200, catalog.text
    payload = {
        "server": "code",
        "remote_name": "inspect",
        "fingerprint": catalog.json()[0]["fingerprint"],
    }
    response = client.post("/api/v1/mcp/tools", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    tool = response.json()
    assert "secret-test" not in response.text
    assert (
        client.post("/api/v1/mcp/tools", headers=headers, json=payload).json()["id"] == tool["id"]
    )
    version = client.post(
        f"/api/v1/agents/{version['agent_id']}/versions",
        headers=headers,
        json={
            "version": "mcp",
            "goal": "Review code",
            "instructions": "Use the tool",
            "primary_model": "fake",
            "tool_version_ids": [tool["id"]],
            "runtime_config": {"max_steps": 4, "max_runtime_seconds": 180},
        },
    )
    assert version.status_code == 201, version.text
    client.app.state.settings.approval_reviewer_token = SecretStr(TOKEN)
    client.app.state.settings.approval_reviewer_id = uuid4()
    return headers, version.json(), tool


def test_mcp_review_execute_and_reuse(client, monkeypatch):
    headers, version, tool = setup(client, monkeypatch)
    calls = []

    async def execute(binding, arguments):
        calls.append(arguments)
        return {"content": [{"type": "text", "text": "Code inspected"}]}

    monkeypatch.setattr(mcp_client, "execute", execute)
    run = post_run(client, headers, version, "/tool " + tool["name"] + ' {"code":"x=1"}').json()
    assert run["status"] == "WAITING_FOR_APPROVAL", run
    assert calls == []
    approval = client.get(f"/api/v1/approvals?run_id={run['id']}", headers=headers).json()[0]
    auth = {**headers, "Authorization": "Bearer " + TOKEN}
    assert (
        client.post(
            f"/api/v1/approvals/{approval['id']}/approve",
            headers=auth,
            json={"reason": "Reviewed exact code payload"},
        ).status_code
        == 200
    )
    result = client.post(f"/api/v1/runs/{run['id']}/resume", headers=auth)
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "COMPLETED", result.text
    assert calls == [{"code": "x=1"}]
    client.post(f"/api/v1/runs/{run['id']}/resume", headers=auth)
    assert len(calls) == 1


def test_mcp_invalid_input_and_changed_discovery(client, monkeypatch):
    headers, version, tool = setup(client, monkeypatch)
    run = post_run(client, headers, version, "/tool " + tool["name"] + ' {"unknown":1}').json()
    assert run["status"] == "FAILED", run
    assert run["error_code"] == "TOOL_VALIDATION_FAILED"
    response = client.post(
        "/api/v1/mcp/tools",
        headers=headers,
        json={"server": "code", "remote_name": "inspect", "fingerprint": "0" * 64},
    )
    assert response.status_code == 409
    other, _ = setup_version(client)
    assert client.get("/api/v1/tools/" + tool["id"], headers=other).status_code == 404


def test_mcp_failed_external_call_blocks_retry(client, monkeypatch):
    headers, version, tool = setup(client, monkeypatch)

    async def fail(*args):
        raise ToolFailure("MCP_CONNECTION_FAILED")

    monkeypatch.setattr(mcp_client, "execute", fail)
    run = post_run(client, headers, version, "/tool " + tool["name"] + ' {"code":"x=1"}').json()
    approval = client.get(f"/api/v1/approvals?run_id={run['id']}", headers=headers).json()[0]
    auth = {**headers, "Authorization": "Bearer " + TOKEN}
    client.post(
        f"/api/v1/approvals/{approval['id']}/approve", headers=auth, json={"reason": "Review"}
    )
    result = client.post(f"/api/v1/runs/{run['id']}/resume", headers=auth)
    assert result.json()["status"] == "FAILED", result.text
    response = client.post(
        f"/api/v1/runs/{run['id']}/retry", headers={**headers, "Idempotency-Key": uuid4().hex}
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "RETRY_REQUIRES_RECONCILIATION"


def test_mcp_worker_unknown_outcome_is_not_replayed(client, monkeypatch, database_url):
    import asyncio
    import os

    from test_durability_postgres import process

    redis_url = os.environ.get("FORGE_TEST_REDIS_URL")
    if not redis_url:
        pytest.skip("Disposable Redis required")
    headers, version, tool = setup(client, monkeypatch)
    client.app.state.settings.execution_mode = "queued"
    run = post_run(client, headers, version, "/tool " + tool["name"] + ' {"code":"x=1"}').json()
    process(database_url, redis_url, run)
    approval = client.get(f"/api/v1/approvals?run_id={run['id']}", headers=headers).json()[0]
    auth = {**headers, "Authorization": "Bearer " + TOKEN}
    client.post(
        f"/api/v1/approvals/{approval['id']}/approve", headers=auth, json={"reason": "Review"}
    )
    attempts = []

    async def interrupted(*args):
        attempts.append(True)
        raise asyncio.CancelledError()

    monkeypatch.setattr(mcp_client, "execute", interrupted)
    with pytest.raises(asyncio.CancelledError):
        process(database_url, redis_url, run)
    process(database_url, redis_url, run)
    result = client.get(f"/api/v1/runs/{run['id']}", headers=headers).json()
    assert result["status"] == "FAILED", result
    assert result["error_code"] == "TOOL_OUTCOME_UNKNOWN"
    assert len(attempts) == 1


def test_mcp_denial_never_contacts_tool(client, monkeypatch):
    headers, version, tool = setup(client, monkeypatch)

    async def unexpected(*args):
        pytest.fail("Denied tool must not execute")

    monkeypatch.setattr(mcp_client, "execute", unexpected)
    run = post_run(client, headers, version, "/tool " + tool["name"] + ' {"code":"x=1"}').json()
    approval = client.get(f"/api/v1/approvals?run_id={run['id']}", headers=headers).json()[0]
    auth = {**headers, "Authorization": "Bearer " + TOKEN}
    response = client.post(
        f"/api/v1/approvals/{approval['id']}/deny",
        headers=auth,
        json={"reason": "Do not share this code"},
    )
    assert response.status_code == 200
    assert client.get(f"/api/v1/runs/{run['id']}", headers=headers).json()["status"] == "CANCELLED"
