"""Thin client adapters for canonical MCP contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from pioneer_agent.mcp_server.contracts import (
    ContractResponse,
    GAME_TOOL_ARGUMENTS,
    GAME_TOOL_RESPONSE_MODELS,
)


LOOKUP_TOPIC = "lookup_topic"
ANSWER_RULE_QUESTION = "answer_rule_question"
RESOLVE_TERM = "resolve_term"
QA_READ_ONLY_TOOLS = frozenset({LOOKUP_TOPIC, ANSWER_RULE_QUESTION, RESOLVE_TERM})


class McpClient(Protocol):
    """Transport-neutral MCP client boundary."""

    async def call_tool(
        self,
        name: str,
        arguments: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...


class InProcessMcpClient:
    """Adapt FastMCP's in-process call result to the transport-neutral shape."""

    def __init__(self, server: Any) -> None:
        self.server = server
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(
        self,
        name: str,
        arguments: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        self.calls.append((name, dict(arguments)))
        result = await self.server.call_tool(name, dict(arguments))
        if not isinstance(result, tuple) or len(result) != 2:
            raise McpToolError("unexpected in-process MCP result")
        _, structured = result
        if not isinstance(structured, Mapping):
            raise McpToolError("in-process MCP result has no structured object payload")
        return {"isError": False, "structuredContent": dict(structured)}


class McpToolError(RuntimeError):
    pass


def structured_content(result: Mapping[str, Any]) -> dict[str, Any]:
    """Unwrap an MCP tool result without depending on one SDK transport."""

    if result.get("isError") is True:
        raise McpToolError("MCP tool returned isError=true")
    payload = result.get("structuredContent", result)
    if not isinstance(payload, Mapping):
        raise McpToolError("MCP tool result has no structured object payload")
    return dict(payload)


def validate_game_response(name: str, payload: Mapping[str, Any]) -> ContractResponse:
    """Validate with the canonical sanmou-game/v1 response model."""

    response_model = GAME_TOOL_RESPONSE_MODELS.get(name)
    if response_model is None or name not in GAME_TOOL_ARGUMENTS:
        raise McpToolError(f"game tool is outside canonical read-only contract: {name}")
    return response_model.model_validate(payload)
