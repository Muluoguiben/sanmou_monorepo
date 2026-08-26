"""Frozen read-only MCP names consumed by the recommendation harness."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


SESSION_STATUS = "session_status"
OBSERVE_GAME = "observe_game"
GET_RUNTIME_STATE = "get_runtime_state"
GET_ADVISOR_REPORT = "get_advisor_report"
LIST_ACTION_CANDIDATES = "list_action_candidates"
GET_LAST_TRACE = "get_last_trace"
EVALUATE_FIXTURE = "evaluate_fixture"

GAME_READ_ONLY_TOOLS = frozenset(
    {
        SESSION_STATUS,
        OBSERVE_GAME,
        GET_RUNTIME_STATE,
        GET_ADVISOR_REPORT,
        LIST_ACTION_CANDIDATES,
        GET_LAST_TRACE,
        EVALUATE_FIXTURE,
    }
)

LOOKUP_TOPIC = "lookup_topic"
ANSWER_RULE_QUESTION = "answer_rule_question"
RESOLVE_TERM = "resolve_term"
QA_READ_ONLY_TOOLS = frozenset({LOOKUP_TOPIC, ANSWER_RULE_QUESTION, RESOLVE_TERM})


class McpClient(Protocol):
    """Transport-neutral MCP client boundary.

    A future SDK adapter only needs to implement this method. The harness does
    not import MCP server handlers or any control/executor component.
    """

    async def call_tool(
        self,
        name: str,
        arguments: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...


class McpToolError(RuntimeError):
    pass


def structured_content(result: Mapping[str, Any]) -> dict[str, Any]:
    """Unwrap an MCP tool result without depending on one SDK implementation."""

    if result.get("isError") is True:
        raise McpToolError("MCP tool returned isError=true")
    payload = result.get("structuredContent", result)
    if not isinstance(payload, Mapping):
        raise McpToolError("MCP tool result has no structured object payload")
    return dict(payload)
