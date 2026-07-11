"""Entry point for the autonomous observe → plan → act loop.

Usage:
  PYTHONPATH=src python3 -m pioneer_agent.app.autonomous
  PYTHONPATH=src python3 -m pioneer_agent.app.autonomous --max-iterations 5
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from pioneer_agent.adapters.bridge_client import BridgeClient
from pioneer_agent.app.cli_utils import user_path
from pioneer_agent.core.device import (
    CapabilityFlags,
    DevicePlatform,
    DeviceProfile,
    DeviceSession,
    ObservationSource,
    ObservationSourceType,
    Orientation,
)
from pioneer_agent.core.enums import ActionType
from pioneer_agent.executor.ui_actions import UIActions
from pioneer_agent.executor.operator_confirmation import (
    JsonlOperatorConfirmationStore,
    WaitingOperatorConfirmationProvider,
)
from pioneer_agent.executor.ui_runner import UIActionRunner
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
from pioneer_agent.runtime.architecture_gates import (
    LOW_RISK_AUTOMATION_ACTIONS,
    AutomationMode,
    AutomationReadinessGate,
)
from pioneer_agent.runtime.autonomous_loop import AutonomousLoop, TickResult
from pioneer_agent.safety.kill_switch import KillSwitch, default_kill_switch_path
from pioneer_agent.safety.guard import SessionMode
from pioneer_agent.storage.loop_logger import LoopLogger
from pioneer_agent.storage.trace_store import TraceStore


def _lineup_preset_binding(value: str) -> tuple[str, str]:
    try:
        return parse_operator_lineup_binding(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _add_execution_mode_args(parser: argparse.ArgumentParser) -> None:
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--execute",
        dest="execution_mode",
        action="store_const",
        const="execute",
        help=(
            "Reserved formal execution mode; currently disabled until a committed "
            "QA attestation can be recomputed from trusted M1a evidence."
        ),
    )
    mode.add_argument(
        "--dry-run",
        dest="execution_mode",
        action="store_const",
        const="dry_run",
        help="Run perception + decision but skip UI action dispatch (default).",
    )
    mode.add_argument(
        "--evidence-capture",
        dest="execution_mode",
        action="store_const",
        const="evidence_capture",
        help="Run one explicitly confirmed low-risk action to collect closure evidence.",
    )
    parser.set_defaults(execution_mode="dry_run")


def _resolve_execution_policy(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> tuple[bool, AutomationMode, AutomationReadinessGate]:
    if args.execution_mode == "dry_run":
        if args.evidence_action is not None or args.confirm_evidence_capture:
            parser.error("evidence arguments require --evidence-capture")
        return True, AutomationMode.SEMI_AUTO, AutomationReadinessGate()

    if args.execution_mode == "execute":
        parser.error(
            "--execute is disabled: no trusted M1a closure evidence exists; "
            "formal execution must wait for a committed QA attestation that can be "
            "recomputed from bound live traces"
        )

    if args.execution_mode != "evidence_capture":
        parser.error(f"unsupported execution mode: {args.execution_mode!r}")
    if args.max_iterations != 1:
        parser.error("--evidence-capture requires --max-iterations 1")
    if args.evidence_action is None:
        parser.error("--evidence-capture requires --evidence-action")
    if not args.confirm_evidence_capture:
        parser.error("--evidence-capture requires --confirm-evidence-capture")
    try:
        gate = AutomationReadinessGate.for_evidence_capture(
            args.evidence_action,
            human_confirmed=True,
        )
    except ValueError as exc:
        parser.error(str(exc))
    return False, AutomationMode.EVIDENCE_CAPTURE, gate


def _build_live_device_session(bridge: BridgeClient) -> DeviceSession:
    window = dict(bridge.window_info())
    width = window.get("width")
    height = window.get("height")
    hwnd = window.get("hwnd")
    pid = window.get("pid")
    if (
        not isinstance(width, int)
        or isinstance(width, bool)
        or width <= 0
        or not isinstance(height, int)
        or isinstance(height, bool)
        or height <= 0
        or window.get("usable") is not True
        or window.get("visible") is not True
        or window.get("iconic") is not False
        or window.get("offscreen") is not False
        or not isinstance(hwnd, int)
        or isinstance(hwnd, bool)
        or hwnd <= 0
        or not isinstance(pid, int)
        or isinstance(pid, bool)
        or pid <= 0
    ):
        raise RuntimeError("bridge window is not visible and usable")
    capabilities = CapabilityFlags(
        live_capture=True,
        input_control=True,
        reliable_window_info=True,
    )
    source = ObservationSource(
        source_type=ObservationSourceType.WINDOWS_WINDOW_CAPTURE,
        capabilities=capabilities,
        metadata={
            "bridge_port": bridge.port,
            "hwnd": hwnd,
            "pid": pid,
        },
    )
    return DeviceSession(
        profile=DeviceProfile(
            platform=DevicePlatform.PC_CLIENT,
            resolution=(width, height),
            screenshot_size=(width, height),
            orientation=(
                Orientation.LANDSCAPE if width >= height else Orientation.PORTRAIT
            ),
        ),
        source=source,
        capabilities=capabilities,
    )


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
    _add_execution_mode_args(parser)
    parser.add_argument(
        "--evidence-action",
        choices=tuple(sorted(item.value for item in LOW_RISK_AUTOMATION_ACTIONS)),
        default=None,
        help="Exact low-risk action authorized for --evidence-capture.",
    )
    parser.add_argument(
        "--confirm-evidence-capture",
        action="store_true",
        help=(
            "Explicitly authorize opening a frame-bound confirmation request; "
            "the final click still requires a separate one-shot grant."
        ),
    )
    parser.add_argument(
        "--operator-confirmation-store",
        type=user_path,
        default=None,
        help="Append-only grant/consume JSONL (default: log-dir/operator_confirmations.jsonl).",
    )
    parser.add_argument(
        "--operator-confirmation-request",
        type=user_path,
        default=None,
        help=(
            "Short-lived exact request shown to the operator "
            "(default: log-dir/operator_confirmation_request.json)."
        ),
    )
    parser.add_argument(
        "--operator-confirmation-wait-seconds",
        type=float,
        default=15.0,
        help="Maximum terminal-frame confirmation wait (default: 15, hard fail on timeout).",
    )
    parser.add_argument(
        "--operator-confirmation-poll-seconds",
        type=float,
        default=0.2,
        help="Grant-store poll interval while waiting (default: 0.2).",
    )
    parser.add_argument(
        "--operator-confirmation-ttl-seconds",
        type=float,
        default=10.0,
        help="Maximum one-shot grant TTL within the request window (default: 10).",
    )
    parser.add_argument(
        "--stuck-threshold",
        type=int,
        default=3,
        help=(
            "Consecutive idle/unknown ticks before recovery evaluation (default: 3); "
            "automatic ESC input remains disabled for live sessions."
        ),
    )
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
    dry_run, automation_mode, automation_gate = _resolve_execution_policy(
        args,
        parser,
    )
    project_root = Path(__file__).resolve().parents[5]
    kill_switch_path = (
        args.kill_switch_file or default_kill_switch_path(project_root)
    ).resolve()
    if not dry_run:
        try:
            kill_switch_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            parser.error(f"kill-switch parent is not accessible: {exc}")
    kill_switch = KillSwitch(kill_switch_path)

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    loop_logger = LoopLogger(args.log_dir, archive_screenshots=not args.no_archive)
    trace_store = TraceStore(args.trace_path or args.log_dir / "trace.jsonl")
    operator_confirmation_provider = None
    if not dry_run:
        confirmation_store_path = (
            args.operator_confirmation_store
            or args.log_dir / "operator_confirmations.jsonl"
        )
        confirmation_request_path = (
            args.operator_confirmation_request
            or args.log_dir / "operator_confirmation_request.json"
        )
        try:
            confirmation_store = JsonlOperatorConfirmationStore(
                confirmation_store_path,
                max_ttl_seconds=30.0,
            )
            operator_confirmation_provider = WaitingOperatorConfirmationProvider(
                confirmation_store,
                confirmation_request_path,
                wait_timeout_seconds=args.operator_confirmation_wait_seconds,
                poll_interval_seconds=args.operator_confirmation_poll_seconds,
                confirmation_ttl_seconds=args.operator_confirmation_ttl_seconds,
                abort_if=kill_switch.is_triggered,
            )
        except ValueError as exc:
            parser.error(f"invalid operator confirmation channel: {exc}")
        logging.getLogger(__name__).warning(
            "final mutating clicks require a separate frame-bound grant: "
            "request=%s (review/grant with pioneer_agent.app.operator_confirmation), "
            "store=%s",
            confirmation_request_path,
            confirmation_store_path,
        )

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
        runner = None
        if not dry_run:
            logging.getLogger(__name__).warning(
                "live UI execution explicitly enabled in %s mode",
                automation_mode.value,
            )
            try:
                device_session = _build_live_device_session(bridge)
            except (ConnectionError, RuntimeError, TypeError, ValueError) as exc:
                parser.error(f"cannot start live evidence capture: {exc}")
            runner = UIActionRunner(
                ui,
                device_session=device_session,
                capabilities=device_session.capabilities,
                session_mode=SessionMode.LIVE,
                automation_mode=automation_mode,
                automation_gate=automation_gate,
                operator_confirmation_provider=operator_confirmation_provider,
                kill_switch_path=kill_switch_path,
            )
        loop = AutonomousLoop(
            bridge=bridge,
            vision_sync=VisionSync(vision),
            ui_actions=ui,
            runner=runner,
            loop_logger=loop_logger,
            trace_store=trace_store,
            kill_switch=kill_switch,
            runbook_engine=runbook_engine,
            runbook_state_store=runbook_state_store,
            lineup_preset_bindings=lineup_preset_bindings,
            evidence_action_type=(
                ActionType(args.evidence_action)
                if automation_mode == AutomationMode.EVIDENCE_CAPTURE
                else None
            ),
            dry_run=dry_run,
            stuck_threshold=args.stuck_threshold,
        )
        if automation_mode == AutomationMode.EVIDENCE_CAPTURE:
            expected_action = ActionType(args.evidence_action)
            try:
                result = loop.tick(0)
            except Exception as exc:  # noqa: BLE001
                # Provider/bridge exceptions can contain paths or response
                # payloads. Keep stdout machine-stable and log only the type.
                logging.getLogger(__name__).error(
                    "evidence capture tick failed (exception_type=%s)",
                    type(exc).__name__,
                )
                print(
                    json.dumps(
                        {
                            "mode": "evidence_capture",
                            "expected_action": expected_action.value,
                            "success": False,
                            "error_code": "evidence_tick_failed",
                            "exception_type": type(exc).__name__,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                )
                return 2
            summary = _evidence_capture_summary(result, expected_action=expected_action)
            print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
            return 0 if summary["success"] else 3
        loop.run_forever(max_iterations=args.max_iterations)
    return 0


def _evidence_capture_summary(
    result: TickResult,
    *,
    expected_action: ActionType,
) -> dict[str, object]:
    selected = result.selection.selected_action
    execution = result.execution
    selected_action = selected.action_type if selected is not None else None
    validation_issues = _evidence_capture_validation_issues(
        result,
        expected_action=expected_action,
    )
    constraint = result.selection.selection_reason.get(
        "evidence_action_constraint"
    )
    return {
        "mode": "evidence_capture",
        "expected_action": expected_action.value,
        "selected_action": selected_action.value if selected_action is not None else None,
        "selected_action_id": selected.action_id if selected is not None else None,
        "execution_status": execution.status if execution is not None else None,
        "verification_status": (
            execution.verification_status if execution is not None else None
        ),
        "execution_reported_failure": (
            execution.failure_reason is not None if execution is not None else False
        ),
        "recovery_required": (
            execution.recovery_required if execution is not None else False
        ),
        "selection_constraint": constraint if isinstance(constraint, dict) else None,
        "validation_issues": validation_issues,
        "success": not validation_issues,
    }


def _evidence_capture_validation_issues(
    result: TickResult,
    *,
    expected_action: ActionType,
) -> list[str]:
    issues: list[str] = []
    selected = result.selection.selected_action
    execution = result.execution
    if selected is None:
        return ["no_current_frame_candidate"]
    if selected.action_type != expected_action:
        issues.append("selected_action_type_mismatch")
    if not isinstance(selected.action_id, str) or not selected.action_id.strip():
        issues.append("selected_action_id_invalid")
    if execution is None:
        issues.append("execution_missing")
        return issues
    if execution.action_id != selected.action_id:
        issues.append("execution_action_id_mismatch")
    if execution.status != "ok":
        issues.append("execution_not_ok")
    if execution.verification_status != "verified":
        issues.append("execution_not_verified")
    if execution.failure_reason is not None:
        issues.append("execution_has_failure_reason")
    if execution.recovery_required is not False:
        issues.append("execution_requires_recovery")

    verifier = execution.summary.get("post_action_verifier")
    if not isinstance(verifier, dict):
        issues.append("post_action_verifier_missing")
        return issues
    if verifier.get("action_type") != selected.action_type.value:
        issues.append("post_action_verifier_action_mismatch")
    if verifier.get("status") != "verified":
        issues.append("post_action_verifier_not_verified")

    target_fields = {
        ActionType.CLAIM_CHAPTER_REWARD: ("chapter_id",),
        ActionType.RECRUIT_SOLDIERS: ("team_id",),
        ActionType.UPGRADE_BUILDING: (
            "building_name",
            "current_level",
            "target_level",
        ),
    }.get(selected.action_type, ())
    if not target_fields or any(field not in selected.params for field in target_fields):
        issues.append("selected_action_target_identity_incomplete")
    else:
        expected_target = {field: selected.params[field] for field in target_fields}
        if verifier.get("target_identity") != expected_target:
            issues.append("post_action_verifier_target_mismatch")

    checked = verifier.get("checked")
    if not isinstance(checked, list) or not checked:
        issues.append("post_action_verifier_checks_missing")
    deltas = verifier.get("post_action_delta")
    if (
        not isinstance(deltas, list)
        or not deltas
        or any(not isinstance(delta, dict) for delta in deltas)
    ):
        issues.append("post_action_delta_missing")
    post_observe = verifier.get("post_observe")
    if not isinstance(post_observe, dict):
        issues.append("post_action_observation_missing")
    else:
        if not isinstance(post_observe.get("observation"), dict):
            issues.append("post_action_observation_missing")
        frame = post_observe.get("frame")
        if not isinstance(frame, dict) or frame.get("role") != "post_action":
            issues.append("post_action_frame_missing")
    return sorted(set(issues))


if __name__ == "__main__":
    raise SystemExit(main())
