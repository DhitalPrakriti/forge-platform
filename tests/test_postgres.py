import asyncio
import os
import subprocess

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from forge.core.config import Settings
from forge.db.session import Database
from forge.main import create_app

pytestmark = pytest.mark.integration


def test_migrations_database_and_readiness():
    url = os.environ.get("FORGE_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set FORGE_TEST_DATABASE_URL to a disposable PostgreSQL database")
    env = {**os.environ, "FORGE_DATABASE_URL": url}

    def alembic(*args):
        subprocess.run(["alembic", *args], env=env, check=True, capture_output=True, text=True)

    async def revision():
        db = Database(Settings(_env_file=None, database_url=url))
        try:
            async with db.sessions() as session:
                return (
                    await session.execute(text("SELECT version_num FROM alembic_version"))
                ).scalar()
        finally:
            await db.close()

    alembic("upgrade", "head")
    assert asyncio.run(revision()) == "0006_durability"
    alembic("downgrade", "base")
    assert asyncio.run(revision()) is None
    alembic("upgrade", "head")
    assert asyncio.run(revision()) == "0006_durability"
    alembic("check")
    with TestClient(create_app(Settings(_env_file=None, database_url=url))) as client:
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}
