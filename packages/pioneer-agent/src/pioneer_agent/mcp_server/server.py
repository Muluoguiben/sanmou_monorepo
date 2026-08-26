from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from pioneer_agent.storage.trace_store import TraceStore

from .contracts import (
    ActionCandidatesResponse,
    AdvisorReportResponse,
    FixtureEvaluationResponse,
    LastTraceResponse,
    ObserveGameResponse,
    RuntimeStateResponse,
    SessionStatusResponse,
)
from .service import GameMCPService


SERVER_NAME = "sanmou-game"
READ_ONLY_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
READ_ONLY_REFRESH_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
)


def create_server(service: GameMCPService | None = None) -> FastMCP:
    game_service = service or build_default_service()
    server = FastMCP(
        SERVER_NAME,
        instructions=(
            "Read-only Sanmou game observation and Advisor contract. "
            "This server has no game-input or execution authority."
        ),
        json_response=True,
    )

    @server.tool(annotations=READ_ONLY_ANNOTATIONS)
    def session_status() -> SessionStatusResponse:
        """Read session, capture health, and latest cache metadata without observing."""

        return game_service.session_status()

    @server.tool(annotations=READ_ONLY_REFRESH_ANNOTATIONS)
    def observe_game() -> ObserveGameResponse:
        """Capture and perceive one fresh game observation without sending input."""

        return game_service.observe_game()

    @server.tool(annotations=READ_ONLY_ANNOTATIONS)
    def get_runtime_state() -> RuntimeStateResponse:
        """Read the cached RuntimeState; never refresh or invoke vision implicitly."""

        return game_service.get_runtime_state()

    @server.tool(annotations=READ_ONLY_ANNOTATIONS)
    def get_advisor_report() -> AdvisorReportResponse:
        """Read the cached AdvisorReport; return not_observed when cache is empty."""

        return game_service.get_advisor_report()

    @server.tool(annotations=READ_ONLY_ANNOTATIONS)
    def list_action_candidates() -> ActionCandidatesResponse:
        """List cached ranked proposals; every proposal is explicitly non-executable."""

        return game_service.list_action_candidates()

    @server.tool(annotations=READ_ONLY_ANNOTATIONS)
    def get_last_trace() -> LastTraceResponse:
        """Read one bounded trace summary with SHA references and no image bytes."""

        return game_service.get_last_trace()

    @server.tool(annotations=READ_ONLY_ANNOTATIONS)
    def evaluate_fixture(
        fixture: Annotated[
            str,
            Field(
                min_length=1,
                max_length=240,
                description="JSON path relative to the configured offline fixture root",
            ),
        ],
    ) -> FixtureEvaluationResponse:
        """Evaluate one closed-root offline fixture; never reads a live source."""

        return game_service.evaluate_fixture(fixture)

    _enforce_strict_tool_inputs(server)
    return server


def build_default_service() -> GameMCPService:
    fixture_root = _configured_fixture_root()
    trace_store = _configured_trace_store()
    return GameMCPService(fixture_root=fixture_root, trace_store=trace_store)


def _configured_fixture_root() -> Path | None:
    configured = os.environ.get("SANMOU_GAME_FIXTURE_ROOT")
    if configured:
        return Path(configured)
    project_root = Path(__file__).resolve().parents[3]
    development_root = project_root / "tests" / "fixtures"
    return development_root if development_root.is_dir() else None


def _configured_trace_store() -> TraceStore | None:
    configured = os.environ.get("SANMOU_GAME_TRACE_PATH")
    if not configured:
        return None
    path = Path(configured).resolve()
    # TraceStore creates parent directories in its constructor. The read-only
    # server therefore refuses absent paths instead of creating runtime state.
    if not path.is_file():
        return None
    return TraceStore(path)


def _enforce_strict_tool_inputs(server: FastMCP) -> None:
    """Make FastMCP v1 reject undeclared arguments on every tool.

    FastMCP v1.28/1.29 derives an argument model with ``extra=ignore`` even
    when every public contract model is strict. The server owns this one
    compatibility shim until migration to the v2 SDK is a separate decision.
    """

    for tool in server._tool_manager._tools.values():  # noqa: SLF001 - SDK v1 compatibility boundary
        tool.parameters["additionalProperties"] = False
        tool.fn_metadata.arg_model.model_config["extra"] = "forbid"
        tool.fn_metadata.arg_model.model_rebuild(force=True)


mcp = create_server()


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
