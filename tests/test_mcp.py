import asyncio
import json

import pytest
from mcp.types import Tool as RemoteTool

from forge.tools import mcp_client
from forge.tools.builtins import ToolFailure
from forge.tools.mcp_registry import metadata, validate_binding
from forge.tools.models import Tool


def remote():
    return {
        "name": "add",
        "description": "Add numbers",
        "inputSchema": {
            "type": "object",
            "properties": {"a": {"type": "integer"}},
            "required": ["a"],
            "additionalProperties": False,
        },
    }


def test_snapshot_and_schema_constraints():
    assert mcp_client.snapshot(RemoteTool(**remote())) == remote()
    for schema in (
        {"type": "object", "$ref": "https://example.com/schema"},
        {"type": "object", "properties": {"x": {"pattern": ".*"}}},
        {"type": "array"},
    ):
        with pytest.raises(ToolFailure):
            mcp_client.check_schema(schema)


def test_server_config_no_browser_urls_or_secret_metadata(monkeypatch):
    monkeypatch.setenv(
        "FORGE_MCP_SERVERS",
        json.dumps({"code": {"url": "https://example.com/mcp", "token": "private-test-token"}}),
    )
    binding = {
        "server": "code",
        "endpoint_hash": mcp_client.digest("https://example.com/mcp"),
        "remote": remote(),
    }
    tool = Tool(**metadata(binding), connection_config=binding, status="ACTIVE")
    validate_binding(tool)
    assert "private-test-token" not in json.dumps(metadata(binding))
    monkeypatch.setenv("FORGE_MCP_SERVERS", '{"code":{"url":"https://other.example/mcp"}}')
    with pytest.raises(ToolFailure, match="MCP_ENDPOINT_CHANGED"):
        validate_binding(tool)
    with pytest.raises(ToolFailure):
        mcp_client.endpoint("unconfigured")


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://example.com/mcp",
        "https://user:secret@example.com/mcp",
        "https://example.com/?key=secret",
    ],
)
def test_invalid_endpoints(monkeypatch, url):
    monkeypatch.setenv("FORGE_MCP_SERVERS", json.dumps({"code": {"url": url}}))
    with pytest.raises(ToolFailure):
        mcp_client.servers()


def test_duplicate_discovery_rejected():
    class Client:
        async def list_tools(self, cursor=None):
            from mcp.types import ListToolsResult

            return ListToolsResult(tools=[RemoteTool(**remote()), RemoteTool(**remote())])

    with pytest.raises(ToolFailure):
        asyncio.run(mcp_client.list_remote(Client()))


def test_real_streamable_http_discovery_execution_and_drift(monkeypatch):
    """Exercise the SDK against a real loopback MCP server; no paid provider calls."""
    import socket
    import subprocess
    import sys
    import time

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen(
        [sys.executable, "examples/mcp_code_server.py", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    monkeypatch.setenv(
        "FORGE_MCP_SERVERS", json.dumps({"code": {"url": f"http://127.0.0.1:{port}/mcp"}})
    )
    try:
        for _ in range(100):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    break
            except OSError:
                if process.poll() is not None:
                    pytest.fail("Example MCP server failed to start")
                time.sleep(0.05)

        async def exercise():
            tools = await mcp_client.discover("code")
            tool = next(t for t in tools if t["name"] == "inspect_code")
            binding = {
                "server": "code",
                "endpoint_hash": mcp_client.digest(f"http://127.0.0.1:{port}/mcp"),
                "remote": tool,
            }
            result = await mcp_client.execute(
                binding, {"code": "def average(xs):\n    return sum(xs) / len(xs)"}
            )
            assert result["structuredContent"]["functions"] == ["average"]
            assert result["structuredContent"]["executed"] is False
            binding["remote"] = {**tool, "description": "Changed description"}
            with pytest.raises(ToolFailure, match="MCP_TOOL_CHANGED"):
                await mcp_client.execute(binding, {"code": "x=1"})

        asyncio.run(exercise())
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_pattern_named_argument_is_not_a_regex_constraint():
    mcp_client.check_schema({"type": "object", "properties": {"pattern": {"type": "string"}}})


def test_transport_refuses_redirect_before_forwarding_credentials(monkeypatch):
    import httpx

    monkeypatch.setenv(
        "FORGE_MCP_SERVERS", '{"code":{"url":"https://example.com/mcp","token":"secret"}}'
    )
    requests = []

    def handle(request):
        requests.append(str(request.url))
        return httpx.Response(307, headers={"Location": "https://other.example/mcp"})

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs),
    )
    with pytest.raises(ToolFailure, match="MCP_REDIRECT_REJECTED"):
        asyncio.run(mcp_client.discover("code"))
    assert requests == ["https://example.com/mcp"]
