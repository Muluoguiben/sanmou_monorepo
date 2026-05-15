"""Advisor-only observation entry point.

Examples:
  PYTHONPATH=src python -m pioneer_agent.app.advisor_observe --screenshot sample.png
  PYTHONPATH=src python -m pioneer_agent.app.advisor_observe --watch-folder ./screenshots
  PYTHONPATH=src python -m pioneer_agent.app.advisor_observe --windows-bridge
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pioneer_agent.adapters.capture import (
    ScreenshotFileCaptureAdapter,
    WatchFolderCaptureAdapter,
    WindowsBridgeCaptureAdapter,
)
from pioneer_agent.core.device import AccountSession, DevicePlatform
from pioneer_agent.perception.vision import build_vision_client
from pioneer_agent.perception.vision_sync import VisionSync
from pioneer_agent.runtime.advisor_loop import AdvisorLoop


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one Advisor-only observation tick.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--screenshot", type=Path, help="Analyze one screenshot file.")
    source.add_argument("--watch-folder", type=Path, help="Analyze the newest screenshot in a folder.")
    source.add_argument("--windows-bridge", action="store_true", help="Capture the PC client through the Windows bridge.")
    parser.add_argument(
        "--platform",
        choices=[item.value for item in DevicePlatform],
        default=DevicePlatform.UNKNOWN.value,
        help="Platform hint for screenshot/watch-folder sources.",
    )
    parser.add_argument("--account-label", default=None)
    parser.add_argument("--server-id", default=None)
    parser.add_argument("--season-id", default=None)
    parser.add_argument("--role-name", default=None)
    parser.add_argument("--vision-provider", choices=("gemini", "openai"), default=None)
    args = parser.parse_args(argv)

    platform = DevicePlatform(args.platform)
    if args.screenshot is not None:
        capture = ScreenshotFileCaptureAdapter(args.screenshot, platform=platform)
    elif args.watch_folder is not None:
        capture = WatchFolderCaptureAdapter(args.watch_folder, platform=platform)
    else:
        capture = WindowsBridgeCaptureAdapter()

    account = AccountSession(
        account_label=args.account_label,
        server_id=args.server_id,
        season_id=args.season_id,
        role_name=args.role_name,
    )
    vision = build_vision_client(args.vision_provider)
    loop = AdvisorLoop(capture, VisionSync(vision), account_session=account)
    report = loop.tick()
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
