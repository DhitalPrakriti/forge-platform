import asyncio
import os
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from forge.api.runs import get_adapter
from forge.core.config import Settings
from forge.main import create_app
from forge.model_router.base import ModelFailure, ModelResult
from forge.model_router.fake import FakeAdapter

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def database_url():
    url = os.environ.get("FORGE_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set FORGE_TEST_DATABASE_URL to a disposable PostgreSQL database")
    subprocess.run(
        ["alembic", "upgrade", "head"],
        env={**os.environ, "FORGE_DATABASE_URL": url},
        check=True,
        capture_output=True,
    )
    return url


@pytest.fixture
def client(database_url):
    config = Settings(
        _env_file=None,
        environment="test",
        execution_mode="inline",
        database_url=database_url,
        model_backend="fake",
        model_timeout_seconds=0.2,
    )
    with TestClient(create_app(config)) as client:
        yield client


def setup_version(client, **changes):
    org = client.post("/api/v1/organizations", json={"name": "Runtime", "slug": uuid4().hex}).json()
    headers = {"X-Organization-ID": org["id"], "Idempotency-Key": uuid4().hex}
    agent = client.post(
        "/api/v1/agents", headers=headers, json={"name": "Demo", "slug": "demo"}
    ).json()
    version = client.post(
        f"/api/v1/agents/{agent['id']}/versions",
        headers=headers,
        json={
            "version": "v1",
            "goal": "Help",
            "instructions": "Be concise",
            "primary_model": "gemini-example",
            **changes,
        },
    )
    assert version.status_code == 201, version.text
    return headers, version.json()


def post_run(client, headers, version, message="Hi"):
    return client.post(
        "/api/v1/runs",
        headers=headers,
        json={"agent_version_id": version["id"], "input": {"message": message}},
    )


def test_fake_run_exact_version_history_and_idempotency(client):
    headers, version = setup_version(client)
    response = post_run(client, headers, version)
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["agent_version_id"] == version["id"]
    assert run["status"] == "COMPLETED" and run["state_version"] == 2
    assert run["model_calls_count"] == 1 and run["tool_calls_count"] == 0
    assert run["output"]["message"].startswith("[FAKE MODEL")
    assert run["execution_config"]["provider"] == "fake"
    assert run["completed_at"] and run["started_at"]
    path = f"/api/v1/runs/{run['id']}"
    assert client.get(path, headers=headers).json() == run
    events = client.get(path + "/events", headers=headers).json()
    assert [e["event_type"] for e in events] == ["CREATED", "RUNNING", "COMPLETED"]
    assert [e["sequence_number"] for e in events] == [0, 1, 2]
    assert len(client.get(path + "/events?after=0&limit=1", headers=headers).json()) == 1
    calls = client.get(path + "/model-calls", headers=headers).json()
    assert len(calls) == 1 and calls[0]["status"] == "COMPLETED"
    assert calls[0]["model"] == "gemini-example"
    assert calls[0]["actual_model"] == "forge-fake-v1"
    assert calls[0]["latency_ms"] >= 0
    assert post_run(client, headers, version).status_code == 200
    conflict = post_run(client, headers, version, "Changed")
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    # Later metadata and version changes cannot affect an existing run.
    client.patch(f"/api/v1/agents/{version['agent_id']}", headers=headers, json={"name": "Renamed"})
    newer = client.post(
        f"/api/v1/agents/{version['agent_id']}/versions",
        headers=headers,
        json={
            "version": "v2",
            "goal": "Other",
            "instructions": "Changed",
            "primary_model": "other",
        },
    )
    assert newer.status_code == 201
    assert client.get(path, headers=headers).json() == run


@pytest.mark.parametrize(
    "outcome, status, code",
    [
        ("timeout", "TIMED_OUT", "MODEL_TIMEOUT"),
        ("provider", "FAILED", "MODEL_PROVIDER_UNAVAILABLE"),
        ("unexpected", "FAILED", "MODEL_INTERNAL_ERROR"),
        ("tool", "FAILED", "TOOL_NOT_ALLOWED"),
        ("blocked", "FAILED", "MODEL_RESPONSE_INCOMPLETE"),
    ],
)
def test_failed_runs_persist_and_do_not_execute_tools(client, outcome, status, code):
    class Adapter(FakeAdapter):
        provider = "google"

        async def generate(self, request):
            if outcome == "timeout":
                await asyncio.sleep(10)
            if outcome == "provider":
                raise ModelFailure("MODEL_PROVIDER_UNAVAILABLE")
            if outcome == "unexpected":
                raise RuntimeError("private secret payload")
            return ModelResult(
                "",
                "exact-model",
                usage={"total_token_count": 10},
                tool_requests=[{"name": "issue_refund", "arguments": {"amount": 5000}}]
                if outcome == "tool"
                else [],
                finish_reason="STOP" if outcome == "tool" else "SAFETY",
            )

    client.app.dependency_overrides[get_adapter] = lambda: Adapter()
    headers, version = setup_version(client)
    response = post_run(client, headers, version)
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["status"] == status and run["error_code"] == code
    assert run["total_cost"] is None
    assert run["output"] is None and run["tool_calls_count"] == (1 if outcome == "tool" else 0)
    assert "private" not in response.text
    calls = client.get(f"/api/v1/runs/{run['id']}/model-calls", headers=headers).json()
    assert len(calls) == 1 and calls[0]["completed_at"]
    assert "private" not in str(calls)
    assert post_run(client, headers, version).json()["id"] == run["id"]


