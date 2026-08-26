from __future__ import annotations

from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult, InputRequiredResult, TextContent, ToolAnnotations

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
    read_only_hint=READ_ONLY_ANNOTATIONS["readOnlyHint"],
    open_world_hint=READ_ONLY_ANNOTATIONS["openWorldHint"],
)


class StrictSchemaMCPServer(MCPServer):
    """MCPServer with fail-closed top-level schemas for every registered tool."""

    async def list_tools(self):
        tools = await super().list_tools()
        return [
            tool.model_copy(
                update={"input_schema": TOOL_INPUT_MODELS[tool.name].model_json_schema()}
            )
            for tool in tools
        ]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        context: Context | None = None,
    ) -> CallToolResult | InputRequiredResult:
        try:
            validated = validate_tool_arguments(name, arguments)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        return await super().call_tool(name, validated, context)


def _sdk_result(result: dict[str, Any]) -> CallToolResult:
    content = [
        TextContent(type="text", text=item["text"])
        for item in result["content"]
        if item.get("type") == "text"
    ]
    return CallToolResult(
        content=content,
        structured_content=result.get("structuredContent"),
        is_error=bool(result.get("isError", False)),
    )


def create_mcp_server(handler: KnowledgeToolHandler) -> StrictSchemaMCPServer:
    server = StrictSchemaMCPServer(
        SERVER_NAME,
        version=SERVER_VERSION,
        description="Read-only Sanmou reviewed knowledge and offline Advisor evidence tools.",
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
    ) -> CallToolResult:
        return _sdk_result(
            handler.call_tool(
                "advisor_fixture_eval",
                {"fixture": fixture, "expected_action_type": expected_action_type},
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
