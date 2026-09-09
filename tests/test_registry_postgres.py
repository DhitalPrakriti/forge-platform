import asyncio
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from forge.core.config import Settings
from forge.db.session import Database
from forge.main import create_app

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
    with TestClient(
        create_app(Settings(_env_file=None, environment="test", database_url=database_url))
    ) as client:
        yield client


def organization(client):
    slug = f"org-{uuid4().hex}"
    response = client.post("/api/v1/organizations", json={"name": "Demo", "slug": slug})
    assert response.status_code == 201, response.text
    return {"X-Organization-ID": response.json()["id"]}


def agent(client, scope, slug="support"):
    response = client.post("/api/v1/agents", headers=scope, json={"name": "Support", "slug": slug})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def version_payload(**changes):
    return {
        "version": "v1",
        "goal": "Help customers",
        "instructions": "Follow policy.",
        "primary_model": "gemini-2.5-flash",
        **changes,
    }


def test_registry_versions_and_archive(client):
    scope = organization(client)
    aid = agent(client, scope)
    base = f"/api/v1/agents/{aid}"
    first = client.post(f"{base}/versions", headers=scope, json=version_payload())
    assert first.status_code == 201, first.text
    original = first.json()
    assert original["lifecycle_status"] == "DRAFT"
    second = client.post(
        f"{base}/versions",
        headers=scope,
        json=version_payload(version="v2", instructions="Revised policy."),
    )
    assert second.status_code == 201
    versions = client.get(f"{base}/versions", headers=scope).json()
    assert [v["version"] for v in versions] == ["v1", "v2"]
    assert client.get(f"{base}/versions?limit=1&offset=1", headers=scope).json() == [second.json()]
    patched = client.patch(base, headers=scope, json={"name": "New name"})
    assert patched.status_code == 200, patched.text
    vpath = f"{base}/versions/{original['id']}"
    assert client.get(vpath, headers=scope).json() == original
    rejection = client.patch(vpath, headers=scope, json={"instructions": "Mutate history"})
    assert rejection.status_code == 409
    assert rejection.json()["error"]["code"] == "VERSION_IMMUTABLE"
    stage = client.post(f"/api/v1/agent-versions/{original['id']}/stage", headers=scope)
    assert stage.status_code == 409
    assert stage.json()["error"]["code"] == "EVALUATION_SUITE_REQUIRED"
    archive = client.post(f"/api/v1/agent-versions/{original['id']}/archive", headers=scope)
    assert archive.status_code == 200, archive.text
    assert archive.json() == original | {"lifecycle_status": "ARCHIVED"}
    again = client.post(f"/api/v1/agent-versions/{original['id']}/archive", headers=scope)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "INVALID_LIFECYCLE_TRANSITION"
    assert (
        client.get(f"{base}/versions/{second.json()['id']}", headers=scope).json() == second.json()
    )


def test_organization_scoping_and_validation(client):
    a, b = organization(client), organization(client)
    aid, bid = agent(client, a), agent(client, b)
    vid = client.post(f"/api/v1/agents/{aid}/versions", headers=a, json=version_payload()).json()[
        "id"
    ]
    assert (
        client.get("/api/v1/organizations/current", headers=a).json()["id"]
        == a["X-Organization-ID"]
    )
    assert [row["id"] for row in client.get("/api/v1/agents", headers=b).json()] == [bid]
    for method, path, payload in [
        ("get", f"/agents/{aid}", None),
        ("patch", f"/agents/{aid}", {"name": "Hacked"}),
        ("get", f"/agents/{aid}/versions", None),
        ("post", f"/agents/{aid}/versions", version_payload()),
        ("get", f"/agents/{bid}/versions/{vid}", None),
        ("patch", f"/agents/{aid}/versions/{vid}", {}),
        ("post", f"/agent-versions/{vid}/archive", None),
        ("post", f"/agent-versions/{vid}/stage", None),
    ]:
        response = client.request(method, f"/api/v1{path}", headers=b, json=payload)
        assert response.status_code == 404, (path, response.text)
    assert client.get("/api/v1/agents").status_code == 422
    assert client.get("/api/v1/agents", headers={"X-Organization-ID": "bad"}).status_code == 422
    assert client.get("/api/v1/agents?limit=101", headers=a).status_code == 422
    assert (
        client.post(
            "/api/v1/agents",
            headers={"X-Organization-ID": str(uuid4())},
            json={"name": "Missing", "slug": "missing"},
        ).status_code
        == 404
    )
    # Wrong parent within the same organization must also conceal the version.
    other = agent(client, a, "other")
    assert client.get(f"/api/v1/agents/{other}/versions/{vid}", headers=a).status_code == 404