def test_scope_lifecycle_and_missing_configuration(client):
    headers, version = setup_version(client)
    other, other_version = setup_version(client)
    assert post_run(client, other, version).status_code == 404
    run = post_run(client, headers, version).json()
    for suffix in ("", "/events", "/model-calls"):
        assert client.get(f"/api/v1/runs/{run['id']}{suffix}", headers=other).status_code == 404
    no_key = {"X-Organization-ID": headers["X-Organization-ID"]}
    assert post_run(client, no_key, version).status_code == 422
    client.post(f"/api/v1/agent-versions/{other_version['id']}/archive", headers=other)
    assert post_run(client, other, other_version).status_code == 409
    client.app.state.settings.model_backend = "gemini"
    client.app.state.settings.gemini_api_key = None
    fresh = headers | {"Idempotency-Key": uuid4().hex}
    result = post_run(client, fresh, version)
    assert result.status_code == 503
    assert result.json()["error"]["code"] == "MODEL_NOT_CONFIGURED"
    client.app.state.settings.environment = "production"
    assert post_run(client, headers, version).status_code == 503
    assert client.get(f"/api/v1/runs/{run['id']}", headers=headers).status_code == 503


@pytest.mark.parametrize(
    "changes",
    [
        {"fallback_models": ["other"]},
        {"runtime_template_revision": "future"},
    ],
)
def test_unsupported_configuration_never_calls_model(client, changes):
    headers, version = setup_version(client, **changes)
    response = post_run(client, headers, version)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "RUNTIME_CONFIGURATION_UNSUPPORTED"


def test_concurrent_duplicate_only_calls_provider_once(client):
    started, release = threading.Event(), threading.Event()
    requests = []

    class Adapter(FakeAdapter):
        async def generate(self, request):
            requests.append(request)
            started.set()
            await asyncio.to_thread(release.wait, 5)
            return await super().generate(request)

    client.app.state.settings.model_timeout_seconds = 10
    client.app.dependency_overrides[get_adapter] = lambda: Adapter()
    headers, version = setup_version(client)
    with ThreadPoolExecutor(max_workers=2) as executor:
        initial = executor.submit(post_run, client, headers, version)
        try:
            assert started.wait(5)
            duplicate = post_run(client, headers, version)
            assert duplicate.status_code == 200, duplicate.text
            assert duplicate.json()["status"] == "RUNNING"
        finally:
            release.set()
        response = initial.result(timeout=5)
    assert response.status_code == 201
    assert response.json()["id"] == duplicate.json()["id"]
    assert len(requests) == 1
    assert requests[0].instructions == "Be concise"
    assert requests[0].model == "gemini-example"


def test_provider_usage_and_effective_request_are_preserved(client):
    seen = []

    class Adapter(FakeAdapter):
        provider = "google"

        async def generate(self, request):
            seen.append(request)
            return ModelResult(
                "Bonjour 👋",
                "gemini-exact-revision",
                input_tokens=12,
                output_tokens=7,
                usage={"total_token_count": 19},
                finish_reason="STOP",
            )

    client.app.state.settings.model_timeout_seconds = 10
    client.app.dependency_overrides[get_adapter] = lambda: Adapter()
    headers, version = setup_version(
        client, runtime_config={"max_steps": 1, "max_runtime_seconds": 2}
    )
    response = post_run(client, headers, version, "Hello café")
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["status"] == "COMPLETED"
    assert run["output"] == {"message": "Bonjour 👋"}
    assert run["total_cost"] is None
    assert 0 < seen[0].timeout_seconds <= 2
    assert seen[0].message == "Hello café" and seen[0].instructions == version["instructions"]
    call = client.get(f"/api/v1/runs/{run['id']}/model-calls", headers=headers).json()[0]
    assert call["input_tokens"] == 12 and call["output_tokens"] == 7
    assert call["actual_model"] == "gemini-exact-revision"
    assert call["usage"] == {"total_token_count": 19}
    assert call["estimated_cost"] is None
