"""Discovery review and immutable tool registration; credentials never enter metadata."""

from uuid import UUID

from pydantic import Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from forge.agents.schemas import Schema
from forge.approvals.models import Policy
from forge.core.errors import DomainError
from forge.tools import mcp_client
from forge.tools.builtins import ToolFailure
from forge.tools.models import Tool

RULES = {"decision": "REQUIRE_APPROVAL", "automatic_retry": False}


class MCPRegister(Schema):
    server: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,31}$")
    remote_name: str = Field(min_length=1, max_length=64)
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


def metadata(binding):
    remote = binding["remote"]
    return {
        "name": "mcp_"
        + mcp_client.digest([binding["server"], remote["name"]])[:12]
        + "_"
        + remote["name"][:40],
        "version": mcp_client.digest(binding),
        "description": remote.get("description", remote["name"]),
        "input_schema": remote["inputSchema"],
        "output_schema": remote.get("outputSchema", {}),
        "risk_level": "HIGH",
        "timeout_seconds": 25,
        "retry_safe": False,
        "idempotency_supported": False,
        "handler_type": "MCP_HTTP_V1",
    }


def validate_binding(tool):
    binding = tool.connection_config
    if not binding or tool.status != "ACTIVE":
        raise ToolFailure("MCP_TOOL_UNAVAILABLE")
    if mcp_client.digest(mcp_client.endpoint(binding["server"])["url"]) != binding["endpoint_hash"]:
        raise ToolFailure("MCP_ENDPOINT_CHANGED")
    if any(getattr(tool, k) != v for k, v in metadata(binding).items()):
        raise ToolFailure("MCP_TOOL_CHANGED")


async def policy(session, org):
    await session.execute(
        insert(Policy)
        .values(organization_id=org, name="mcp-review", version="1.0.0", rules=RULES)
        .on_conflict_do_nothing()
    )
    result = await session.scalar(
        select(Policy).where(
            Policy.organization_id == org, Policy.name == "mcp-review", Policy.version == "1.0.0"
        )
    )
    if result.rules != RULES:
        raise ToolFailure("POLICY_DENIED")
    return result


async def catalog(server):
    try:
        remote = await mcp_client.discover(server)
        return [{"tool": t, "fingerprint": mcp_client.digest(t)} for t in remote]
    except ToolFailure as exc:
        raise DomainError(
            exc.code, "MCP discovery failed. Check the server configuration.", 502
        ) from None


async def register(session, org: UUID, payload: MCPRegister):
    choices = await catalog(payload.server)
    selected = next((t for t in choices if t["tool"]["name"] == payload.remote_name), None)
    if selected is None or selected["fingerprint"] != payload.fingerprint:
        raise DomainError("MCP_TOOL_CHANGED", "Discover again and review the updated tool.", 409)
    binding = {
        "server": payload.server,
        "remote": selected["tool"],
        "endpoint_hash": mcp_client.digest(mcp_client.endpoint(payload.server)["url"]),
    }
    values = metadata(binding)
    await session.execute(
        insert(Tool)
        .values(organization_id=org, connection_config=binding, **values)
        .on_conflict_do_nothing()
    )
    await policy(session, org)
    await session.commit()
    return await session.scalar(
        select(Tool).where(
            Tool.organization_id == org,
            Tool.name == values["name"],
            Tool.version == values["version"],
        )
    )
