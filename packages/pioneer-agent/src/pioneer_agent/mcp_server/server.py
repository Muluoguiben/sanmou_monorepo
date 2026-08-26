from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from pioneer_agent.core.device import DeviceSession
from pioneer_agent.storage.trace_store import TraceStore

from .contracts import (
    ActionCandidatesResponse,
    AdvisorReportResponse,
    FixtureEvaluationResponse,
    GAME_TOOL_ARGUMENTS,
    LastTraceResponse,
    ObserveGameResponse,
    RuntimeStateResponse,
    SERVER_NAME,
    SessionStatusResponse,
)
from .service import GameMCPService, ObservationProvider


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


class StrictFastMCP(FastMCP):
    """FastMCP v1 adapter using only public SDK extension methods."""

    async def list_tools(self):  # noqa: ANN201 - SDK return type varies within v1
        tools = await super().list_tools()
        strict_tools = []
        for tool in tools:
            schema = dict(tool.inputSchema)
            schema["additionalProperties"] = False
            strict_tools.append(tool.model_copy(update={"inputSchema": schema}))
        return strict_tools

    async def call_tool(self, name: str, arguments: dict[str, Any]):  # noqa: ANN201
        allowed = GAME_TOOL_ARGUMENTS.get(name)
        if allowed is not None:
            extra = sorted(set(arguments).difference(allowed))
            if extra:
                raise ToolError("Extra inputs are not permitted: " + ", ".join(extra))
        return await super().call_tool(name, arguments)


def create_server(service: GameMCPService | None = None) -> FastMCP:
    game_service = service or build_default_service()
    server = StrictFastMCP(
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
        include_details: Annotated[
            bool,
            Field(
                strict=True,
                description="Return ranked actions and selection diagnostics; false returns a bounded summary",
            ),
        ] = True,
    ) -> FixtureEvaluationResponse:
        """Evaluate one closed-root offline fixture; never reads a live source."""

        return game_service.evaluate_fixture(
            fixture,
            include_details=include_details,
        )

    return server


def build_default_service() -> GameMCPService:
    """Build the M0 contract skeleton; live observation remains unconfigured."""

    fixture_root = _configured_fixture_root()
    trace_store = _configured_trace_store()
    return GameMCPService(fixture_root=fixture_root, trace_store=trace_store)


def build_live_service(
    *,
    observation_provider: ObservationProvider,
    device_session: DeviceSession | None = None,
    trace_store: TraceStore | None = None,
    fixture_root: Path | None = None,
) -> GameMCPService:
    """Explicit live composition seam for a separately built observe/advisor provider."""

    return GameMCPService(
        observation_provider=observation_provider,
        device_session=device_session,
        trace_store=trace_store,
        fixture_root=fixture_root,
    )


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


mcp = create_server()


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
