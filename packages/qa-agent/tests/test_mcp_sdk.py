import asyncio
import os
from pathlib import Path
import sys
import unittest

from mcp import Client, StdioServerParameters

from qa_agent.mcp_server.server import SERVER_NAME, SERVER_VERSION, create_mcp_server
from qa_agent.mcp_server.tooling import TOOL_NAMES, KnowledgeToolHandler


class McpSdkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.project_root = Path(__file__).resolve().parents[1]
        cls.handler = KnowledgeToolHandler.from_project_root(cls.project_root)
        cls.server = create_mcp_server(cls.handler)

    def test_official_sdk_lists_six_strict_read_only_tools(self) -> None:
        async def inspect_tools() -> None:
            async with Client(self.server, raise_exceptions=True) as client:
                response = await client.list_tools()
                self.assertEqual(client.server_info.name, SERVER_NAME)
                self.assertEqual(client.server_info.version, SERVER_VERSION)
                self.assertEqual([tool.name for tool in response.tools], list(TOOL_NAMES))
                for tool in response.tools:
                    with self.subTest(tool=tool.name):
                        self.assertFalse(tool.input_schema["additionalProperties"])
                        self.assertEqual(tool.input_schema["type"], "object")
                        self.assertTrue(tool.annotations.read_only_hint)
                        self.assertFalse(tool.annotations.open_world_hint)

        asyncio.run(inspect_tools())

    def test_official_sdk_rejects_extra_fields_and_type_coercion(self) -> None:
        cases = [
            ("lookup_topic", {"topic": "建筑升级", "unexpected": True}),
            ("lookup_topic", {"topic": 1}),
            ("lookup_topic", {"topic": "建筑升级", "domain": "unknown"}),
            ("advisor_golden_replay_status", {"include_fixture_results": "false"}),
        ]

        async def assert_rejected() -> None:
            async with Client(self.server, raise_exceptions=True) as client:
                for name, arguments in cases:
                    with self.subTest(tool=name, arguments=arguments):
                        result = await client.call_tool(name, arguments)
                        self.assertTrue(result.is_error)
                        self.assertIn(f"Invalid arguments for {name}", result.content[0].text)

        asyncio.run(assert_rejected())

    def test_stdio_matches_direct_handler_for_all_six_tools(self) -> None:
        cases = [
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

        async def assert_stdio_parity() -> None:
            python_path = os.environ.get("PYTHONPATH", "")
            parameters = StdioServerParameters(
                command=sys.executable,
                args=["-m", "qa_agent.mcp_server.stdio_server"],
                cwd=self.project_root,
                env={"PYTHONPATH": python_path},
            )
            async with Client(parameters, raise_exceptions=True) as client:
                listed = await client.list_tools()
                direct_definitions = self.handler.tool_definitions()
                self.assertEqual([tool.name for tool in listed.tools], list(TOOL_NAMES))
                self.assertEqual(
                    [tool.input_schema for tool in listed.tools],
                    [definition["inputSchema"] for definition in direct_definitions],
                )
                for tool in listed.tools:
                    self.assertTrue(tool.annotations.read_only_hint)
                    self.assertFalse(tool.annotations.open_world_hint)

                for name, arguments in cases:
                    with self.subTest(tool=name):
                        expected = self.handler.call_tool(name, arguments)
                        actual = await client.call_tool(name, arguments)
                        self.assertEqual(actual.is_error, expected["isError"])
                        self.assertEqual(actual.structured_content, expected["structuredContent"])
                        self.assertEqual(actual.content[0].text, expected["content"][0]["text"])

        asyncio.run(assert_stdio_parity())


if __name__ == "__main__":
    unittest.main()
