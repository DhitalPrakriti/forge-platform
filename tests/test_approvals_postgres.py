import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from test_runtime_postgres import client as runtime_client
from test_runtime_postgres import database_url as runtime_database_url
from test_runtime_postgres import post_run, setup_version

from forge.approvals.models import DemoRefund, RunCheckpoint
from forge.core.config import Settings
from forge.db.session import Database
from forge.main import create_app

client = runtime_client
database_url = runtime_database_url
pytestmark = pytest.mark.integration
TOKEN = "test-reviewer-credential-not-a-secret-12345"
REVIEWER = uuid4()


def setup(client, seconds=180):
    client.app.state.settings.approval_reviewer_token = SecretStr(TOKEN)
    client.app.state.settings.approval_reviewer_id = REVIEWER
    headers, initial = setup_version(client)
    policy = client.post("/api/v1/policies", headers=headers).json()
    tool = client.post("/api/v1/tools", headers=headers, json={"name": "issue_refund"}).json()
    response = client.post(
        f"/api/v1/agents/{initial['agent_id']}/versions",
        headers=headers,
        json={
            "version": "refunds",
            "goal": "Demo",
            "instructions": "Use tools",
            "primary_model": "fake",
            "tool_version_ids": [tool["id"]],
            "policy_version_ids": [policy["id"]],
            "runtime_config": {"max_steps": 4, "max_runtime_seconds": seconds},
        },
    )
    assert response.status_code == 201, response.text
    return headers, response.json(), tool, policy


def refund(client, headers, version, amount="425.00"):
    response = post_run(
        client,
        headers,
        version,
        f'/tool issue_refund {{"customer_id":"cust_001","amount_usd":"{amount}"}}',
    )
    assert response.status_code == 201, response.text
    return response.json()


def approvals(client, headers, run):
    return client.get(f"/api/v1/approvals?run_id={run['id']}", headers=headers).json()


def review_headers(headers):
    return {**headers, "Authorization": "Bearer " + TOKEN}


def count(database_url, org):
    async def query():
        db = Database(Settings(_env_file=None, database_url=database_url))
        try:
            async with db.sessions() as s:
                return await s.scalar(
                    select(func.count())
                    .select_from(DemoRefund)
                    .where(DemoRefund.organization_id == UUID(org))
                )
        finally:
            await db.close()

    return asyncio.run(query())


@pytest.mark.parametrize(
    "amount,status,effects",
    [
        ("50.00", "COMPLETED", 1),
        ("100.00", "COMPLETED", 1),
        ("100.01", "WAITING_FOR_APPROVAL", 0),
        ("425.00", "WAITING_FOR_APPROVAL", 0),
        ("500.00", "WAITING_FOR_APPROVAL", 0),
        ("500.01", "FAILED", 0),
        ("700.00", "FAILED", 0),
        ("0.00", "FAILED", 0),
        ("NaN", "FAILED", 0),
    ],
)
def test_refund_thresholds(client, database_url, amount, status, effects):
    headers, version, _, _ = setup(client)
    run = refund(client, headers, version, amount)
    assert run["status"] == status, run
    assert count(database_url, headers["X-Organization-ID"]) == effects
    assert len(approvals(client, headers, run)) == (1 if status == "WAITING_FOR_APPROVAL" else 0)


def test_restart_approve_resume_exactly_once(client, database_url):
    headers, version, _, _ = setup(client)
    run = refund(client, headers, version)
    approval = approvals(client, headers, run)[0]
    path = f"/api/v1/approvals/{approval['id']}/approve"
    assert client.post(path, headers=headers, json={"reason": "Checked"}).status_code == 401
    assert (
        client.post(f"/api/v1/runs/{run['id']}/resume", headers=review_headers(headers)).status_code
        == 409
    )
    result = client.post(
        path, headers=review_headers(headers), json={"reason": "Checked exact request"}
    )
    assert result.status_code == 200, result.text
    assert result.json()["reviewed_by"] == str(REVIEWER)
    # Independent application/engine/session pool, with no original in-memory continuation.
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=database_url,
        model_backend="fake",
        approval_reviewer_token=TOKEN,
        approval_reviewer_id=REVIEWER,
    )
    with TestClient(create_app(settings)) as restarted:
        result = restarted.post(f"/api/v1/runs/{run['id']}/resume", headers=review_headers(headers))
        assert result.status_code == 200, result.text
        assert result.json()["status"] == "COMPLETED", result.text
        assert result.json()["model_calls_count"] == 2
        assert result.json()["tool_calls_count"] == 1
        assert (
            restarted.post(
                f"/api/v1/runs/{run['id']}/resume", headers=review_headers(headers)
            ).json()["id"]
            == run["id"]
        )
    assert count(database_url, headers["X-Organization-ID"]) == 1
    assert (
        client.post(path, headers=review_headers(headers), json={"reason": "Retry"}).status_code
        == 200
    )
    assert (
        client.post(
            path.replace("/approve", "/deny"),
            headers=review_headers(headers),
            json={"reason": "Changed"},
        ).status_code
        == 409
    )


