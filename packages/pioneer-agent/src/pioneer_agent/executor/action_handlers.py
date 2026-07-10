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

from typing import Any, Callable

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


def _advisor_only_handler(action: CandidateAction, _ui: UIActions) -> ExecutionResult:
    """Advisor-only inspection actions never dispatch UI input."""
    return ExecutionResult(
        action_id=action.action_id,
        status="ok",
        verification_status="not_applicable",
        summary={
            "action_type": action.action_type.value,
            "note": "advisor inspection — no UI action",
        },
    )


def _claim_chapter_reward(action: CandidateAction, ui: UIActions) -> ExecutionResult:
    button = _button_param(action.params.get("claim_button"))
    if button is None:
        return _pending(action, "chapter claim button bbox not observed")
    return _click_semantic_button(
        action,
        ui,
        button=button,
        target_key="chapter_claim_button",
        label="章节奖励领取",
    )


def _upgrade_building(action: CandidateAction, ui: UIActions) -> ExecutionResult:
    # Safe first slice: when already on the upgrade dialog, click the visible
    # enabled confirm button from semantic perception. Opening arbitrary building
    # panels still stays pending until that sequence is calibrated.
    building = action.params.get("building_name") or action.params.get("building")
    if not building:
        return _fail(action, "missing building_name in params")
    dialog = action.params.get("upgrade_dialog")
    if (
        isinstance(dialog, dict)
        and "visible" in dialog
        and not isinstance(dialog.get("visible"), bool)
    ):
        return _fail(action, "upgrade_dialog.visible must be an observed boolean")
    if not isinstance(dialog, dict) or dialog.get("visible") is not True:
        button = _button_param(action.params.get("upgrade_button"))
        if button is None:
            return _pending(action, f"upgrade dialog for {building} not yet observed")
        return _click_semantic_button(
            action,
            ui,
            button=button,
            target_key="building_upgrade_button",
            label=f"升级入口:{building}",
            flow_step="open_upgrade_dialog",
            terminal_for_verifier=False,
        )
    dialog_building = dialog.get("building_name")
    if dialog_building and str(dialog_building) != str(building):
        return _fail(action, f"upgrade dialog building mismatch: expected {building}, saw {dialog_building}")
    if dialog.get("can_upgrade") is False:
        return _fail(action, f"upgrade dialog for {building} is not upgradeable")
    current_level = action.params.get("current_level")
    target_level = action.params.get("target_level")
    dialog_current = dialog.get("current_level")
    dialog_next = dialog.get("next_level")
    for field_name, value in (
        ("current_level", current_level),
        ("target_level", target_level),
        ("upgrade_dialog.current_level", dialog_current),
        ("upgrade_dialog.next_level", dialog_next),
    ):
        if isinstance(value, bool) or not isinstance(value, int):
            return _fail(action, f"{field_name} must be an observed integer")
    if dialog_current != current_level:
        return _fail(
            action,
            f"upgrade dialog baseline mismatch: expected {current_level}, saw {dialog_current}",
        )
    if dialog_next != target_level or target_level != current_level + 1:
        return _fail(
            action,
            f"upgrade dialog target mismatch: expected {target_level}, saw {dialog_next}",
        )
    button = _button_param(dialog.get("confirm_button"))
    if button is None:
        return _pending(action, f"upgrade confirm button for {building} not yet observed")
    return _click_semantic_button(
        action,
        ui,
        button=button,
        target_key="upgrade_confirm_button",
        label=f"升级确认:{building}",
        flow_step="confirm_upgrade",
    )


def _transfer_main_lineup(action: CandidateAction, _ui: UIActions) -> ExecutionResult:
    return _pending(action, "team transfer flow not yet calibrated")


def _attack_land(action: CandidateAction, _ui: UIActions) -> ExecutionResult:
    return _pending(action, "attack flow (出征 → 选武将 → 出战) not yet calibrated")


def _recruit_soldiers(action: CandidateAction, _ui: UIActions) -> ExecutionResult:
    button = _button_param(action.params.get("recruit_button"))
    if button is None:
        return _pending(action, "recruit button bbox not observed")
    return _click_semantic_button(
        action,
        _ui,
        button=button,
        target_key="recruit_button",
        label=f"征兵:{action.params.get('team_id') or 'visible_team'}",
    )


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


