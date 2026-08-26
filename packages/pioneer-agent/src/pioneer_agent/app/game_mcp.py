"""Explicit production composition for the read-only ``sanmou-game`` MCP.

The default ``python -m pioneer_agent.mcp_server`` entry point remains a
contract skeleton. This module requires an observation source and never
constructs an executor or control adapter.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from pioneer_agent.adapters.capture import (
    CaptureAdapter,
    ScreenshotFileCaptureAdapter,
    WatchFolderCaptureAdapter,
    WindowsBridgeCaptureAdapter,
)
from pioneer_agent.core.device import AccountSession, DevicePlatform
from pioneer_agent.mcp_server.live_provider import AdvisorLoopObservationProvider
from pioneer_agent.mcp_server.server import build_live_service, create_server
from pioneer_agent.perception.vision import build_vision_client
from pioneer_agent.perception.vision_sync import VisionSync
from pioneer_agent.runtime.advisor_loop import AdvisorLoop
from pioneer_agent.storage.trace_store import TraceStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the explicit read-only sanmou-game live MCP over stdio."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--screenshot", type=Path)
    source.add_argument("--watch-folder", type=Path)
    source.add_argument("--windows-bridge", action="store_true")
    parser.add_argument(
        "--platform",
        choices=[item.value for item in DevicePlatform],
        default=DevicePlatform.UNKNOWN.value,
        help="Platform hint for screenshot/watch-folder sources.",
    )
    parser.add_argument("--vision-provider", default=None)
    parser.add_argument("--fixture-root", type=Path, default=None)
    parser.add_argument("--trace-path", type=Path, default=None)
    parser.add_argument("--account-label", default=None)
    parser.add_argument("--server-id", default=None)
    parser.add_argument("--season-id", default=None)
    parser.add_argument("--role-name", default=None)
    return parser


def build_live_server(
    args: argparse.Namespace,
    *,
    capture: CaptureAdapter | None = None,
    vision_sync: Any | None = None,
):  # noqa: ANN201 - FastMCP's concrete generic type varies by SDK minor
    capture_adapter = capture or _capture_from_args(args)
    sync = vision_sync or VisionSync(build_vision_client(args.vision_provider))
    account = AccountSession(
        account_label=args.account_label,
        server_id=args.server_id,
        season_id=args.season_id,
        role_name=args.role_name,
    )
    loop = AdvisorLoop(capture_adapter, sync, account_session=account)
    provider = AdvisorLoopObservationProvider(loop)
    service = build_live_service(
        observation_provider=provider,
        device_session=capture_adapter.device_session,
        trace_store=_read_only_trace_store(args.trace_path),
        fixture_root=_fixture_root(args.fixture_root),
    )
    return create_server(service)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_live_server(args).run(transport="stdio")
    return 0


def _capture_from_args(args: argparse.Namespace) -> CaptureAdapter:
    platform = DevicePlatform(args.platform)
    if args.screenshot is not None:
        return ScreenshotFileCaptureAdapter(args.screenshot, platform=platform)
    if args.watch_folder is not None:
        return WatchFolderCaptureAdapter(args.watch_folder, platform=platform)
    if args.windows_bridge:
        return WindowsBridgeCaptureAdapter()
    raise ValueError("an explicit observation source is required")


def _fixture_root(explicit: Path | None) -> Path | None:
    configured = explicit or _environment_path("SANMOU_GAME_FIXTURE_ROOT")
    if configured is not None:
        return configured
    development_root = Path(__file__).resolve().parents[3] / "tests" / "fixtures"
    return development_root if development_root.is_dir() else None


def _read_only_trace_store(explicit: Path | None) -> TraceStore | None:
    configured = explicit or _environment_path("SANMOU_GAME_TRACE_PATH")
    if configured is None:
        return None
    resolved = configured.resolve()
    if not resolved.is_file():
        return None
    return TraceStore(resolved)


def _environment_path(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value) if value else None


if __name__ == "__main__":
    raise SystemExit(main())
