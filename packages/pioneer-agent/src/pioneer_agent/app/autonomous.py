"""Entry point for the autonomous observe → plan → act loop.

Usage:
  PYTHONPATH=src python3 -m pioneer_agent.app.autonomous
  PYTHONPATH=src python3 -m pioneer_agent.app.autonomous --max-iterations 5
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from pioneer_agent.adapters.bridge_client import BridgeClient
from pioneer_agent.app.cli_utils import user_path
from pioneer_agent.executor.ui_actions import UIActions
from pioneer_agent.perception.ui_registry import UIRegistry
from pioneer_agent.perception.vision import build_vision_client
from pioneer_agent.perception.vision_sync import VisionSync
from pioneer_agent.runbook.loader import RUNBOOK_LOAD_ERRORS, load_runbook_or_default
from pioneer_agent.runbook.lineup_binding import (
    operator_lineup_binding_map,
    parse_operator_lineup_binding,
)
from pioneer_agent.runbook.state_store import (
    RunbookStateStore,
    acquire_single_instance_lock,
    build_engine_from_store,
)
from pioneer_agent.runtime.autonomous_loop import AutonomousLoop
from pioneer_agent.safety.kill_switch import KillSwitch, default_kill_switch_path
from pioneer_agent.storage.loop_logger import LoopLogger
from pioneer_agent.storage.trace_store import TraceStore


def _lineup_preset_binding(value: str) -> tuple[str, str]:
    try:
        return parse_operator_lineup_binding(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the autonomous pioneer-agent loop.")
    parser.add_argument("--max-iterations", type=int, default=None,
                        help="Stop after N ticks (default: run forever).")
    parser.add_argument("--log-dir", type=user_path, default=Path("data/loop"),
                        help="Directory for loop.jsonl + archived screenshots.")
    parser.add_argument("--trace-path", type=user_path, default=None,
                        help="Structured trace JSONL path (default: log-dir/trace.jsonl).")
    parser.add_argument("--no-archive", action="store_true",
                        help="Skip archiving screenshot PNGs (JSONL only).")
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run perception + decision but skip UI action dispatch.")
    parser.add_argument("--stuck-threshold", type=int, default=3,
                        help="Consecutive idle/unknown ticks before ESC recovery (default: 3).")
    parser.add_argument("--vision-provider", choices=("gemini", "openai"), default=None,
                        help="Vision provider override. Defaults to PIONEER_VISION_PROVIDER or gemini.")
    parser.add_argument("--kill-switch-file", type=user_path, default=None,
                        help="Stop dispatching UI actions when this file exists.")
    parser.add_argument("--runbook", action="store_true",
                        help="Drive phases with the default opening runbook (see SANMOU_OPENING_RUNBOOK_PATH).")
    parser.add_argument("--runbook-path", type=user_path, default=None,
                        help="Explicit runbook YAML path (implies --runbook).")
    parser.add_argument("--runbook-state", type=user_path, default=None,
                        help="Runbook cursor/gate persistence file (default: log-dir/runbook_state.json).")
    parser.add_argument(
        "--lineup-preset-binding",
        type=_lineup_preset_binding,
        action="append",
        default=[],
        metavar="TEAM_ID=PRESET",
        help=(
            "Explicit operator binding for a currently observed team; may be repeated, "
            "expires after 4h, and implies --runbook."
        ),
    )
    args = parser.parse_args(argv)
    try:
        lineup_preset_bindings = operator_lineup_binding_map(
            args.lineup_preset_binding
        )
    except ValueError as exc:
        parser.error(str(exc))
    kill_switch_path = args.kill_switch_file or default_kill_switch_path(
        Path(__file__).resolve().parents[5]
    )

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    loop_logger = LoopLogger(args.log_dir, archive_screenshots=not args.no_archive)
    trace_store = TraceStore(args.trace_path or args.log_dir / "trace.jsonl")

    runbook_engine = None
    runbook_state_store = None
    runbook_requested = (
        args.runbook
        or args.runbook_path is not None
        or args.runbook_state is not None
        or bool(lineup_preset_bindings)
    )
    runbook_lock = None
    if runbook_requested:
        try:
            runbook = load_runbook_or_default(args.runbook_path)
        except RUNBOOK_LOAD_ERRORS as exc:
            parser.error(f"failed to load runbook: {exc}")
        if runbook is None:
            parser.error("--runbook requested but no runbook YAML was found")
        state_path = args.runbook_state or args.log_dir / "runbook_state.json"
        runbook_lock = acquire_single_instance_lock(
            state_path.with_name(state_path.name + ".lock")
        )
        if runbook_lock is None:
            parser.error(
                f"another autonomous loop already holds {state_path} "
                "(single-writer rule) — stop it or use a different --runbook-state"
            )
        runbook_state_store = RunbookStateStore(state_path)
        runbook_engine = build_engine_from_store(runbook, runbook_state_store)
        logging.getLogger(__name__).info(
            "runbook enabled: season=%s start_phase=%s",
            runbook.season,
            runbook_engine.current_phase.phase_id,
        )

    with BridgeClient() as bridge:
        vision = build_vision_client(args.vision_provider)
        registry = UIRegistry.load()
        ui = UIActions(bridge, registry, vision=vision)
        loop = AutonomousLoop(
            bridge=bridge,
            vision_sync=VisionSync(vision),
            ui_actions=ui,
            loop_logger=loop_logger,
            trace_store=trace_store,
            kill_switch=KillSwitch(kill_switch_path),
            runbook_engine=runbook_engine,
            runbook_state_store=runbook_state_store,
            lineup_preset_bindings=lineup_preset_bindings,
            dry_run=args.dry_run,
            stuck_threshold=args.stuck_threshold,
        )
        loop.run_forever(max_iterations=args.max_iterations)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