def _button_param(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return value


def terminal_mutating_target(action: CandidateAction) -> str | None:
    """Return the semantic target for a final M1a mutating click, if any."""
    binding = terminal_mutating_binding(action)
    return binding[0] if binding is not None else None


def terminal_mutating_binding(
    action: CandidateAction,
) -> tuple[str, dict[str, Any]] | None:
    """Return the exact target key and bbox used by a final M1a click."""
    binding = semantic_click_binding(action)
    if binding is None or binding[2] is not True:
        return None
    return binding[0], binding[1]


def semantic_click_binding(
    action: CandidateAction,
) -> tuple[str, dict[str, Any], bool] | None:
    """Return the exact click target, bbox, and terminal flag used by dispatch."""
    if action.action_type == ActionType.CLAIM_CHAPTER_REWARD:
        button = _button_param(action.params.get("claim_button"))
        if button is not None and isinstance(button.get("bbox"), dict):
            return "chapter_claim_button", dict(button["bbox"]), True
        return None
    if action.action_type == ActionType.RECRUIT_SOLDIERS:
        button = _button_param(action.params.get("recruit_button"))
        if button is not None and isinstance(button.get("bbox"), dict):
            return "recruit_button", dict(button["bbox"]), True
        return None
    if action.action_type == ActionType.UPGRADE_BUILDING:
        dialog = action.params.get("upgrade_dialog")
        if (
            isinstance(dialog, dict)
            and dialog.get("visible") is True  # exact bool; truthy values never bypass
        ):
            button = _button_param(dialog.get("confirm_button"))
            if button is not None and isinstance(button.get("bbox"), dict):
                return "upgrade_confirm_button", dict(button["bbox"]), True
            return None
        if (
            isinstance(dialog, dict)
            and "visible" in dialog
            and not isinstance(dialog.get("visible"), bool)
        ):
            return None
        button = _button_param(action.params.get("upgrade_button"))
        if button is not None and isinstance(button.get("bbox"), dict):
            return "building_upgrade_button", dict(button["bbox"]), False
    return None


def _click_semantic_button(
    action: CandidateAction,
    ui: UIActions,
    *,
    button: dict[str, Any],
    target_key: str,
    label: str,
    flow_step: str | None = None,
    terminal_for_verifier: bool = True,
) -> ExecutionResult:
    if not button.get("visible"):
        return _fail(action, f"{target_key} is not visible")
    if not button.get("enabled"):
        return _fail(action, f"{target_key} is disabled")
    bbox = button.get("bbox")
    if not isinstance(bbox, dict):
        return _pending(action, f"{target_key} bbox missing")
    outcome = ui.click_bbox(target_key, bbox, label=label)
    if not outcome.success:
        return _fail(action, outcome.reason or f"{target_key} click failed")
    step = {
        "flow_step": flow_step or target_key,
        "target_key": target_key,
        "click_px": {"x": outcome.px[0], "y": outcome.px[1]},
        "matched_label": outcome.matched_label,
        "terminal_for_verifier": terminal_for_verifier,
    }
    return ExecutionResult(
        action_id=action.action_id,
        status="ok",
        verification_status="unverified" if terminal_for_verifier else "not_applicable",
        recovery_required=False,
        summary={
            "action_type": action.action_type.value,
            "target_key": target_key,
            "click_px": {"x": outcome.px[0], "y": outcome.px[1]},
            "matched_label": outcome.matched_label,
            "flow_step": step["flow_step"],
            "flow_steps": [step],
            "terminal_for_verifier": terminal_for_verifier,
        },
    )


HANDLERS: dict[ActionType, Handler] = {
    ActionType.WAIT_FOR_RESOURCE: _wait_handler,
    ActionType.WAIT_FOR_STAMINA: _wait_handler,
    ActionType.CLAIM_CHAPTER_REWARD: _claim_chapter_reward,
    ActionType.UPGRADE_BUILDING: _upgrade_building,
    ActionType.TRANSFER_MAIN_LINEUP_TO_TEAM: _transfer_main_lineup,
    ActionType.ATTACK_LAND: _attack_land,
    ActionType.RECRUIT_SOLDIERS: _recruit_soldiers,
    ActionType.INSPECT_TEAM_READINESS: _advisor_only_handler,
    ActionType.ABANDON_LAND: _abandon_land,
}


def dispatch(action: CandidateAction, ui: UIActions) -> ExecutionResult:
    handler = HANDLERS.get(action.action_type)
    if handler is None:
        return _fail(action, f"no handler for {action.action_type}")
    return handler(action, ui)
