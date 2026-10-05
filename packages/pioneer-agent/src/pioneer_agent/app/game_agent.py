"""Run one recommendation-only decision window over real MCP stdio servers."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import time
from contextlib import asynccontextmanager
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
    parser.add_argument("--task-spec", type=Path, help="Version 1 read-only TaskSpec JSON")
    parser.add_argument("--run-state-path", type=Path)
    parser.add_argument("--run-trace-path", type=Path)
    parser.add_argument("--resume-task", action="store_true")
    parser.add_argument("--task-timeout", type=_positive_timeout, default=300.0)
    parser.add_argument("--task-tool-limit", type=int, default=100)
    return parser


def _positive_timeout(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("timeout must be finite and positive")
    return number


async def run(args: argparse.Namespace) -> dict:
    if args.task_spec is not None:
        return await _run_task(args)
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


async def _run_task(args: argparse.Namespace, *, game_client=None) -> dict:
    from pioneer_agent.agent_harness.run_store import CheckpointConflict, JsonRunStore

    if args.run_state_path is None or args.run_trace_path is None:
        raise ValueError("task mode requires --run-state-path and --run-trace-path")
    if args.qa_question:
        raise ValueError("task v1 is Game-only; QA remains in single-window mode")
    store = JsonRunStore(args.run_state_path)
    try:
        # Includes initial checkpoint read, budget restore and MCP cleanup.
        with store.acquire() as ownership:
            return await _run_owned_task(args, store=store, ownership=ownership, game_client=game_client)
    except CheckpointConflict:
        return {"status": "blocked", "reason": "checkpoint_conflict",
                "execution_authority": "none", "executable": False}


async def _run_owned_task(args, *, store, ownership, game_client=None):
    """Opt-in task mode; default CLI remains a single recommendation window."""
    from pioneer_agent.agent_harness.context_builder import BoundedContextBuilder
    from pioneer_agent.agent_harness.run_budget import BudgetLimits, RunBudgetLedger
    from pioneer_agent.agent_harness.run_store import CheckpointConflict
    from pioneer_agent.agent_harness.run_trace import JsonlRunTrace
    from pioneer_agent.agent_harness.task_contracts import TaskSpec, TERMINAL_STATUSES
    from pioneer_agent.agent_harness.task_policy import RuleDecisionPolicy
    from pioneer_agent.agent_harness.task_runner import TaskRunner

    if args.run_state_path is None or args.run_trace_path is None:
        raise ValueError("task mode requires --run-state-path and --run-trace-path")
    if args.qa_question:
        raise ValueError("task v1 is Game-only; QA remains in single-window mode")
    task = TaskSpec.model_validate_json(args.task_spec.read_text(encoding="utf-8"))
    saved = ownership.load()
    run_id = args.agent_session_id or (saved.run_id if saved else f"task-{uuid4().hex}")
    budget = RunBudgetLedger(BudgetLimits(max_steps=task.max_steps,
        max_tool_calls=args.task_tool_limit, max_model_attempts=0, max_seconds=args.task_timeout))
    client = game_client or StdioMcpClient(
        _game_parameters(args), expected_server_name=SERVER_NAME,
        required_tools=GAME_TOOL_ALLOWLIST, exact_tools=True,
        connect_timeout_s=args.mcp_connect_timeout, request_timeout_s=args.mcp_request_timeout)
    harness = RecommendationHarness(game_client=client,
        journal_store=JsonJournalStore(args.journal_path), tool_log=JsonlToolLog(args.tool_log_path),
        agent_session_id=run_id, model_id="rule-observe-v1")
    runner = TaskRunner(task=task, run_id=run_id, harness=harness, store=store,
        policy=RuleDecisionPolicy(), context_builder=BoundedContextBuilder(),
        budget=budget, trace=JsonlRunTrace(args.run_trace_path), ownership=ownership)
    if runner.state.status in TERMINAL_STATUSES or (
            runner.state.status == "paused" and not args.resume_task):
        return (await runner.run()).model_dump(mode="json")
    try:
        # The total budget starts before connection, includes waits and cleanup.
        # StdioMcpClient also retains its independent bounded cleanup contract.
        async with asyncio.timeout(budget.remaining_seconds()):
            async with _task_client_lifetime(client, runner):
                result = await runner.run(resume=args.resume_task)
    except CheckpointConflict:
        raise
    except (Exception, asyncio.CancelledError) as exc:
        if runner._checkpoint_failed:
            raise
        reason = "run_deadline" if isinstance(exc, TimeoutError) else f"transport:{type(exc).__name__}"
        runner._emit("transport_lifecycle", transport="error", business=reason,
                     error_type=type(exc).__name__)
        if runner.state.status not in TERMINAL_STATUSES:
            runner._finish("cancelled" if isinstance(exc, asyncio.CancelledError) else "failed", reason)
        if isinstance(exc, asyncio.CancelledError):
            raise
        # A goal already verified remains terminal even if transport cleanup
        # fails. Report that separate failure explicitly, never silently pass.
        return {**runner.state.model_dump(mode="json"), "transport_lifecycle_error": reason}
    return result.model_dump(mode="json")


@asynccontextmanager
async def _task_client_lifetime(client, runner):
    """Cleanup cannot suppress/replace a body failure, especially cancel/CAS.

    Keep this inside the existing timeout so deadline cancellation retains the
    standard asyncio.timeout conversion after client cleanup has completed.
    """
    primary = None
    try:
        async with client:
            try:
                yield
            except BaseException as exc:
                primary = exc
                raise
    except BaseException as cleanup:
        if primary is not None and cleanup is not primary:
            primary.add_note(f"task_cleanup_error:{type(cleanup).__name__}")
            try:
                runner._emit("transport_cleanup", transport="error",
                    error_type=type(cleanup).__name__,
                    metadata={"primary_error_type": type(primary).__name__})
            except Exception as trace_error:
                primary.add_note(f"cleanup_trace_error:{type(trace_error).__name__}")
            raise primary from cleanup
        raise
    if primary is not None:
        # A managed client returning True must not swallow task cancellation/CAS.
        raise primary


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
