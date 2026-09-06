import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from forge.core.config import Settings
from forge.core.errors import DomainError
from forge.health.service import check_database
from forge.main import create_app

URL = "postgresql+asyncpg://forge:test_secret@127.0.0.1:1/forge_test"


def settings(**kwargs):
    return Settings(_env_file=None, database_url=URL, **kwargs)


def test_configuration(monkeypatch):
    monkeypatch.setenv("FORGE_DATABASE_URL", URL)
    monkeypatch.setenv("FORGE_DATABASE_TIMEOUT_SECONDS", "2.5")
    config = Settings(_env_file=None)
    assert config.database_timeout_seconds == 2.5
    assert "test_secret" not in repr(config)
    assert config.database_url.get_secret_value() == URL


@pytest.mark.parametrize("url", ["sqlite:///test.db", "postgresql://user@host/db", "bad"])
def test_invalid_database_url(url):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url=url)


@pytest.mark.parametrize("timeout", [0, -1, 61])
def test_invalid_timeout(timeout):
    with pytest.raises(ValidationError):
        settings(database_timeout_seconds=timeout)


def test_missing_database_url(monkeypatch):
    monkeypatch.delenv("FORGE_DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_health_and_resource_cleanup():
    app = create_app(settings(database_timeout_seconds=0.1))
    with TestClient(app) as client:
        database = app.state.database
        original_close = database.close
        database.close = AsyncMock(wraps=original_close)
        live = client.get("/api/v1/health/live")
        assert live.status_code == 200
        assert live.json() == {"status": "ok"}
        ready = client.get("/api/v1/health/ready")
        assert ready.status_code == 503
        assert ready.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
        assert ready.json()["error"]["trace_id"] == ready.headers["X-Trace-ID"]
        assert "test_secret" not in ready.text
        assert client.get("/api/v1/health/live").status_code == 200
    database.close.assert_awaited_once()


def test_error_contract(caplog):
    app = create_app(settings())

    class Payload(BaseModel):
        count: int

    @app.post("/validation")
    def validation(payload: Payload):
        return payload

    @app.get("/domain")
    def domain():
        raise DomainError("EXAMPLE_CONFLICT", "Example conflict.", 409)

    @app.get("/unexpected")
    def unexpected():
        raise RuntimeError("private_exception_secret")

    @app.get("/unauthorized")
    def unauthorized():
        raise HTTPException(401, "private_detail", headers={"WWW-Authenticate": "Bearer"})

    with TestClient(app, raise_server_exceptions=False) as client:
        responses = [
            (client.get("/missing"), 404, "HTTP_404"),
            (client.post("/validation", json={"count": "private_input"}), 422, "VALIDATION_ERROR"),
            (client.get("/domain"), 409, "EXAMPLE_CONFLICT"),
            (client.get("/unexpected"), 500, "INTERNAL_ERROR"),
            (client.get("/unauthorized"), 401, "HTTP_401"),
            (client.post("/api/v1/health/live"), 405, "HTTP_405"),
        ]
        for response, status, code in responses:
            assert response.status_code == status
            error = response.json()["error"]
            assert set(error) == {"code", "message", "trace_id", "details"}
            assert error["code"] == code
            assert error["trace_id"] == response.headers["X-Trace-ID"]
            assert "private_" not in response.text
        assert "private_exception_secret" not in caplog.text
        assert "INTERNAL_ERROR trace_id=" in caplog.text
        assert responses[4][0].headers["WWW-Authenticate"] == "Bearer"
        assert len({r.headers["X-Trace-ID"] for r, _, _ in responses}) == len(responses)


def test_readiness_bounds_slow_database():
    class SlowConnection:
        async def __aenter__(self):
            await asyncio.sleep(10)

        async def __aexit__(self, *args):
            pass

    class SlowEngine:
        def connect(self):
            return SlowConnection()

    with pytest.raises(DomainError) as exc:
        asyncio.run(check_database(SlowEngine(), 0.01))
    assert exc.value.status_code == 503
