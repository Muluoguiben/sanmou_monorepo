"""High-level UI action primitives used by the controller loop.

Bridges the gap between decision output (PlannedAction) and the low-level
bridge_client mouse/keyboard commands. Two tiers:

  * Fixed-position buttons (bottom menu, ESC close) — resolved via
    UIRegistry against live window size.
  * Dynamic targets (buildings, lands, hero rows) — resolved via the
    Gemini locator (`find_elements` + `to_pixel_box`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

from pioneer_agent.core.models import ObservationSnapshot
from pioneer_agent.executor.input_policy import InputPolicy
from pioneer_agent.executor.semantic_frame_guard import (
    ATOMIC_CLICK_AUTHORIZATION_SCOPES,
    FINAL_MUTATING_AUTHORIZATION_SCOPE,
    INTERMEDIATE_AUTHORIZATION_SCOPE,
    SEMANTIC_ROI_ALGORITHM,
    SemanticFrameGuard,
    authorization_scope_for_semantic_target,
    semantic_target_geometry,
)
from pioneer_agent.perception.ui_registry import UIRegistry
from pioneer_agent.perception.vision import (
    PixelBox,
    VisionClient,
    find_elements,
    to_pixel_box,
)


class _BridgeLike:
    """Protocol-ish type — anything with click/drag/screenshot/key_press."""

    atomic_frame_click_guard_version: int
    atomic_frame_click_guard_modes: frozenset[str]
    atomic_frame_click_authorization_scopes: frozenset[str]

    def click(
        self,
        x: int,
        y: int,
        button: str = "left",
        *,
        expected_window: dict[str, int] | None = None,
        expected_frame_sha256: str | None = None,
        guard_expires_at: str | None = None,
        authorization_scope: str | None = None,
        kill_switch_path: str | None = None,
        semantic_frame_guard: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...
    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.4, button: str = "left") -> dict[str, Any]: ...
    def screenshot(self, save_path: Path | str | None = None) -> bytes: ...
    def key_press(self, key: str, modifiers: list[str] | None = None) -> dict[str, Any]: ...


@dataclass
class ClickOutcome:
    success: bool
    px: tuple[int, int]
    reason: str | None = None
    matched_label: str | None = None
    trace: dict[str, Any] = field(default_factory=dict)


class UIActions:
    def __init__(
        self,
        bridge: _BridgeLike,
        registry: UIRegistry,
        vision: VisionClient | None = None,
        input_policy: InputPolicy | None = None,
    ) -> None:
        self.bridge = bridge
        self.registry = registry
        self.vision = vision
        self.input_policy = input_policy or InputPolicy()
        self._input_trace: list[dict[str, Any]] = []
        self._bound_observation: ObservationSnapshot | None = None
        self._bound_expected_window: dict[str, int] | None = None
        self._bound_operator_confirmation: dict[str, Any] | None = None
        self._bound_dispatch_at: str | None = None
        self._bound_semantic_frame_guard: SemanticFrameGuard | None = None
        self._bound_guard_expires_at: str | None = None
        self._bound_authorization_scope: str | None = None
        self._bound_kill_switch_path: str | None = None

    def bind_observation(
        self,
        observation: ObservationSnapshot | None,
        *,
        expected_window: dict[str, int] | None = None,
        operator_confirmation: dict[str, Any] | None = None,
        dispatch_at: str | None = None,
        semantic_frame_guard: dict[str, Any] | None = None,
        guard_expires_at: str | None = None,
        authorization_scope: str | None = None,
        kill_switch_path: str | None = None,
    ) -> None:
        self._bound_observation = observation
        self._bound_expected_window = (
            dict(expected_window) if expected_window is not None else None
        )
        self._bound_operator_confirmation = (
            dict(operator_confirmation)
            if operator_confirmation is not None
            else None
        )
        self._bound_dispatch_at = dispatch_at
        self._bound_semantic_frame_guard = (
            SemanticFrameGuard.model_validate(semantic_frame_guard)
            if semantic_frame_guard is not None
            else None
        )
        self._bound_guard_expires_at = guard_expires_at
        self._bound_authorization_scope = authorization_scope
        self._bound_kill_switch_path = kill_switch_path

    def reset_input_trace(self) -> None:
        self._input_trace.clear()

    def consume_input_trace(self) -> list[dict[str, Any]]:
        events = list(self._input_trace)
        self._input_trace.clear()
        return events

    # --- fixed positions --------------------------------------------------

    def click_button(self, key: str) -> ClickOutcome:
        verdict = self.input_policy.evaluate_button(key, registered_keys=self.registry.keys())
        if not verdict.allowed:
            return ClickOutcome(success=False, px=(0, 0), reason=verdict.reason)
        observation = self._bound_observation
        if observation is not None and observation.frame_size is not None:
            w, h = observation.frame_size
        else:
            png = self.bridge.screenshot()
            w, h = _image_size(png)
        button = self.registry.get(key)
        x, y = button.resolve(w, h)
        resp = self._click(x, y)
        ok = resp.get("status") == "ok"
        trace = _input_trace_event(
            action="click_button",
            coordinate_space="window:relative",
            raw_size=(w, h),
            click_point=(x, y),
            target={"key": key, "label": button.label},
        )
        if observation is not None:
            trace["observation"] = {
                "observation_id": observation.observation_id,
                "captured_at": observation.captured_at.isoformat(),
                "frame_sha256": observation.frame_sha256,
                "source": observation.source,
            }
        if self._bound_expected_window is not None:
            trace["expected_window"] = dict(self._bound_expected_window)
        self._add_confirmation_trace(trace)
        self._add_atomic_frame_guard_trace(trace, resp)
        self._input_trace.append(trace)
        return ClickOutcome(success=ok, px=(x, y), reason=None if ok else str(resp), trace=trace)

    # --- dynamic (vision-located) -----------------------------------------

    def click_element(self, query: str, *, index: int = 0) -> ClickOutcome:
        if self.vision is None:
            raise RuntimeError("VisionClient required for dynamic element clicks")
        verdict = self.input_policy.evaluate_element_query(query)
        if not verdict.allowed:
            return ClickOutcome(success=False, px=(0, 0), reason=verdict.reason)
        png = self.bridge.screenshot()
        w, h = _image_size(png)
        boxes = find_elements(self.vision, png, query)
        if not boxes:
            return ClickOutcome(success=False, px=(0, 0), reason=f"no match for: {query}")
        if index >= len(boxes):
            return ClickOutcome(success=False, px=(0, 0), reason=f"only {len(boxes)} matches for: {query}")
        pix: PixelBox = to_pixel_box(boxes[index], w, h)
        cx, cy = pix.center
        resp = self._click(cx, cy)
        ok = resp.get("status") == "ok"
        trace = _input_trace_event(
            action="click_element",
            coordinate_space="window:relative",
            raw_size=(w, h),
            click_point=(cx, cy),
            target={"query": query, "index": index, "matched_label": pix.label},
            normalized_bbox=_normalized_bbox(boxes[index]),
            pixel_bbox={"x": pix.x, "y": pix.y, "width": pix.width, "height": pix.height},
        )
        self._add_confirmation_trace(trace)
        self._add_atomic_frame_guard_trace(trace, resp)
        self._input_trace.append(trace)
        return ClickOutcome(
            success=ok,
            px=(cx, cy),
            matched_label=pix.label,
            reason=None if ok else str(resp),
            trace=trace,
        )

    def click_bbox(
        self,
        target_key: str,
        bbox: dict[str, Any],
        *,
        label: str | None = None,
    ) -> ClickOutcome:
        """Click a semantic bbox that was already produced by a vision domain.

        Domain bboxes use the same 0-1000 normalized coordinate space as the
        generic locator. Unlike `click_element`, this does not call vision again;
        it only uses a target key allowlist plus bbox validation.
        """
        verdict = self.input_policy.evaluate_semantic_target(target_key)
        if not verdict.allowed:
            return ClickOutcome(success=False, px=(0, 0), reason=verdict.reason)
        observation = self._bound_observation
        if observation is not None and observation.frame_size is not None:
            w, h = observation.frame_size
        else:
            png = self.bridge.screenshot()
            w, h = _image_size(png)
        try:
            roi_bbox, click_point = semantic_target_geometry((w, h), bbox)
        except ValueError:
            return ClickOutcome(success=False, px=(0, 0), reason=f"invalid bbox for: {target_key}")
        x_min = float(bbox["x_min"])
        y_min = float(bbox["y_min"])
        x_max = float(bbox["x_max"])
        y_max = float(bbox["y_max"])
        px_x, px_y = click_point.x, click_point.y
        pixel_bbox = {
            "x": roi_bbox.x,
            "y": roi_bbox.y,
            "width": roi_bbox.width,
            "height": roi_bbox.height,
        }
        bound_guard = self._bound_semantic_frame_guard
        if bound_guard is not None and (
            bound_guard.semantic_target_key != target_key
            or bound_guard.roi_bbox != roi_bbox
            or bound_guard.click_point != click_point
        ):
            return ClickOutcome(
                success=False,
                px=(px_x, px_y),
                reason="terminal semantic bbox does not match the confirmed ROI guard",
            )
        resp = self._click(px_x, px_y)
        ok = resp.get("status") == "ok"
        trace = _input_trace_event(
            action="click_semantic_bbox",
            coordinate_space="window:relative",
            raw_size=(w, h),
            click_point=(px_x, px_y),
            target={"key": target_key, "label": label or target_key},
            normalized_bbox={
                "x": x_min / 1000,
                "y": y_min / 1000,
                "width": (x_max - x_min) / 1000,
                "height": (y_max - y_min) / 1000,
            },
            pixel_bbox=pixel_bbox,
        )
        if observation is not None:
            trace["observation"] = {
                "observation_id": observation.observation_id,
                "captured_at": observation.captured_at.isoformat(),
                "frame_sha256": observation.frame_sha256,
                "source": observation.source,
            }
        if self._bound_expected_window is not None:
            trace["expected_window"] = dict(self._bound_expected_window)
        self._add_confirmation_trace(trace)
        self._add_atomic_frame_guard_trace(trace, resp)
        self._input_trace.append(trace)
        return ClickOutcome(
            success=ok,
            px=(px_x, px_y),
            matched_label=label,
            reason=None if ok else str(resp),
            trace=trace,
        )

    def _click(self, x: int, y: int) -> dict[str, Any]:
        if self._bound_expected_window is None:
            return self.bridge.click(x, y)
        observation = self._bound_observation
        confirmation = self._bound_operator_confirmation
        guard = self._bound_semantic_frame_guard
        expiry = self._bound_guard_expires_at
        scope = self._bound_authorization_scope
        kill_switch_path = self._bound_kill_switch_path
        if (
            observation is None
            or guard is None
            or not isinstance(expiry, str)
            or scope not in ATOMIC_CLICK_AUTHORIZATION_SCOPES
            or not isinstance(kill_switch_path, str)
            or not kill_switch_path
        ):
            return _atomic_guard_error(
                "guarded live click is missing its observation, ROI, deadline, scope, or kill switch"
            )
        if authorization_scope_for_semantic_target(guard.semantic_target_key) != scope:
            return _atomic_guard_error(
                "guarded live click authorization scope does not match its semantic target"
            )
        if scope == FINAL_MUTATING_AUTHORIZATION_SCOPE:
            if (
                confirmation is None
                or confirmation.get("frame_sha256") != observation.frame_sha256
                or confirmation.get("semantic_frame_guard")
                != guard.model_dump(mode="json")
                or confirmation.get("expires_at") != expiry
            ):
                return _atomic_guard_error(
                    "final guarded click does not match its operator confirmation"
                )
        elif confirmation is not None or scope != INTERMEDIATE_AUTHORIZATION_SCOPE:
            return _atomic_guard_error(
                "intermediate guarded click must use observation-only authorization"
            )
        if getattr(self.bridge, "atomic_frame_click_guard_version", None) != 1:
            return _atomic_guard_error(
                "bridge does not support atomic semantic ROI click guard v1"
            )
        modes = getattr(self.bridge, "atomic_frame_click_guard_modes", frozenset())
        if "semantic_roi_rgb24_sha256" not in modes:
            return _atomic_guard_error(
                "bridge does not advertise semantic ROI click validation"
            )
        scopes = getattr(
            self.bridge,
            "atomic_frame_click_authorization_scopes",
            frozenset(),
        )
        if scope not in scopes:
            return _atomic_guard_error(
                f"bridge does not advertise atomic authorization scope {scope}"
            )
        try:
            response = self.bridge.click(
                x,
                y,
                expected_window=dict(self._bound_expected_window),
                expected_frame_sha256=observation.frame_sha256,
                guard_expires_at=expiry,
                authorization_scope=scope,
                kill_switch_path=kill_switch_path,
                semantic_frame_guard=guard.model_dump(mode="json"),
            )
        except (TypeError, ValueError, RuntimeError) as exc:
            return _atomic_guard_error(
                f"bridge rejected atomic semantic ROI click: {exc}"
            )
        if response.get("status") != "ok":
            return response
        proof = response.get("atomic_frame_guard")
        if (
            not isinstance(proof, dict)
            or proof.get("verified") is not True
            or proof.get("mode") != "semantic_roi_rgb24_sha256"
            or proof.get("expected_roi_sha256") != guard.roi_sha256
            or proof.get("captured_roi_sha256") != guard.roi_sha256
            or proof.get("guard_expires_at") != expiry
            or proof.get("authorization_scope") != scope
            or not _valid_kill_switch_attestation(proof.get("kill_switch_guard"))
        ):
            return _atomic_guard_error(
                "bridge omitted a valid semantic ROI click attestation"
            )
        return response

    def _add_confirmation_trace(self, trace: dict[str, Any]) -> None:
        confirmation = self._bound_operator_confirmation
        if confirmation is None or self._bound_dispatch_at is None:
            return
        trace["confirmation_id"] = confirmation.get("confirmation_id")
        trace["confirmed_at"] = confirmation.get("confirmed_at")
        trace["dispatch_at"] = self._bound_dispatch_at
        trace["operator_confirmation"] = dict(confirmation)

    def _add_atomic_frame_guard_trace(
        self,
        trace: dict[str, Any],
        response: dict[str, Any],
    ) -> None:
        guard = self._bound_semantic_frame_guard
        if guard is None:
            return
        proof = response.get("atomic_frame_guard")
        trace["atomic_frame_guard"] = {
            "required": True,
            "algorithm": SEMANTIC_ROI_ALGORITHM,
            "authorization_scope": self._bound_authorization_scope,
            "guard_expires_at": self._bound_guard_expires_at,
            "binding": guard.model_dump(mode="json"),
            "bridge_verified": (
                isinstance(proof, dict) and proof.get("verified") is True
            ),
            "bridge_attestation": dict(proof) if isinstance(proof, dict) else None,
        }

    # --- navigation -------------------------------------------------------

    def pan_map(self, dx: int, dy: int, duration: float = 0.4) -> ClickOutcome:
        """Drag the map by (dx, dy) from the window center."""
        verdict = self.input_policy.evaluate_drag()
        if not verdict.allowed:
            return ClickOutcome(success=False, px=(0, 0), reason=verdict.reason)
        png = self.bridge.screenshot()
        w, h = _image_size(png)
        cx, cy = w // 2, h // 2
        resp = self.bridge.drag(cx, cy, cx + dx, cy + dy, duration=duration)
        ok = resp.get("status") == "ok"
        trace = _input_trace_event(
            action="drag",
            coordinate_space="window:relative",
            raw_size=(w, h),
            click_point=(cx + dx, cy + dy),
            target={"from": _point_dict(cx, cy), "to": _point_dict(cx + dx, cy + dy), "duration": duration},
        )
        self._input_trace.append(trace)
        return ClickOutcome(success=ok, px=(cx + dx, cy + dy), reason=None if ok else str(resp), trace=trace)

    def close_popup(self) -> ClickOutcome:
        # Prefer ESC keystroke over clicking the X, which may not exist on every dialog.
        verdict = self.input_policy.evaluate_key("escape")
        if not verdict.allowed:
            return ClickOutcome(success=False, px=(0, 0), reason=verdict.reason)
        resp = self.bridge.key_press("escape")
        ok = resp.get("status") == "ok"
        trace = {
            "action": "key_press",
            "key": "escape",
            "coordinate_space": "keyboard",
        }
        self._input_trace.append(trace)
        return ClickOutcome(success=ok, px=(0, 0), reason=None if ok else str(resp), trace=trace)


def _image_size(png_bytes: bytes) -> tuple[int, int]:
    img = Image.open(BytesIO(png_bytes))
    return img.width, img.height


def _atomic_guard_error(message: str) -> dict[str, Any]:
    return {
        "status": "error",
        "message": message,
        "atomic_frame_guard": {"verified": False},
    }


def _valid_kill_switch_attestation(value: Any) -> bool:
    if not isinstance(value, dict) or value.get("checked") is not True:
        return False
    checks = value.get("checks")
    if not isinstance(checks, list):
        return False
    expected_stages = (
        "before_capture",
        "after_capture",
        "before_input_injection",
    )
    return tuple(
        item.get("stage") if isinstance(item, dict) else None
        for item in checks
    ) == expected_stages and all(
        isinstance(item, dict)
        and item.get("parent_accessible") is True
        and item.get("stop_file_present") is False
        and isinstance(item.get("checked_at"), str)
        for item in checks
    )


def _input_trace_event(
    *,
    action: str,
    coordinate_space: str,
    raw_size: tuple[int, int],
    click_point: tuple[int, int],
    target: dict[str, Any],
    normalized_bbox: dict[str, float] | None = None,
    pixel_bbox: dict[str, int] | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "action": action,
        "coordinate_space": coordinate_space,
        "window_coordinate_space": "window:relative",
        "display_coordinate_space": "unknown",
        "raw_size": {"width": raw_size[0], "height": raw_size[1]},
        "prepared_size": {"width": raw_size[0], "height": raw_size[1]},
        "scale": 1.0,
        "click_point": _point_dict(*click_point),
        "target": target,
    }
    if normalized_bbox is not None:
        event["normalized_bbox"] = normalized_bbox
    if pixel_bbox is not None:
        event["pixel_bbox"] = pixel_bbox
    return event


def _normalized_bbox(box: Any) -> dict[str, float]:
    x1 = min(box.x_min, box.x_max) / 1000
    x2 = max(box.x_min, box.x_max) / 1000
    y1 = min(box.y_min, box.y_max) / 1000
    y2 = max(box.y_min, box.y_max) / 1000
    return {
        "x": x1,
        "y": y1,
        "width": x2 - x1,
        "height": y2 - y1,
    }


def _parse_normalized_bbox(payload: dict[str, Any]) -> tuple[int, int, int, int] | None:
    try:
        x_min = int(payload["x_min"])
        y_min = int(payload["y_min"])
        x_max = int(payload["x_max"])
        y_max = int(payload["y_max"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (0 <= x_min < x_max <= 1000 and 0 <= y_min < y_max <= 1000):
        return None
    return x_min, y_min, x_max, y_max


def _point_dict(x: int, y: int) -> dict[str, int]:
    return {"x": x, "y": y}
