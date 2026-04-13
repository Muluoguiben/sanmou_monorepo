"""Dispatch table mapping ActionType → concrete UI sequence.

Every handler takes `(action, ui)` and returns an ExecutionResult with:
  * status: "ok" | "pending" | "failed"
  * verification_status: "verified" | "unverified" | "not_applicable"
  * failure_reason: human-readable if not ok
  * summary: per-handler details (e.g. click pixel, matched label)

Clickable action types that depend on the dynamic vision locator are
marked `pending` until real in-game screenshots are available for the
panel sequences (征兵所 upgrade confirm dialog, attack launch flow, etc).
Wait actions are fully implemented — they are pure replanning signals.
"""
from __future__ import annotations

from typing import Callable

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction, ExecutionResult
from pioneer_agent.executor.ui_actions import UIActions

Handler = Callable[[CandidateAction, UIActions], ExecutionResult]


def _wait_handler(action: CandidateAction, _ui: UIActions) -> ExecutionResult:
    """Wait actions are decisions to replan later — no UI interaction."""
    return ExecutionResult(
        action_id=action.action_id,
        status="ok",
        verification_status="not_applicable",
        summary={"action_type": action.action_type.value, "note": "wait — no UI action"},
    )


def _claim_chapter_reward(action: CandidateAction, ui: UIActions) -> ExecutionResult:
    # Typical flow: open chapter panel (fixed) → click reward row (dynamic) → confirm.
    # Panel button is not yet in registry; flow needs calibration screenshots.
    return _pending(action, "chapter panel button not yet calibrated")


def _upgrade_building(action: CandidateAction, ui: UIActions) -> ExecutionResult:
    # Flow: already in city view → click the building (dynamic) → confirm upgrade (dynamic).
    # Requires: building name in action.params and an upgrade-confirm dialog screenshot.
    building = action.params.get("building_name") or action.params.get("building")
    if not building:
        return _fail(action, "missing building_name in params")
    return _pending(action, f"upgrade dialog for {building} not yet calibrated")


def _transfer_main_lineup(action: CandidateAction, _ui: UIActions) -> ExecutionResult:
    return _pending(action, "team transfer flow not yet calibrated")


def _attack_land(action: CandidateAction, _ui: UIActions) -> ExecutionResult:
    return _pending(action, "attack flow (出征 → 选武将 → 出战) not yet calibrated")


def _recruit_soldiers(action: CandidateAction, _ui: UIActions) -> ExecutionResult:
    return _pending(action, "recruit dialog (征兵所 → 征兵 → 确认) not yet calibrated")


def _abandon_land(action: CandidateAction, _ui: UIActions) -> ExecutionResult:
    return _pending(action, "abandon land flow not yet calibrated")


def _pending(action: CandidateAction, reason: str) -> ExecutionResult:
    return ExecutionResult(
        action_id=action.action_id,
        status="pending",
        verification_status="unverified",
        failure_reason=reason,
        recovery_required=False,
        summary={"action_type": action.action_type.value, "note": reason},
    )


def _fail(action: CandidateAction, reason: str) -> ExecutionResult:
    return ExecutionResult(
        action_id=action.action_id,
        status="failed",
        verification_status="unverified",
        failure_reason=reason,
        recovery_required=True,
        summary={"action_type": action.action_type.value},
    )


HANDLERS: dict[ActionType, Handler] = {
    ActionType.WAIT_FOR_RESOURCE: _wait_handler,
    ActionType.WAIT_FOR_STAMINA: _wait_handler,
    ActionType.CLAIM_CHAPTER_REWARD: _claim_chapter_reward,
    ActionType.UPGRADE_BUILDING: _upgrade_building,
    ActionType.TRANSFER_MAIN_LINEUP_TO_TEAM: _transfer_main_lineup,
    ActionType.ATTACK_LAND: _attack_land,
    ActionType.RECRUIT_SOLDIERS: _recruit_soldiers,
    ActionType.ABANDON_LAND: _abandon_land,
}


def dispatch(action: CandidateAction, ui: UIActions) -> ExecutionResult:
    handler = HANDLERS.get(action.action_type)
    if handler is None:
        return _fail(action, f"no handler for {action.action_type}")
    return handler(action, ui)
