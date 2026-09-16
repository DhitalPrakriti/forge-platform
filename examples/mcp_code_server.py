"""Local MCP example: inspect pasted Python without executing it or accessing files."""

import argparse
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from forge.tools.python_inspection import PythonOutput, inspect_python


def make_server(port=8040):
    server = FastMCP(
        "FORGE code inspection",
        host="127.0.0.1",
        port=port,
        json_response=True,
        stateless_http=True,
    )

    @server.tool()
    def inspect_code(code: Annotated[str, Field(min_length=1, max_length=12000)]) -> PythonOutput:
        """Inspect Python syntax, functions, imports and division lines. Never executes code."""
        return PythonOutput(**inspect_python(code))

    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8040)
    args = parser.parse_args()
    make_server(args.port).run(transport="streamable-http")
