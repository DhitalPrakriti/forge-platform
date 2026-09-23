import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_knowledge import upload
from test_runtime_postgres import client as runtime_client
from test_runtime_postgres import database_url as runtime_database_url
from test_runtime_postgres import post_run, setup_version

from forge.core.config import Settings
from forge.db.session import Database

client = runtime_client
database_url = runtime_database_url
pytestmark = pytest.mark.integration


def test_documents_scope_binding_search_and_tool_run(client, database_url):
    headers, initial = setup_version(client)
    other, _ = setup_version(client)
    documents = []
    for message in (b"Restaurant hours: Monday 9am to 5pm.", b"Secret restaurant hours: midnight."):
        response = client.post("/api/v1/knowledge/documents", headers=headers, json=upload(message))
        assert response.status_code == 201, response.text
        documents.append(response.json())
    doc = documents[0]
    assert len(client.get("/api/v1/knowledge/documents", headers=headers).json()) == 2
    assert client.get("/api/v1/knowledge/documents", headers=other).json() == []
    assert client.get(f"/api/v1/knowledge/documents/{doc['id']}", headers=other).status_code == 404
    query = {"query": "hours", "document_ids": [doc["id"]]}
    response = client.post("/api/v1/knowledge/search", headers=headers, json=query)
    assert response.status_code == 200, response.text
    assert len(response.json()["matches"]) == 1
    assert "Monday" in response.json()["matches"][0]["excerpt"]
    assert client.post("/api/v1/knowledge/search", headers=other, json=query).status_code == 404
    tool = client.post("/api/v1/tools", headers=headers, json={"name": "search_documents"}).json()
    config = {
        "version": "knowledge-v1",
        "goal": "Help",
        "instructions": "Search documents.",
        "primary_model": "forge-fake-v1",
        "knowledge_document_ids": [doc["id"]],
    }
    path = f"/api/v1/agents/{initial['agent_id']}/versions"
    assert client.post(path, headers=headers, json=config).status_code == 422
    config["tool_version_ids"] = [tool["id"]]
    response = client.post(path, headers=headers, json=config)
    assert response.status_code == 201, response.text
    version = response.json()
    run = post_run(client, headers, version, '/tool search_documents {"query":"hours"}').json()
    assert run["status"] == "COMPLETED", run
    assert run["execution_config"]["knowledge_document_ids"] == [doc["id"]]
    calls = client.get(f"/api/v1/runs/{run['id']}/tool-calls", headers=headers).json()
    assert calls[0]["status"] == "COMPLETED", calls
    assert [m["document_id"] for m in calls[0]["result"]["matches"]] == [doc["id"]]
    config.update(version="bad", knowledge_document_ids=[str(uuid4())])
    assert client.post(path, headers=headers, json=config).status_code == 404

    async def immutable():
        db = Database(Settings(_env_file=None, database_url=database_url))
        try:
            async with db.sessions() as session:
                with pytest.raises(DBAPIError):
                    await session.execute(
                        text("UPDATE knowledge_documents SET title='Changed' WHERE id=:id"),
                        {"id": UUID(doc["id"])},
                    )
                await session.rollback()
                with pytest.raises(DBAPIError):
                    await session.execute(
                        text("UPDATE knowledge_chunks SET text='Changed' WHERE document_id=:id"),
                        {"id": UUID(doc["id"])},
                    )
        finally:
            await db.close()

    asyncio.run(immutable())


def test_search_cannot_expand_version_access(client):
    headers, initial = setup_version(client)
    tool = client.post("/api/v1/tools", headers=headers, json={"name": "search_documents"}).json()
    document = client.post(
        "/api/v1/knowledge/documents",
        headers=headers,
        json=upload(b"Private opening hours are midnight."),
    ).json()
    path = f"/api/v1/agents/{initial['agent_id']}/versions"
    version = client.post(
        path,
        headers=headers,
        json={
            "version": "no-documents",
            "goal": "Help",
            "instructions": "Search",
            "primary_model": "forge-fake-v1",
            "tool_version_ids": [tool["id"]],
        },
    ).json()
    for arguments, expected in [
        ('{"query":"hours"}', "COMPLETED"),
        ('{"query":"hours","document_ids":["' + document["id"] + '"]}', "DENIED"),
    ]:
        headers["Idempotency-Key"] = uuid4().hex
        run = post_run(client, headers, version, "/tool search_documents " + arguments).json()
        calls = client.get(f"/api/v1/runs/{run['id']}/tool-calls", headers=headers).json()
        assert calls[0]["status"] == expected, calls
        if expected == "COMPLETED":
            assert calls[0]["result"]["matches"] == []
        else:
            assert calls[0]["result"] is None
    other, other_version = setup_version(client)
    other_tool = client.post(
        "/api/v1/tools", headers=other, json={"name": "search_documents"}
    ).json()
    response = client.post(
        f"/api/v1/agents/{other_version['agent_id']}/versions",
        headers=other,
        json={
            "version": "cross-workspace",
            "goal": "Help",
            "instructions": "Search",
            "primary_model": "forge-fake-v1",
            "tool_version_ids": [other_tool["id"]],
            "knowledge_document_ids": [document["id"]],
        },
    )
    assert response.status_code == 404