def test_duplicates_and_inactive_agent(client):
    scope = organization(client)
    aid = agent(client, scope)
    duplicate = client.post(
        "/api/v1/agents", headers=scope, json={"name": "Duplicate", "slug": "support"}
    )
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["error"]["code"] == "AGENT_SLUG_EXISTS"
    path = f"/api/v1/agents/{aid}/versions"
    assert client.post(path, headers=scope, json=version_payload()).status_code == 201
    duplicate = client.post(path, headers=scope, json=version_payload())
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["error"]["code"] == "VERSION_EXISTS"
    assert (
        client.patch(
            f"/api/v1/agents/{aid}", headers=scope, json={"status": "INACTIVE"}
        ).status_code
        == 200
    )
    assert client.post(path, headers=scope, json=version_payload(version="v2")).status_code == 409
    assert len(client.get(path, headers=scope).json()) == 1


def test_unverified_staging_references_are_blocked(client):
    scope = organization(client)
    aid = agent(client, scope)
    payload = version_payload(
        evaluation_suite_version_id=str(uuid4()),
    )
    response = client.post(f"/api/v1/agents/{aid}/versions", headers=scope, json=payload)
    assert response.status_code == 201
    vid = response.json()["id"]
    staged = client.post(f"/api/v1/agent-versions/{vid}/stage", headers=scope)
    assert staged.status_code == 409
    assert staged.json()["error"]["code"] == "STAGING_DEPENDENCIES_UNAVAILABLE"
    assert (
        client.get(f"/api/v1/agents/{aid}/versions/{vid}", headers=scope).json()["lifecycle_status"]
        == "DRAFT"
    )


def test_concurrent_version_creation_and_archive(client):
    scope = organization(client)
    aid = agent(client, scope)
    path = f"/api/v1/agents/{aid}/versions"
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(
                lambda _: client.post(path, headers=scope, json=version_payload()), range(2)
            )
        )
    assert sorted(r.status_code for r in responses) == [201, 409]
    rows = client.get(path, headers=scope).json()
    assert len(rows) == 1
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(
                lambda _: client.post(
                    f"/api/v1/agent-versions/{rows[0]['id']}/archive", headers=scope
                ),
                range(2),
            )
        )
    assert sorted(r.status_code for r in responses) == [200, 409]


def test_postgres_guards_history(client, database_url):
    scope = organization(client)
    aid = agent(client, scope)
    response = client.post(f"/api/v1/agents/{aid}/versions", headers=scope, json=version_payload())
    vid = response.json()["id"]

    async def verify():
        database = Database(Settings(_env_file=None, database_url=database_url))
        try:
            for statement, code in [
                (
                    "UPDATE agent_versions SET instructions = 'changed' WHERE id = :id",
                    "VERSION_IMMUTABLE",
                ),
                (
                    "UPDATE agent_versions SET runtime_config = '{}' WHERE id = :id",
                    "VERSION_IMMUTABLE",
                ),
                (
                    "UPDATE agent_versions SET lifecycle_status = 'PRODUCTION' WHERE id = :id",
                    "INVALID_LIFECYCLE_TRANSITION",
                ),
                ("DELETE FROM agent_versions WHERE id = :id", "VERSION_IMMUTABLE"),
                ("TRUNCATE agent_versions CASCADE", "VERSION_IMMUTABLE"),
            ]:
                async with database.sessions() as session:
                    with pytest.raises(DBAPIError) as error:
                        await session.execute(text(statement), {"id": vid})
                    assert code in str(error.value)
                    await session.rollback()
        finally:
            await database.close()

    asyncio.run(verify())
    assert (
        client.get(f"/api/v1/agents/{aid}/versions/{vid}", headers=scope).json() == response.json()
    )


def test_organization_uniqueness_and_rejected_initial_status(client):
    payload = {"name": "Demo", "slug": "unique-" + uuid4().hex}
    response = client.post("/api/v1/organizations", json=payload)
    assert response.status_code == 201
    duplicate = client.post("/api/v1/organizations", json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "ORGANIZATION_SLUG_EXISTS"
    scope = {"X-Organization-ID": response.json()["id"]}
    aid = agent(client, scope)
    response = client.post(
        f"/api/v1/agents/{aid}/versions",
        headers=scope,
        json=version_payload(lifecycle_status="APPROVED"),
    )
    assert response.status_code == 422
    assert client.get(f"/api/v1/agents/{aid}/versions", headers=scope).json() == []
