from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys
import unittest

from mcp import StdioServerParameters

from pioneer_agent.agent_harness.contracts import QA_READ_ONLY_TOOLS
from pioneer_agent.agent_harness.stdio_client import StdioMcpClient
from pioneer_agent.mcp_server.contracts import GAME_TOOL_ALLOWLIST, SERVER_NAME


class AgentHarnessStdioClientTests(unittest.TestCase):
    def test_official_stdio_clients_bind_real_game_and_qa_servers(self) -> None:
        repo_root = Path(__file__).resolve().parents[4]
        pioneer_root = repo_root / "packages" / "pioneer-agent"
        qa_root = repo_root / "packages" / "qa-agent"
        common_src = repo_root / "packages" / "sanmou-common" / "src"
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            [
                str(pioneer_root / "src"),
                str(qa_root / "src"),
                str(common_src),
                env.get("PYTHONPATH", ""),
            ]
        )

        async def exercise() -> None:
            game = StdioMcpClient(
                StdioServerParameters(
                    command=sys.executable,
                    args=["-m", "pioneer_agent.mcp_server"],
                    cwd=pioneer_root,
                    env={
                        **env,
                        "SANMOU_GAME_FIXTURE_ROOT": str(pioneer_root / "tests" / "fixtures"),
                    },
                ),
                expected_server_name=SERVER_NAME,
                required_tools=GAME_TOOL_ALLOWLIST,
                exact_tools=True,
            )
            qa = StdioMcpClient(
                StdioServerParameters(
                    command=sys.executable,
                    args=["-m", "qa_agent.mcp_server.stdio_server"],
                    cwd=qa_root,
                    env=env,
                ),
                expected_server_name="sanguo-kb",
                required_tools=QA_READ_ONLY_TOOLS,
            )
            async with game, qa:
                fixture = await game.call_tool(
                    "evaluate_fixture",
                    {"fixture": "chapter_claimable_state.json"},
                )
                answer = await qa.call_tool(
                    "answer_rule_question",
                    {"question": "体力不足时怎么办？", "domain": "team"},
                )
                self.assertFalse(fixture["isError"])
                self.assertEqual(
                    fixture["structuredContent"]["execution_authority"],
                    "none",
                )
                self.assertFalse(
                    fixture["structuredContent"]["evaluation"]["selected_action"][
                        "executable"
                    ]
                )
                self.assertFalse(answer["isError"])
                self.assertTrue(answer["structuredContent"]["evidence"])

        asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
