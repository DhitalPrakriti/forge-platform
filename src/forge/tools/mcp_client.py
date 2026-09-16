"""Bounded MCP transport. Only operator-configured endpoints can be contacted."""

import asyncio
import hashlib
import json
import logging
import re
from contextlib import asynccontextmanager
from datetime import timedelta
from urllib.parse import urlsplit

import httpx
from jsonschema import Draft202012Validator
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from forge.tools.builtins import ToolFailure

# SDK transport tracebacks may include server payloads. FORGE records safe error codes instead.
for _logger in ("mcp.client.streamable_http", "mcp.shared.session", "mcp.client.session", "client"):
    logging.getLogger(_logger).disabled = True


class MCPSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FORGE_", env_file=".env", extra="ignore")
    mcp_servers: SecretStr = SecretStr("{}")


def servers():
    try:
        entries = json.loads(MCPSettings().mcp_servers.get_secret_value())
        if not isinstance(entries, dict) or len(entries) > 20:
            raise ValueError
        for key, value in entries.items():
            if not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", key):
                raise ValueError
            url = urlsplit(value["url"])
            if (
                (
                    url.scheme != "https"
                    and not (
                        url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}
                    )
                )
                or not url.hostname
                or url.username
                or url.password
                or url.query
                or url.fragment
            ):
                raise ValueError
            if not isinstance(value.get("token", ""), str):
                raise ValueError
        return entries
    except Exception:
        raise ToolFailure("MCP_CONFIGURATION_INVALID") from None


def endpoint(key):
    config = servers().get(key)
    if config is None:
        raise ToolFailure("MCP_SERVER_UNAVAILABLE")
    return config


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def check_schema(schema):
    # Deliberately bounded portable subset; no remote refs, regex execution or recursive schemas.
    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise ToolFailure("MCP_SCHEMA_UNSUPPORTED")
    if len(json.dumps(schema)) > 16_000:
        raise ToolFailure("MCP_SCHEMA_UNSUPPORTED")

    def walk(value, depth=0):
        if depth > 20:
            raise ToolFailure("MCP_SCHEMA_UNSUPPORTED")
        if not isinstance(value, dict):
            return
        if any(
            k in value
            for k in ("$ref", "$dynamicRef", "$recursiveRef", "pattern", "patternProperties")
        ):
            raise ToolFailure("MCP_SCHEMA_UNSUPPORTED")
        for key in ("properties", "$defs", "definitions", "dependentSchemas"):
            mapping = value.get(key, {})
            if isinstance(mapping, dict):
                for child in mapping.values():
                    walk(child, depth + 1)
        for key in (
            "items",
            "additionalProperties",
            "unevaluatedProperties",
            "unevaluatedItems",
            "propertyNames",
            "contains",
            "not",
            "if",
            "then",
            "else",
        ):
            walk(value.get(key), depth + 1)
        for key in ("allOf", "anyOf", "oneOf", "prefixItems"):
            children = value.get(key, [])
            if isinstance(children, list):
                for child in children:
                    walk(child, depth + 1)

    walk(schema)
    try:
        Draft202012Validator.check_schema(schema)
    except Exception:
        raise ToolFailure("MCP_SCHEMA_UNSUPPORTED") from None


def snapshot(tool):
    value = tool.model_dump(mode="json", by_alias=True, exclude_none=True)
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", value["name"]):
        raise ToolFailure("MCP_SCHEMA_UNSUPPORTED")
    if len(value.get("description", "")) > 4000:
        raise ToolFailure("MCP_SCHEMA_UNSUPPORTED")
    check_schema(value["inputSchema"])
    if value.get("outputSchema"):
        check_schema(value["outputSchema"])
    return value


class BoundedStream(httpx.AsyncByteStream):
    def __init__(self, stream):
        self.stream = stream

    async def __aiter__(self):
        size = 0
        async for chunk in self.stream:
            size += len(chunk)
            if size > 1_000_000:
                raise ToolFailure("MCP_RESPONSE_TOO_LARGE")
            yield chunk

    async def aclose(self):
        await self.stream.aclose()


@asynccontextmanager
async def connection(key, expected_endpoint=None):
    config = endpoint(key)
    if expected_endpoint and digest(config["url"]) != expected_endpoint:
        raise ToolFailure("MCP_ENDPOINT_CHANGED")
    headers = {"Accept-Encoding": "identity"}
    if config.get("token"):
        headers["Authorization"] = "Bearer " + config["token"]

    async def block_redirect(response):
        if response.is_redirect:
            raise ToolFailure("MCP_REDIRECT_REJECTED")
        if response.headers.get("content-encoding", "identity") != "identity":
            raise ToolFailure("MCP_ENCODING_UNSUPPORTED")
        response.stream = BoundedStream(response.stream)

    try:
        async with asyncio.timeout(25):
            async with httpx.AsyncClient(
                headers=headers,
                timeout=20,
                trust_env=False,
                follow_redirects=False,
                event_hooks={"response": [block_redirect]},
            ) as http:
                async with streamable_http_client(config["url"], http_client=http) as streams:
                    async with ClientSession(
                        streams[0], streams[1], read_timeout_seconds=timedelta(seconds=20)
                    ) as client:
                        await client.initialize()
                        yield client
    except ToolFailure:
        raise
    except ExceptionGroup as exc:
        # anyio task groups wrap application errors; retain only our controlled code.
        pending = list(exc.exceptions)
        while pending:
            error = pending.pop()
            if isinstance(error, ToolFailure):
                raise ToolFailure(error.code) from None
            if isinstance(error, ExceptionGroup):
                pending.extend(error.exceptions)
        raise ToolFailure("MCP_CONNECTION_FAILED") from None
    except Exception:
        # Never persist or return SDK errors: they may contain URLs or credentials.
        raise ToolFailure("MCP_CONNECTION_FAILED") from None


async def list_remote(client):
    found, cursor, seen = [], None, set()
    for _ in range(10):
        page = await client.list_tools(cursor=cursor)
        for tool in page.tools:
            if tool.name in seen:
                raise ToolFailure("MCP_DUPLICATE_TOOL")
            seen.add(tool.name)
            value = snapshot(tool)
            found.append(value)
            if len(found) > 100:
                raise ToolFailure("MCP_CATALOG_TOO_LARGE")
        cursor = page.nextCursor
        if not cursor:
            return found
    raise ToolFailure("MCP_CATALOG_TOO_LARGE")


async def discover(key):
    async with connection(key) as client:
        return await list_remote(client)


async def execute(binding, arguments):
    async with connection(binding["server"], binding["endpoint_hash"]) as client:
        current = next(
            (t for t in await list_remote(client) if t["name"] == binding["remote"]["name"]), None
        )
        if current != binding["remote"]:
            raise ToolFailure("MCP_TOOL_CHANGED")
        result = await client.call_tool(current["name"], arguments)
        if result.isError:
            raise ToolFailure("MCP_TOOL_FAILED")
        output = result.model_dump(mode="json", by_alias=True, exclude_none=True)
        if len(json.dumps(output).encode()) > 64_000:
            raise ToolFailure("TOOL_OUTPUT_TOO_LARGE")
        if any(c.get("type") != "text" for c in output.get("content", [])):
            raise ToolFailure("MCP_OUTPUT_UNSUPPORTED")
        if current.get("outputSchema"):
            if not Draft202012Validator(current["outputSchema"]).is_valid(
                output.get("structuredContent")
            ):
                raise ToolFailure("TOOL_OUTPUT_INVALID")
        return output
