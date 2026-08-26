from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import CallToolResult, ContentBlock, TextContent, Tool, ToolAnnotations

from qa_agent.mcp_server.tooling import (
    READ_ONLY_ANNOTATIONS,
    TOOL_DESCRIPTIONS,
    TOOL_INPUT_MODELS,
    KnowledgeToolHandler,
    validate_tool_arguments,
)


SERVER_NAME = "sanguo-kb"
SERVER_VERSION = "0.1.0"

READ_ONLY_TOOL_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=READ_ONLY_ANNOTATIONS["readOnlyHint"],
    destructiveHint=READ_ONLY_ANNOTATIONS["destructiveHint"],
    idempotentHint=READ_ONLY_ANNOTATIONS["idempotentHint"],
    openWorldHint=READ_ONLY_ANNOTATIONS["openWorldHint"],
)


class StrictSchemaFastMCP(FastMCP):
    """FastMCP v1 with fail-closed top-level schemas and raw input validation."""

    def __init__(self, *args: Any, version: str, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # FastMCP v1 does not expose a version constructor argument, while its
        # low-level official Server does. Preserve the existing connector identity.
        self._mcp_server.version = version  # noqa: SLF001 - SDK v1 compatibility boundary

    async def list_tools(self) -> list[Tool]:
        tools = await super().list_tools()
        return [
            tool.model_copy(
                update={"inputSchema": TOOL_INPUT_MODELS[tool.name].model_json_schema()}
            )
            for tool in tools
        ]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> Sequence[ContentBlock] | dict[str, Any]:
        try:
            validated = validate_tool_arguments(name, arguments)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        return await super().call_tool(name, validated)


def _sdk_result(result: dict[str, Any]) -> CallToolResult:
    content = [
        TextContent(type="text", text=item["text"])
        for item in result["content"]
        if item.get("type") == "text"
    ]
    return CallToolResult(
        content=content,
        structuredContent=result.get("structuredContent"),
        isError=bool(result.get("isError", False)),
    )


def create_mcp_server(handler: KnowledgeToolHandler) -> StrictSchemaFastMCP:
    server = StrictSchemaFastMCP(
        SERVER_NAME,
        version=SERVER_VERSION,
        instructions="Read-only Sanmou reviewed knowledge and offline Advisor evidence tools.",
        json_response=True,
    )

    @server.tool(
        description=TOOL_DESCRIPTIONS["lookup_topic"],
        annotations=READ_ONLY_TOOL_ANNOTATIONS,
        structured_output=False,
    )
    def lookup_topic(topic: str, domain: str | None = None) -> CallToolResult:
        return _sdk_result(handler.call_tool("lookup_topic", {"topic": topic, "domain": domain}))

    @server.tool(
        description=TOOL_DESCRIPTIONS["answer_rule_question"],
        annotations=READ_ONLY_TOOL_ANNOTATIONS,
        structured_output=False,
    )
    def answer_rule_question(question: str, domain: str | None = None) -> CallToolResult:
        return _sdk_result(
            handler.call_tool("answer_rule_question", {"question": question, "domain": domain})
        )

    @server.tool(
        description=TOOL_DESCRIPTIONS["resolve_term"],
        annotations=READ_ONLY_TOOL_ANNOTATIONS,
        structured_output=False,
    )
    def resolve_term(term: str, domain: str | None = None) -> CallToolResult:
        return _sdk_result(handler.call_tool("resolve_term", {"term": term, "domain": domain}))

    @server.tool(
        description=TOOL_DESCRIPTIONS["advisor_golden_replay_status"],
        annotations=READ_ONLY_TOOL_ANNOTATIONS,
        structured_output=False,
    )
    def advisor_golden_replay_status(include_fixture_results: bool = True) -> CallToolResult:
        return _sdk_result(
            handler.call_tool(
                "advisor_golden_replay_status",
                {"include_fixture_results": include_fixture_results},
            )
        )

    @server.tool(
        description=TOOL_DESCRIPTIONS["advisor_fixture_eval"],
        annotations=READ_ONLY_TOOL_ANNOTATIONS,
        structured_output=False,
    )
    def advisor_fixture_eval(
        fixture: str,
        expected_action_type: str | None = None,
        include_details: bool = True,
    ) -> CallToolResult:
        return _sdk_result(
            handler.call_tool(
                "advisor_fixture_eval",
                {
                    "fixture": fixture,
                    "expected_action_type": expected_action_type,
                    "include_details": include_details,
                },
            )
        )

    @server.tool(
        description=TOOL_DESCRIPTIONS["advisor_terminal_source_evidence_eval"],
        annotations=READ_ONLY_TOOL_ANNOTATIONS,
        structured_output=False,
    )
    def advisor_terminal_source_evidence_eval(
        action_type: str,
        terminal_source_evidence: dict[str, Any],
        fixture: str | None = None,
        page: str | None = None,
    ) -> CallToolResult:
        return _sdk_result(
            handler.call_tool(
                "advisor_terminal_source_evidence_eval",
                {
                    "action_type": action_type,
                    "terminal_source_evidence": terminal_source_evidence,
                    "fixture": fixture,
                    "page": page,
                },
            )
        )

    return server
