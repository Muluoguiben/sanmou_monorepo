from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import anyio
from mcp import StdioServerParameters

from pioneer_agent.agent_harness.stdio_client import StdioMcpClient

if __package__:
    from .test_agent_harness_timeouts import SERVER
else:
    from test_agent_harness_timeouts import SERVER


class ShutdownRaceTests(unittest.IsolatedAsyncioTestCase):
    def peer(self, phase, *, cleanup_error=None, with_late_response=True, continuous_output=False):
        incoming, read = anyio.create_memory_object_stream(0)
        write, outgoing = anyio.create_memory_object_stream(0)
        session_closed = asyncio.Event()
        delivered = asyncio.Event()
        initialized = asyncio.Event()
        primary = TimeoutError("synthetic primary deadline")

        @asynccontextmanager
        async def transport(*args, **kwargs):
            if not with_late_response:
                try:
                    yield read, write
                finally:
                    await incoming.aclose()
                    await read.aclose()
                    await write.aclose()
                    await outgoing.aclose()
                return

            async def late_stdout():
                await session_closed.wait()
                # Force the same late-send ordering as the SDK stdout_reader.
                await incoming.send(object())
                delivered.set()
                if continuous_output:
                    while True:
                        await incoming.send(object())

            try:
                async with anyio.create_task_group() as group:
                    group.start_soon(late_stdout)
                    try:
                        yield read, write
                    finally:
                        with anyio.fail_after(1):
                            await delivered.wait()
                        if cleanup_error is not None:
                            raise cleanup_error
            finally:
                await incoming.aclose()
                await read.aclose()
                await write.aclose()
                await outgoing.aclose()

        class Session:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                await read.aclose()
                session_closed.set()

            async def initialize(self):
                initialized.set()
                if phase in ("cancel", "cancel_error"):
                    try:
                        await asyncio.Event().wait()
                    except asyncio.CancelledError:
                        if phase == "cancel_error":
                            raise primary
                        raise
                if phase == "initialize":
                    raise primary
                return SimpleNamespace(serverInfo=SimpleNamespace(name="race-test"))

            async def list_tools(self):
                if phase == "list":
                    raise primary
                return SimpleNamespace(tools=[SimpleNamespace(
                    name="session_status", annotations=SimpleNamespace(
                        readOnlyHint=True, destructiveHint=False, openWorldHint=False,
                    ),
                )])

            async def call_tool(self, *args, **kwargs):
                if phase == "call":
                    raise primary
                if phase == "response":
                    sender = asyncio.create_task(incoming.send("normal response"))
                    result = await read.receive()
                    await sender
                    return SimpleNamespace(isError=False, structuredContent={"value": result})
                return SimpleNamespace(isError=False, structuredContent={})

        client = StdioMcpClient(
            StdioServerParameters(command=sys.executable), expected_server_name="race-test",
            required_tools={"session_status"}, connect_timeout_s=2, request_timeout_s=1,
        )
        return client, transport, Session, primary, read, delivered, initialized

    async def test_late_stdout_after_session_close_preserves_original_deadline(self):
        for phase in ("initialize", "list", "call"):
            with self.subTest(phase=phase):
                client, transport, session, primary, read, delivered, _ = self.peer(phase)
                with patch("pioneer_agent.agent_harness.stdio_client.stdio_client", transport), patch(
                    "pioneer_agent.agent_harness.stdio_client.ClientSession", session,
                ):
                    with self.assertRaises(TimeoutError) as caught:
                        async with client:
                            await client.call_tool("session_status", {})
                self.assertIs(caught.exception, primary)
                self.assertTrue(delivered.is_set())
                self.assertEqual(read.statistics().open_receive_streams, 0)
                self.assertIsNone(client._worker)

    async def test_cancelled_initialization_drains_late_stdout(self):
        client, transport, session, _, read, delivered, initialized = self.peer("cancel")
        with patch("pioneer_agent.agent_harness.stdio_client.stdio_client", transport), patch(
            "pioneer_agent.agent_harness.stdio_client.ClientSession", session,
        ):
            pending = asyncio.create_task(client.__aenter__())
            await initialized.wait()
            pending.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await pending
        self.assertTrue(delivered.is_set())
        self.assertEqual(read.statistics().open_receive_streams, 0)

    async def test_cancel_and_initialize_error_race_retrieves_ready_exception(self):
        class TrackedFuture(asyncio.Future):
            retrieved = False

            def exception(self):
                self.retrieved = True
                return super().exception()

        loop = asyncio.get_running_loop()
        client, transport, session, _, read, _, initialized = self.peer("cancel_error")
        with patch("pioneer_agent.agent_harness.stdio_client.stdio_client", transport), patch(
            "pioneer_agent.agent_harness.stdio_client.ClientSession", session,
        ), patch.object(loop, "create_future", side_effect=lambda: TrackedFuture(loop=loop)):
            pending = asyncio.create_task(client.__aenter__())
            await initialized.wait()
            pending.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await pending
        try:
            self.assertTrue(client._ready.retrieved)
            self.assertEqual(read.statistics().open_receive_streams, 0)
        finally:
            client._ready.exception()

    async def test_unrelated_cleanup_exception_is_not_suppressed(self):
        client, transport, session, _, read, delivered, _ = self.peer(
            "ok", cleanup_error=ValueError("synthetic unrelated cleanup error"),
        )
        with patch("pioneer_agent.agent_harness.stdio_client.stdio_client", transport), patch(
            "pioneer_agent.agent_harness.stdio_client.ClientSession", session,
        ):
            with self.assertRaises(ExceptionGroup) as caught:
                async with client:
                    pass
        self.assertTrue(delivered.is_set())
        self.assertEqual(read.statistics().open_receive_streams, 0)
        self.assertEqual(len(caught.exception.exceptions), 1)
        self.assertIsInstance(caught.exception.exceptions[0], ValueError)

    async def test_mixed_cleanup_exception_group_is_preserved(self):
        mixed = ExceptionGroup("synthetic mixed failure", [
            anyio.BrokenResourceError(), ValueError("unexpected cleanup failure"),
        ])
        client, transport, session, _, read, delivered, _ = self.peer("ok", cleanup_error=mixed)
        with patch("pioneer_agent.agent_harness.stdio_client.stdio_client", transport), patch(
            "pioneer_agent.agent_harness.stdio_client.ClientSession", session,
        ):
            with self.assertRaises(ExceptionGroup) as caught:
                async with client:
                    pass
        self.assertTrue(delivered.is_set())
        self.assertEqual(read.statistics().open_receive_streams, 0)
        self.assertIs(caught.exception.exceptions[0], mixed)

    async def test_immediate_shutdown_closes_dormant_receive_endpoint(self):
        client, transport, session, _, read, _, _ = self.peer("ok", with_late_response=False)
        with patch("pioneer_agent.agent_harness.stdio_client.stdio_client", transport), patch(
            "pioneer_agent.agent_harness.stdio_client.ClientSession", session,
        ):
            async with client:
                pass
        self.assertEqual(read.statistics().open_receive_streams, 0)
        self.assertIsNone(client._worker)

    async def test_normal_response_is_not_consumed_by_shutdown_drain(self):
        tasks_before = asyncio.all_tasks()
        client, transport, session, _, read, _, _ = self.peer("response")
        with patch("pioneer_agent.agent_harness.stdio_client.stdio_client", transport), patch(
            "pioneer_agent.agent_harness.stdio_client.ClientSession", session,
        ):
            async with client:
                result = await client.call_tool("session_status", {})
                self.assertEqual(result["structuredContent"], {"value": "normal response"})
            await client._close()
        self.assertEqual(read.statistics().open_receive_streams, 0)
        self.assertEqual(asyncio.all_tasks(), tasks_before)

    async def test_continuous_late_output_cannot_outlive_shutdown_budget(self):
        tasks_before = asyncio.all_tasks()
        client, transport, session, _, read, delivered, _ = self.peer("ok", continuous_output=True)
        real_timeout = asyncio.timeout
        budgets = []

        def scaled_timeout(seconds):
            budgets.append(seconds)
            # Production must still request its exact 10-second shutdown limit.
            # Scale only that deadline in this deterministic bounded test.
            return real_timeout(0.03 if seconds == 10.0 else seconds)

        with patch("pioneer_agent.agent_harness.stdio_client.stdio_client", transport), patch(
            "pioneer_agent.agent_harness.stdio_client.ClientSession", session,
        ), patch("pioneer_agent.agent_harness.stdio_client.asyncio.timeout", scaled_timeout):
            with self.assertRaises(TimeoutError):
                async with client:
                    pass
        self.assertIn(10.0, budgets)
        self.assertTrue(delivered.is_set())
        self.assertEqual(read.statistics().open_receive_streams, 0)
        self.assertEqual(asyncio.all_tasks(), tasks_before)

    async def test_nested_real_clients_and_repeated_close_leave_no_tasks(self):
        tasks_before = asyncio.all_tasks()
        with TemporaryDirectory() as tmp:
            def client(phase):
                return StdioMcpClient(
                    StdioServerParameters(command=sys.executable, args=[
                        "-u", "-c", SERVER, phase, str(Path(tmp) / phase.replace("/", "_")),
                    ]),
                    expected_server_name="silent-test", required_tools={"session_status"},
                    connect_timeout_s=1,
                    # Only the intentionally silent outer request is timed out;
                    # the healthy peer uses the normal production call budget.
                    **({"request_timeout_s": 0.03} if phase == "tools/call" else {}),
                )
            outer, inner = client("tools/call"), client("never")
            async with outer, inner:
                with self.assertRaises(Exception):
                    await outer.call_tool("session_status", {})
                self.assertFalse((await inner.call_tool("session_status", {}))["isError"])
            await outer._close()
            await inner._close()
        self.assertEqual(asyncio.all_tasks(), tasks_before)

    async def test_initialize_uses_connect_budget_not_tool_request_budget(self):
        # Real child: initialize is slower than a tool's deadline but remains
        # inside the unchanged connect deadline. The subsequent tool is silent.
        server = SERVER.replace("import json, sys", "import json, sys, time")
        server = server.replace('if method == "initialize":', 'if method == "initialize":\n        time.sleep(0.15)')
        with TemporaryDirectory() as tmp:
            marker = Path(tmp) / "closed"
            client = StdioMcpClient(
                StdioServerParameters(command=sys.executable, args=["-u", "-c", server, "tools/call", str(marker)]),
                expected_server_name="silent-test", required_tools={"session_status"},
                connect_timeout_s=1, request_timeout_s=0.03,
            )
            async with client:
                with self.assertRaises(Exception):
                    await client.call_tool("session_status", {})
            self.assertEqual(marker.read_text(), "closed")

    async def test_real_child_continuing_output_is_terminated_on_shutdown(self):
        server = SERVER.replace("import json, sys", "import json, sys, os, time")
        server = server.replace('"structuredContent":{}', '"structuredContent":{"pid":os.getpid()}')
        # The synthetic peer ignores EOF for a bounded 30 seconds, longer than
        # the production shutdown budget, while sending valid notifications.
        server += '''
end = time.monotonic() + 30
while time.monotonic() < end:
    print(json.dumps({"jsonrpc":"2.0","method":"notifications/message",
                      "params":{"level":"debug","data":"synthetic late output"}}), flush=True)
    time.sleep(0.01)
'''
        tasks_before = asyncio.all_tasks()
        with TemporaryDirectory() as tmp:
            marker = Path(tmp) / "received-eof"
            client = StdioMcpClient(
                StdioServerParameters(command=sys.executable, args=["-u", "-c", server, "never", str(marker)]),
                expected_server_name="silent-test", required_tools={"session_status"},
                connect_timeout_s=1, request_timeout_s=1,
            )
            async with asyncio.timeout(12):
                async with client:
                    response = await client.call_tool("session_status", {})
                    pid = response["structuredContent"]["pid"]
            self.assertEqual(marker.read_text(), "closed")
            if os.name == "nt":
                import ctypes
                from ctypes import wintypes

                kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
                kernel.OpenProcess.restype = wintypes.HANDLE
                kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
                kernel.CloseHandle.argtypes = [wintypes.HANDLE]
                handle = kernel.OpenProcess(0x00100000, False, pid)
                if handle:
                    try:
                        self.assertEqual(kernel.WaitForSingleObject(handle, 0), 0)
                    finally:
                        kernel.CloseHandle(handle)
            else:
                with self.assertRaises(ProcessLookupError):
                    os.kill(pid, 0)
        self.assertEqual(asyncio.all_tasks(), tasks_before)