def test_denial_and_org_isolation(client, database_url):
    headers, version, _, _ = setup(client)
    run = refund(client, headers, version)
    a = approvals(client, headers, run)[0]
    other, _ = setup_version(client)
    assert client.get(f"/api/v1/approvals/{a['id']}", headers=other).status_code == 404
    assert (
        client.post(
            f"/api/v1/approvals/{a['id']}/approve",
            headers=review_headers(other),
            json={"reason": "x"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/approvals/{a['id']}/deny",
            headers=review_headers(headers),
            json={"reason": "No refund"},
        ).json()["status"]
        == "DENIED"
    )
    result = client.post(f"/api/v1/runs/{run['id']}/resume", headers=review_headers(headers)).json()
    assert result["status"] == "CANCELLED"
    assert count(database_url, headers["X-Organization-ID"]) == 0


def test_expiry_and_disabled_tool(client, database_url):
    import time

    headers, version, _, _ = setup(client, seconds=1)
    run = refund(client, headers, version)
    a = approvals(client, headers, run)[0]
    time.sleep(1.05)
    assert (
        client.post(
            f"/api/v1/approvals/{a['id']}/approve",
            headers=review_headers(headers),
            json={"reason": "Too late"},
        ).json()["status"]
        == "EXPIRED"
    )
    assert count(database_url, headers["X-Organization-ID"]) == 0
    headers, version, tool, _ = setup(client)
    run = refund(client, headers, version)
    a = approvals(client, headers, run)[0]
    client.post(
        f"/api/v1/approvals/{a['id']}/approve",
        headers=review_headers(headers),
        json={"reason": "x"},
    )
    client.patch(f"/api/v1/tools/{tool['id']}", headers=headers, json={"status": "INACTIVE"})
    result = client.post(f"/api/v1/runs/{run['id']}/resume", headers=review_headers(headers))
    assert result.status_code == 409 and result.json()["error"]["code"] == "TOOL_INACTIVE"
    assert count(database_url, headers["X-Organization-ID"]) == 0


def test_immutable_policy_approval_checkpoint(client, database_url):
    headers, version, _, policy = setup(client)
    run = refund(client, headers, version)
    a = approvals(client, headers, run)[0]

    async def check():
        db = Database(Settings(_env_file=None, database_url=database_url))
        try:
            for statement, identity in [
                ("UPDATE policies SET rules='{}' WHERE id=:id", policy["id"]),
                ("UPDATE approvals SET requested_payload='{}' WHERE id=:id", a["id"]),
                ("UPDATE run_checkpoints SET runtime_state='{}' WHERE run_id=:id", run["id"]),
            ]:
                async with db.sessions() as s:
                    with pytest.raises(DBAPIError):
                        await s.execute(text(statement), {"id": identity})
                    await s.rollback()
            async with db.sessions() as s:
                cp = await s.scalar(
                    select(RunCheckpoint).where(RunCheckpoint.run_id == UUID(run["id"]))
                )
                assert (
                    cp.runtime_state["result"]["tool_requests"][0]["arguments"]["amount_usd"]
                    == "425.00"
                )
        finally:
            await db.close()

    asyncio.run(check())


def test_concurrent_resume_and_missing_policy(client, database_url):
    from concurrent.futures import ThreadPoolExecutor

    headers, version, _, _ = setup(client)
    run = refund(client, headers, version)
    a = approvals(client, headers, run)[0]
    client.post(
        f"/api/v1/approvals/{a['id']}/approve",
        headers=review_headers(headers),
        json={"reason": "Verified"},
    )

    def resume():
        return client.post(f"/api/v1/runs/{run['id']}/resume", headers=review_headers(headers))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: resume(), range(2)))
    assert all(r.status_code in (200, 409) for r in results)
    assert any(r.status_code == 200 and r.json()["status"] == "COMPLETED" for r in results)
    assert count(database_url, headers["X-Organization-ID"]) == 1
    result = client.post(
        f"/api/v1/agents/{version['agent_id']}/versions",
        headers=headers,
        json={
            "version": "bad-policy",
            "goal": "x",
            "instructions": "x",
            "primary_model": "x",
            "policy_version_ids": [str(uuid4())],
        },
    )
    assert result.status_code == 404


