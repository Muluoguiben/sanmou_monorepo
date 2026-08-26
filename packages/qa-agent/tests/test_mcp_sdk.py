import asyncio
import os
from pathlib import Path
import sys
import unittest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.memory import create_connected_server_and_client_session

from qa_agent.mcp_server.server import SERVER_NAME, SERVER_VERSION, create_mcp_server
from qa_agent.mcp_server.tooling import TOOL_NAMES, KnowledgeToolHandler


TOOL_CASES = [
    ("lookup_topic", {"topic": "建筑升级"}),
    ("answer_rule_question", {"question": "体力不足时怎么办？", "domain": "team"}),
    ("resolve_term", {"term": "补兵"}),
    ("advisor_golden_replay_status", {"include_fixture_results": False}),
    ("advisor_fixture_eval", {"fixture": "chapter_claimable_state.json"}),
    (
        "advisor_terminal_source_evidence_eval",
        {
            "action_type": "claim_chapter_reward",
            "terminal_source_evidence": {},
        },
    ),
]

REJECTED_CASES = [
    ("lookup_topic", {"topic": "建筑升级", "unexpected": True}),
    ("lookup_topic", {"topic": 1}),
    ("lookup_topic", {"topic": "建筑升级", "domain": "unknown"}),
    ("advisor_golden_replay_status", {"include_fixture_results": "false"}),
    (
        "advisor_terminal_source_evidence_eval",
        {
            "action_type": "claim_chapter_reward",
            "terminal_source_evidence": "{}",
        },
    ),
]


class McpSdkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.project_root = Path(__file__).resolve().parents[1]
        cls.handler = KnowledgeToolHandler.from_project_root(cls.project_root)
        cls.server = create_mcp_server(cls.handler)

    async def _assert_tool_contract(self, session: ClientSession) -> None:
        response = await session.list_tools()
        self.assertEqual([tool.name for tool in response.tools], list(TOOL_NAMES))
        self.assertEqual(
            [tool.inputSchema for tool in response.tools],
            [definition["inputSchema"] for definition in self.handler.tool_definitions()],
        )
        for tool in response.tools:
            with self.subTest(tool=tool.name):
                self.assertFalse(tool.inputSchema["additionalProperties"])
                self.assertEqual(tool.inputSchema["type"], "object")
                self.assertTrue(tool.annotations.readOnlyHint)
                self.assertFalse(tool.annotations.destructiveHint)
                self.assertTrue(tool.annotations.idempotentHint)
                self.assertFalse(tool.annotations.openWorldHint)

    async def _assert_success_parity(self, session: ClientSession) -> None:
        for name, arguments in TOOL_CASES:
            with self.subTest(tool=name):
                expected = self.handler.call_tool(name, arguments)
                actual = await session.call_tool(name, arguments)
                self.assertEqual(actual.isError, expected["isError"])
                self.assertEqual(actual.structuredContent, expected["structuredContent"])
                self.assertEqual(
                    [
                        item.model_dump(mode="json", by_alias=True, exclude_none=True)
                        for item in actual.content
                    ],
                    expected["content"],
                )

    async def _collect_rejections(self, session: ClientSession) -> list[dict]:
        results = []
        for name, arguments in REJECTED_CASES:
            with self.subTest(tool=name, arguments=arguments):
                result = await session.call_tool(name, arguments)
                self.assertTrue(result.isError)
                self.assertIsNone(result.structuredContent)
                self.assertIn(f"Invalid arguments for {name}", result.content[0].text)
                results.append(result.model_dump(mode="json", by_alias=True, exclude_none=True))
        return results

    def test_in_memory_official_client_contract_and_parity(self) -> None:
        async def inspect() -> None:
            async with create_connected_server_and_client_session(self.server) as session:
                await self._assert_tool_contract(session)
                await self._assert_success_parity(session)

        asyncio.run(inspect())

    def test_in_memory_official_client_rejects_extra_enum_and_types(self) -> None:
        async def inspect() -> None:
            async with create_connected_server_and_client_session(self.server) as session:
                await self._collect_rejections(session)

        asyncio.run(inspect())

    def test_stdio_matches_in_memory_for_successes_and_errors(self) -> None:
        async def inspect() -> None:
            async with create_connected_server_and_client_session(self.server) as memory_session:
                expected_errors = await self._collect_rejections(memory_session)

            parameters = StdioServerParameters(
                command=sys.executable,
                args=["-m", "qa_agent.mcp_server.stdio_server"],
                cwd=self.project_root,
                env={"PYTHONPATH": os.environ.get("PYTHONPATH", "")},
            )
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as session:
                    initialized = await session.initialize()
                    self.assertEqual(initialized.serverInfo.name, SERVER_NAME)
                    self.assertEqual(initialized.serverInfo.version, SERVER_VERSION)
                    await self._assert_tool_contract(session)
                    await self._assert_success_parity(session)
                    self.assertEqual(await self._collect_rejections(session), expected_errors)

        asyncio.run(inspect())


if __name__ == "__main__":
    unittest.main()
