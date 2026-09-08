"""Run one recommendation-only decision window over real MCP stdio servers."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import time
from datetime import UTC, datetime
from pathlib import Path
import sys
from uuid import uuid4

from mcp import StdioServerParameters

from pioneer_agent.agent_harness import (
    JsonJournalStore,
    JsonlToolLog,
    RecommendationHarness,
    StdioMcpClient,
)
from pioneer_agent.agent_harness.contracts import QA_READ_ONLY_TOOLS
from pioneer_agent.agent_harness.policy import StopReason
from pioneer_agent.agent_harness.tool_log import ToolCallRecord
from pioneer_agent.core.device import DevicePlatform
from pioneer_agent.mcp_server.contracts import GAME_TOOL_ALLOWLIST, SERVER_NAME


QA_SERVER_NAME = "sanguo-kb"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one recommendation-only Sanmou decision window."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--screenshot", type=Path)
    source.add_argument("--watch-folder", type=Path)
    source.add_argument("--windows-bridge", action="store_true")
    parser.add_argument(
        "--platform",
        choices=[item.value for item in DevicePlatform],
        default=DevicePlatform.UNKNOWN.value,
    )
    parser.add_argument("--vision-provider", default=None)
    parser.add_argument("--fixture-root", type=Path, default=None)
    parser.add_argument("--trace-path", type=Path, default=None)
    parser.add_argument("--qa-sources-dir", default="knowledge_sources")
    parser.add_argument("--qa-question", action="append", default=[])
    parser.add_argument("--journal-path", type=Path, required=True)
    parser.add_argument("--tool-log-path", type=Path, required=True)
    parser.add_argument("--agent-session-id", default=None)
    parser.add_argument("--model-id", default="recommendation-harness-v1")
    parser.add_argument("--mcp-connect-timeout", type=_positive_timeout, default=30.0)
    parser.add_argument("--mcp-request-timeout", type=_positive_timeout, default=60.0)
    return parser


def _positive_timeout(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("timeout must be finite and positive")
    return number


async def run(args: argparse.Namespace) -> dict:
    agent_session_id = args.agent_session_id or f"agent-{uuid4().hex}"
    game_parameters = _game_parameters(args)
    qa_parameters = _qa_parameters(args)
    game_client = StdioMcpClient(
        game_parameters,
        expected_server_name=SERVER_NAME,
        required_tools=GAME_TOOL_ALLOWLIST,
        exact_tools=True,
        connect_timeout_s=args.mcp_connect_timeout,
        request_timeout_s=args.mcp_request_timeout,
    )
    qa_client = StdioMcpClient(
        qa_parameters,
        expected_server_name=QA_SERVER_NAME,
        required_tools=QA_READ_ONLY_TOOLS,
        connect_timeout_s=args.mcp_connect_timeout,
        request_timeout_s=args.mcp_request_timeout,
    )
    harness = RecommendationHarness(
        game_client=game_client,
        qa_client=qa_client,
        journal_store=JsonJournalStore(args.journal_path),
        tool_log=JsonlToolLog(args.tool_log_path),
        agent_session_id=agent_session_id,
        model_id=args.model_id,
    )
    phase = "mcp_connect:game"
    started_at, started = datetime.now(UTC), time.monotonic()
    try:
        async with game_client:
            phase = "mcp_connect:qa"
            started_at, started = datetime.now(UTC), time.monotonic()
            async with qa_client:
                phase = "mcp_lifecycle"
                result = await harness.run_decision_window(qa_questions=args.qa_question)
    except (Exception, asyncio.CancelledError) as exc:
        harness.tool_log.append(ToolCallRecord(
            started_at=started_at, tool_name=phase, arguments_summary={},
            duration_ms=max(0.0, (time.monotonic() - started) * 1000),
            success=False, error_type=type(exc).__name__,
            model_id=args.model_id, agent_session_id=agent_session_id,
        ))
        result = harness._stop(
            harness.journal_store.load(agent_session_id), StopReason.TOOL_FAILURE,
            [phase, type(exc).__name__],
        )
        if isinstance(exc, asyncio.CancelledError):
            raise
    return result.model_dump(mode="json")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = asyncio.run(run(args))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _game_parameters(args: argparse.Namespace) -> StdioServerParameters:
    arguments = ["-m", "pioneer_agent.app.game_mcp"]
    if args.screenshot is not None:
        arguments.extend(["--screenshot", str(args.screenshot.resolve())])
    elif args.watch_folder is not None:
        arguments.extend(["--watch-folder", str(args.watch_folder.resolve())])
    else:
        arguments.append("--windows-bridge")
    arguments.extend(["--platform", args.platform])
    if args.vision_provider:
        arguments.extend(["--vision-provider", args.vision_provider])
    if args.fixture_root is not None:
        arguments.extend(["--fixture-root", str(args.fixture_root.resolve())])
    if args.trace_path is not None:
        arguments.extend(["--trace-path", str(args.trace_path.resolve())])
    return StdioServerParameters(
        command=sys.executable,
        args=arguments,
        cwd=_pioneer_root(),
        env=_child_env(
            include_vision_credentials=True,
            include_capture_credentials=args.windows_bridge,
        ),
    )


def _qa_parameters(args: argparse.Namespace) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "qa_agent.mcp_server.stdio_server",
            "--sources-dir",
            args.qa_sources_dir,
        ],
        cwd=_qa_root(),
        env=_child_env(include_vision_credentials=False),
    )


def _child_env(
    *, include_vision_credentials: bool, include_capture_credentials: bool = False,
) -> dict[str, str]:
    source = dict(os.environ)
    secret_parts = (
        "KEY",
        "TOKEN",
        "SECRET",
        "PASSWORD",
        "COOKIE",
        "AUTH",
        "CREDENTIAL",
        "ASKPASS",
    )
    env = {
        key: value
        for key, value in source.items()
        if not any(part in key.upper() for part in secret_parts)
    }
    if include_vision_credentials:
        for key in ("OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
            if key in source:
                env[key] = source[key]
    if include_capture_credentials and "SANMOU_CAPTURE_TOKEN" in source:
        env["SANMOU_CAPTURE_TOKEN"] = source["SANMOU_CAPTURE_TOKEN"]
    python_paths = [
        _pioneer_root() / "src",
        _repo_root() / "packages" / "sanmou-common" / "src",
        _qa_root() / "src",
    ]
    existing = source.get("PYTHONPATH")
    if existing:
        python_paths.append(Path(existing))
    env["PYTHONPATH"] = os.pathsep.join(str(path) for path in python_paths)
    return env


def _pioneer_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _qa_root() -> Path:
    return _repo_root() / "packages" / "qa-agent"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


if __name__ == "__main__":
    raise SystemExit(main())
