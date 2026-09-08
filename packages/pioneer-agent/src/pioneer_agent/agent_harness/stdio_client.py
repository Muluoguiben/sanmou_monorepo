"""Official-SDK stdio transport for the recommendation-only harness."""

from __future__ import annotations

import asyncio
import math
from datetime import timedelta

from collections.abc import Collection, Mapping
from contextlib import AsyncExitStack
from typing import Any

from anyio.streams.memory import MemoryObjectReceiveStream
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
        connect_timeout_s: float = 30.0,
        request_timeout_s: float = 60.0,
    ) -> None:
        for value in (connect_timeout_s, request_timeout_s):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("MCP timeouts must be finite and positive")
        self._connect_timeout_s = connect_timeout_s
        self._request_timeout_s = request_timeout_s
        self._parameters = parameters
        self._expected_server_name = expected_server_name
        self._required_tools = frozenset(required_tools)
        self._exact_tools = exact_tools
        self._worker: asyncio.Task | None = None
        self._ready: asyncio.Future | None = None
        self._requests: asyncio.Queue = asyncio.Queue()
        self._closing = False
        self._session: ClientSession | None = None
        self._available_tools: frozenset[str] = frozenset()

    async def __aenter__(self) -> StdioMcpClient:
        if self._worker is not None:
            raise McpToolError("stdio MCP client is already connected")
        self._ready = asyncio.get_running_loop().create_future()
        self._requests = asyncio.Queue()
        self._closing = False
        self._worker = asyncio.create_task(self._serve())
        try:
            async with asyncio.timeout(self._connect_timeout_s):
                await asyncio.shield(self._ready)
        except BaseException:
            await self._close()
            raise
        return self

    async def _serve(self) -> None:
        # SDK contexts own AnyIO cancel scopes. Enter, call and close them in a
        # single task, even when game and QA clients are nested or cancelled.
        stack = AsyncExitStack()
        response = None
        shutdown_read = None
        try:
            read, write = await stack.enter_async_context(stdio_client(self._parameters))
            # ClientSession closes its receive endpoint before stdio's reader
            # task stops. Keep a dormant endpoint alive for that shutdown gap.
            shutdown_read = read.clone()
            session = await stack.enter_async_context(ClientSession(
                read, write,
                read_timeout_seconds=timedelta(seconds=self._connect_timeout_s),
            ))
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
            self._session = session
            self._available_tools = names
            self._ready.set_result(None)
            while True:
                name, arguments, response = await self._requests.get()
                try:
                    result = await session.call_tool(
                        name, arguments,
                        read_timeout_seconds=timedelta(seconds=self._request_timeout_s),
                    )
                    if not response.done():
                        response.set_result({
                            "isError": bool(result.isError),
                            "structuredContent": result.structuredContent,
                        })
                except Exception as exc:
                    if not response.done():
                        response.set_exception(exc)
                    return
        except BaseException as exc:
            if not self._ready.done():
                if isinstance(exc, asyncio.CancelledError):
                    self._ready.cancel()
                else:
                    self._ready.set_exception(exc)
            elif response is not None and not response.done():
                response.set_exception(McpToolError("MCP transport stopped"))
        finally:
            self._closing = True
            self._session = None
            self._available_tools = frozenset()
            # Only after advice/calls have stopped may a drain consume late
            # responses. During normal operation the clone never reads data.
            drain = asyncio.create_task(_drain_shutdown(shutdown_read)) if shutdown_read is not None else None
            try:
                # SDK shutdown closes stdin and terminates the child on timeout.
                # Preserve owner-task scope ordering; do not suppress cleanup errors.
                async with asyncio.timeout(10.0):
                    await stack.aclose()
            finally:
                if drain is not None:
                    drain.cancel()
                    try:
                        await drain
                    except asyncio.CancelledError:
                        pass
                    finally:
                        # aclose can complete without scheduling the new task;
                        # then cancellation happens before its async-with starts.
                        await shutdown_read.aclose()

    async def _close(self) -> None:
        worker, self._worker = self._worker, None
        self._session = None
        self._available_tools = frozenset()
        if worker is not None:
            if not worker.done() and not self._closing:
                worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass
            finally:
                # Cancellation can win just before the owner publishes its
                # initialization error, leaving no waiter on the ready future.
                if self._ready is not None and self._ready.done() and not self._ready.cancelled():
                    self._ready.exception()

    async def __aexit__(self, exc_type, exc, traceback) -> None:  # noqa: ANN001
        await self._close()

    async def call_tool(
        self,
        name: str,
        arguments: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        if self._session is None:
            raise McpToolError("stdio MCP client is not connected")
        if name not in self._available_tools:
            raise McpToolError(f"tool is outside the initialized MCP surface: {name}")
        response = asyncio.get_running_loop().create_future()
        try:
            async with asyncio.timeout(self._request_timeout_s):
                await self._requests.put((name, dict(arguments), response))
                return await response
        except BaseException:
            await self._close()
            raise


async def _drain_shutdown(read: MemoryObjectReceiveStream) -> None:
    async with read:
        async for _ in read:
            pass