def test_changed_request_cannot_reuse_approval(client, database_url):
    from forge.runtime.models import Run
    from forge.tools.builtins import ToolFailure
    from forge.tools.hub import ToolHub
    from forge.tools.models import Tool

    headers, version, tool, _ = setup(client)
    run = refund(client, headers, version)
    call = client.get(f"/api/v1/runs/{run['id']}/tool-calls", headers=headers).json()[0]

    async def check():
        db = Database(Settings(_env_file=None, database_url=database_url))
        try:
            async with db.sessions() as s:
                entity = await s.get(Run, UUID(run["id"]))
                bound = await s.get(Tool, UUID(tool["id"]))
                with pytest.raises(ToolFailure, match="TOOL_IDEMPOTENCY_CONFLICT"):
                    await ToolHub(s).execute(
                        entity,
                        UUID(call["model_call_id"]),
                        0,
                        {
                            "name": "issue_refund",
                            "arguments": {"customer_id": "cust_002", "amount_usd": "425.00"},
                        },
                        [bound],
                        10,
                    )
        finally:
            await db.close()

    asyncio.run(check())
    assert count(database_url, headers["X-Organization-ID"]) == 0


def test_multiple_approval_pauses_reuse_previous_results(client, database_url):
    from dataclasses import replace

    from forge.api.runs import get_adapter
    from forge.model_router.fake import FakeAdapter

    class BatchAdapter(FakeAdapter):
        async def generate(self, request):
            result = await super().generate(request)
            if not request.exchanges:
                second = {
                    "name": "issue_refund",
                    "arguments": {"customer_id": "cust_002", "amount_usd": "300.00"},
                }
                return replace(result, tool_requests=[*result.tool_requests, second])
            return result

    client.app.dependency_overrides[get_adapter] = lambda: BatchAdapter()
    headers, version, _, _ = setup(client)
    run = refund(client, headers, version)
    first = approvals(client, headers, run)[0]
    client.post(
        f"/api/v1/approvals/{first['id']}/approve",
        headers=review_headers(headers),
        json={"reason": "first"},
    )
    result = client.post(f"/api/v1/runs/{run['id']}/resume", headers=review_headers(headers))
    assert result.json()["status"] == "WAITING_FOR_APPROVAL", result.text
    assert count(database_url, headers["X-Organization-ID"]) == 1
    second = approvals(client, headers, run)[0]
    assert second["id"] != first["id"]
    client.post(
        f"/api/v1/approvals/{second['id']}/approve",
        headers=review_headers(headers),
        json={"reason": "second"},
    )
    result = client.post(f"/api/v1/runs/{run['id']}/resume", headers=review_headers(headers))
    assert result.json()["status"] == "COMPLETED", result.text
    assert result.json()["model_calls_count"] == 2 and result.json()["tool_calls_count"] == 2
    assert count(database_url, headers["X-Organization-ID"]) == 2


def test_refund_output_failure_rolls_back_effect(client, database_url, monkeypatch):
    from forge.tools import builtins

    async def invalid(*args):
        await builtins.execute_builtin(*args)
        return {"invalid": True}

    monkeypatch.setattr("forge.tools.hub.execute_builtin", invalid)
    headers, version, _, _ = setup(client)
    run = refund(client, headers, version, "50.00")
    assert run["error_code"] == "TOOL_OUTPUT_INVALID"
    assert count(database_url, headers["X-Organization-ID"]) == 0
