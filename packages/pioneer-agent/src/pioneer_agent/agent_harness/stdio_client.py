"""Official-SDK stdio transport for the recommendation-only harness."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from pioneer_agent.agent_harness.contracts import McpToolError


class StdioMcpClient:
    """Bounded MCP client that accepts only a read-only server surface."""

    def __init__(
        self,
        parameters: StdioServerParameters,
        *,
        expected_server_name: str,
        required_tools: Collection[str],
        exact_tools: bool = False,
    ) -> None:
        self._parameters = parameters
        self._expected_server_name = expected_server_name
        self._required_tools = frozenset(required_tools)
        self._exact_tools = exact_tools
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._available_tools: frozenset[str] = frozenset()

    async def __aenter__(self) -> StdioMcpClient:
        stack = AsyncExitStack()
        try:
            read, write = await stack.enter_async_context(stdio_client(self._parameters))
            session = await stack.enter_async_context(ClientSession(read, write))
            initialized = await session.initialize()
            if initialized.serverInfo.name != self._expected_server_name:
                raise McpToolError(
                    "unexpected MCP server identity: "
                    f"{initialized.serverInfo.name!r}"
                )
            listed = await session.list_tools()
            names = frozenset(tool.name for tool in listed.tools)
            if not self._required_tools.issubset(names):
                missing = sorted(self._required_tools - names)
                raise McpToolError(f"MCP server is missing required tools: {missing}")
            if self._exact_tools and names != self._required_tools:
                unexpected = sorted(names - self._required_tools)
                raise McpToolError(f"MCP server exposes unexpected tools: {unexpected}")
            for tool in listed.tools:
                annotations = tool.annotations
                if (
                    annotations is None
                    or annotations.readOnlyHint is not True
                    or annotations.destructiveHint is not False
                    or annotations.openWorldHint is not False
                ):
                    raise McpToolError(
                        f"MCP tool is not closed-world read-only: {tool.name}"
                    )
        except Exception:
            await stack.aclose()
            raise
        self._stack = stack
        self._session = session
        self._available_tools = names
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:  # noqa: ANN001
        stack = self._stack
        self._session = None
        self._stack = None
        self._available_tools = frozenset()
        if stack is not None:
            await stack.aclose()

    async def call_tool(
        self,
        name: str,
        arguments: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        if self._session is None:
            raise McpToolError("stdio MCP client is not connected")
        if name not in self._available_tools:
            raise McpToolError(f"tool is outside the initialized MCP surface: {name}")
        result = await self._session.call_tool(name, dict(arguments))
        return {
            "isError": bool(result.isError),
            "structuredContent": result.structuredContent,
        }
