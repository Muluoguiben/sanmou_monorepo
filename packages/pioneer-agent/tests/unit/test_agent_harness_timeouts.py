from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from mcp import StdioServerParameters

from pioneer_agent.agent_harness.contracts import McpToolError
from pioneer_agent.agent_harness import RecommendationHarness, JsonJournalStore, JsonlToolLog
from pioneer_agent.agent_harness.stdio_client import StdioMcpClient
from pioneer_agent.app import game_agent


# Synthetic JSON-RPC peer: ignores exactly one phase, exits on EOF and records
# shutdown. No model, image, credentials or game input is involved.
SERVER = r'''
import json, sys
from pathlib import Path
phase, marker = sys.argv[1:]
for line in sys.stdin:
    message = json.loads(line)
    method = message.get("method")
    if "id" not in message or method == phase:
        continue
    if method == "initialize":
        result = {"protocolVersion":"2025-11-25", "capabilities":{"tools":{}},
                  "serverInfo":{"name":"silent-test", "version":"1"}}
    elif method == "tools/list":
        result = {"tools":[{"name":"session_status", "inputSchema":{"type":"object"},
                   "annotations":{"readOnlyHint":True,"destructiveHint":False,"openWorldHint":False}}]}
    else:
        result = {"content":[], "isError":False, "structuredContent":{}}
    print(json.dumps({"jsonrpc":"2.0","id":message["id"],"result":result}), flush=True)
Path(marker).write_text("closed", encoding="utf-8")
'''


class StdioDeadlineTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def client(self, phase):
        marker = self.root / (phase.replace("/", "_") + ".closed")
        return StdioMcpClient(
            StdioServerParameters(command=sys.executable, args=["-u", "-c", SERVER, phase, str(marker)]),
            expected_server_name="silent-test", required_tools={"session_status"}, exact_tools=True,
            connect_timeout_s=1.0, request_timeout_s=0.15,
        ), marker

    async def test_silent_initialization_and_catalog_are_bounded_and_cleaned(self):
        for phase in ("initialize", "tools/list"):
            with self.subTest(phase=phase):
                client, marker = self.client(phase)
                started = time.monotonic()
                with self.assertRaises(Exception):
                    async with client:
                        self.fail("silent initialization must not connect")
                self.assertLess(time.monotonic() - started, 5)
                self.assertEqual(marker.read_text(), "closed")
                self.assertIsNone(client._worker)

    async def test_silent_tool_call_closes_nested_client_and_is_not_reused(self):
        client, marker = self.client("tools/call")
        healthy, healthy_marker = self.client("never")
        async with client, healthy:
            with self.assertRaises(Exception):
                await client.call_tool("session_status", {})
            self.assertEqual(marker.read_text(), "closed")
            with self.assertRaises(McpToolError):
                await client.call_tool("session_status", {})
            self.assertFalse((await healthy.call_tool("session_status", {}))["isError"])
        self.assertEqual(healthy_marker.read_text(), "closed")

    async def test_external_cancellation_closes_owner_and_child(self):
        client, marker = self.client("tools/call")
        client._request_timeout_s = 10
        async with client:
            pending = asyncio.create_task(client.call_tool("session_status", {}))
            await asyncio.sleep(0.03)
            pending.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await pending
            self.assertEqual(marker.read_text(), "closed")
            self.assertIsNone(client._worker)

    async def test_silent_tool_failure_is_persisted_by_harness(self):
        client, marker = self.client("tools/call")
        log = JsonlToolLog(self.root / "tools.jsonl")
        store = JsonJournalStore(self.root / "journal.json")
        async with client:
            result = await RecommendationHarness(
                game_client=client, journal_store=store, tool_log=log,
                agent_session_id="silent-call", model_id="synthetic",
            ).run_decision_window()
        self.assertEqual(result.stop.reason, "tool_failure")
        self.assertIsNone(result.recommendation)
        self.assertEqual(marker.read_text(), "closed")
        self.assertFalse(log.read()[-1].success)
        self.assertEqual(log.read()[-1].tool_name, "session_status")
        self.assertEqual(store.load("silent-call").tooling.inferred[-1].inference, "stop:tool_failure")

    async def test_initialization_cancellation_closes_transport(self):
        client, marker = self.client("initialize")
        client._request_timeout_s = 10
        pending = asyncio.create_task(client.__aenter__())
        await asyncio.sleep(0.15)
        pending.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await pending
        self.assertEqual(marker.read_text(), "closed")
        self.assertIsNone(client._worker)

    async def test_connection_creation_deadline_cancels_transport(self):
        cleaned = asyncio.Event()

        @asynccontextmanager
        async def stalled_transport(*args, **kwargs):
            try:
                await asyncio.Event().wait()
                yield
            finally:
                cleaned.set()

        client, _ = self.client("initialize")
        client._connect_timeout_s = 0.03
        with patch("pioneer_agent.agent_harness.stdio_client.stdio_client", stalled_transport):
            with self.assertRaises(TimeoutError):
                async with client:
                    self.fail("connect must time out")
        self.assertTrue(cleaned.is_set())
        self.assertIsNone(client._worker)

    async def test_cli_startup_failure_writes_structured_stop_and_private_log(self):
        args = game_agent.build_parser().parse_args([
            "--screenshot", str(self.root / "unused.png"),
            "--journal-path", str(self.root / "journal.json"),
            "--tool-log-path", str(self.root / "tools.jsonl"),
            "--agent-session-id", "timeout-test",
        ])
        client, marker = self.client("initialize")
        healthy, _ = self.client("never")
        with patch.object(game_agent, "StdioMcpClient", side_effect=[client, healthy]):
            result = await game_agent.run(args)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["stop"]["reason"], "tool_failure")
        self.assertIsNone(result["recommendation"])
        self.assertEqual(marker.read_text(), "closed")
        records = [json.loads(line) for line in (self.root / "tools.jsonl").read_text().splitlines()]
        self.assertEqual(records[-1]["tool_name"], "mcp_connect:game")
        self.assertFalse(records[-1]["success"])
        self.assertEqual(records[-1]["arguments_summary"], {})
        self.assertEqual(json.loads((self.root / "journal.json").read_text())["tooling"]["inferred"][-1]["inference"], "stop:tool_failure")

    def test_nonfinite_or_unbounded_timeouts_are_rejected(self):
        for value in (0, -1, float("inf"), float("nan")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                StdioMcpClient(StdioServerParameters(command=sys.executable),
                    expected_server_name="test", required_tools=set(), request_timeout_s=value)
