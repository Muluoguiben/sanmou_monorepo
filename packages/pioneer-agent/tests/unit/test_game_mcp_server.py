from __future__ import annotations

import ast
import asyncio
import json
import os
import sys
import tomllib
import unittest
from importlib.metadata import version
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.server.fastmcp.exceptions import ToolError

from pioneer_agent.mcp_server.server import (
    build_default_service,
    build_live_service,
    create_server,
)
from pioneer_agent.mcp_server.contracts import GAME_TOOL_ARGUMENTS
from pioneer_agent.mcp_server.service import GameMCPService


TOOL_NAMES = set(GAME_TOOL_ARGUMENTS)


class GameMCPServerTests(unittest.TestCase):
    def test_tool_list_annotations_and_strict_schemas(self) -> None:
        async def inspect_tools():
            return await create_server(GameMCPService()).list_tools()

        tools = asyncio.run(inspect_tools())
        self.assertEqual({tool.name for tool in tools}, TOOL_NAMES)
        for tool in tools:
            with self.subTest(tool=tool.name):
                self.assertTrue(tool.annotations.readOnlyHint)
                self.assertFalse(tool.annotations.destructiveHint)
                self.assertFalse(tool.annotations.openWorldHint)
                self.assertEqual(tool.inputSchema["additionalProperties"], False)
                self.assertIn("outputSchema", tool.model_dump(by_alias=True, exclude_none=True))
        observe = next(tool for tool in tools if tool.name == "observe_game")
        self.assertFalse(observe.annotations.idempotentHint)
        for tool in tools:
            if tool.name != "observe_game":
                self.assertTrue(tool.annotations.idempotentHint)

    def test_mcp_handler_output_matches_service_output(self) -> None:
        service = GameMCPService()
        server = create_server(service)

        async def call():
            return await server.call_tool("session_status", {})

        _, structured = asyncio.run(call())
        self.assertEqual(
            structured,
            service.session_status().model_dump(mode="json"),
        )

    def test_unknown_input_is_rejected_before_handler(self) -> None:
        server = create_server(GameMCPService())

        async def call():
            return await server.call_tool("session_status", {"refresh": True})

        with self.assertRaisesRegex(ToolError, "Extra inputs are not permitted"):
            asyncio.run(call())

    def test_mcp_server_has_no_direct_control_import_or_mutating_tool(self) -> None:
        package_root = Path(__file__).resolve().parents[2] / "src" / "pioneer_agent" / "mcp_server"
        forbidden_imports = (
            "pioneer_agent.executor",
            "pioneer_agent.adapters.control",
            "pioneer_agent.adapters.bridge_client",
            "pioneer_agent.adapters.win_bridge_server",
            "pioneer_agent.runtime.replay_runtime",
            "pioneer_agent.verifier",
        )
        imported: set[str] = set()
        for path in package_root.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
        self.assertFalse(
            {
                name
                for name in imported
                if any(name == forbidden or name.startswith(f"{forbidden}.") for forbidden in forbidden_imports)
            }
        )
        self.assertFalse(
            TOOL_NAMES.intersection(
                {"click", "press_key", "prepare_action", "execute_prepared_action"}
            )
        )
        server_source = (package_root / "server.py").read_text(encoding="utf-8")
        self.assertNotIn("._tool_manager", server_source)
        self.assertNotIn(".fn_metadata", server_source)

    def test_mcp_sdk_compatibility_window_is_the_verified_v1_minor(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        pyproject = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))
        dependencies = pyproject["project"]["dependencies"]

        self.assertIn("mcp>=1.29,<1.30", dependencies)
        major, minor, _patch = (int(part) for part in version("mcp").split(".")[:3])
        self.assertEqual((major, minor), (1, 29))

    def test_default_is_contract_skeleton_and_live_factory_requires_provider(self) -> None:
        self.assertEqual(build_default_service().observe_game().status, "not_configured")

        class _FailingProvider:
            calls = 0

            def observe(self):
                self.calls += 1
                raise RuntimeError("private provider detail")

        provider = _FailingProvider()
        response = build_live_service(observation_provider=provider).observe_game()

        self.assertEqual(provider.calls, 1)
        self.assertEqual(response.status, "error")
        self.assertNotIn("private provider detail", response.error.message)  # type: ignore[union-attr]

    def test_generic_client_smoke_config_matches_module_entrypoint(self) -> None:
        package_root = Path(__file__).resolve().parents[2] / "src" / "pioneer_agent" / "mcp_server"
        config = json.loads(
            (package_root / "client-smoke.example.json").read_text(encoding="utf-8")
        )["mcpServers"]["sanmou-game"]
        self.assertEqual(config["command"], "wsl.exe")
        self.assertIn("Ubuntu", config["args"])
        self.assertIn("/home/lan/projects/sanmou_monorepo", config["args"])
        self.assertIn(
            "SANMOU_GAME_FIXTURE_ROOT=packages/pioneer-agent/tests/fixtures",
            config["args"],
        )
        self.assertEqual(
            config["args"][-3:],
            ["python3", "-m", "pioneer_agent.mcp_server"],
        )

    def test_stdio_initialize_list_and_call_smoke(self) -> None:
        project_root = Path(__file__).resolve().parents[4]
        pioneer_root = project_root / "packages" / "pioneer-agent"
        common_src = project_root / "packages" / "sanmou-common" / "src"
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            [
                str(pioneer_root / "src"),
                str(common_src),
                env.get("PYTHONPATH", ""),
            ]
        )
        env["SANMOU_GAME_FIXTURE_ROOT"] = str(pioneer_root / "tests" / "fixtures")

        async def smoke() -> None:
            params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "pioneer_agent.mcp_server"],
                env=env,
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    initialized = await session.initialize()
                    self.assertEqual(initialized.serverInfo.name, "sanmou-game")
                    listed = await session.list_tools()
                    self.assertEqual({tool.name for tool in listed.tools}, TOOL_NAMES)
                    status = await session.call_tool("session_status", {})
                    self.assertFalse(status.isError)
                    self.assertEqual(status.structuredContent["execution_authority"], "none")
                    fixture = await session.call_tool(
                        "evaluate_fixture",
                        {"fixture": "chapter_claimable_state.json"},
                    )
                    self.assertFalse(fixture.isError)
                    self.assertFalse(fixture.structuredContent["live_source_used"])
                    self.assertFalse(
                        fixture.structuredContent["evaluation"]["selected_action"]["executable"]
                    )

        asyncio.run(smoke())


if __name__ == "__main__":
    unittest.main()
