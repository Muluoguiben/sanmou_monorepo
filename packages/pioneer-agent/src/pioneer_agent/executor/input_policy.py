from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class InputKind(str, Enum):
    CLICK_BUTTON = "click_button"
    CLICK_ELEMENT = "click_element"
    CLICK_SEMANTIC_BBOX = "click_semantic_bbox"
    DRAG = "drag"
    KEY_PRESS = "key_press"


@dataclass(frozen=True)
class InputPolicyVerdict:
    allowed: bool
    reason: str
    kind: InputKind


@dataclass(frozen=True)
class InputPolicy:
    allowed_button_keys: frozenset[str] | None = None
    allowed_element_queries: frozenset[str] = field(default_factory=frozenset)
    allowed_semantic_targets: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "chapter_claim_button",
                "recruit_button",
                "upgrade_confirm_button",
            }
        )
    )
    allowed_keys: frozenset[str] = field(default_factory=lambda: frozenset({"escape"}))
    allow_map_drag: bool = False

    def evaluate_button(
        self,
        key: str,
        *,
        registered_keys: Iterable[str],
    ) -> InputPolicyVerdict:
        if key not in set(registered_keys):
            return InputPolicyVerdict(
                allowed=False,
                reason=f"button key is not registered: {key}",
                kind=InputKind.CLICK_BUTTON,
            )
        if self.allowed_button_keys is not None and key not in self.allowed_button_keys:
            return InputPolicyVerdict(
                allowed=False,
                reason=f"button key is not allowlisted: {key}",
                kind=InputKind.CLICK_BUTTON,
            )
        return InputPolicyVerdict(
            allowed=True,
            reason="registered button is allowed",
            kind=InputKind.CLICK_BUTTON,
        )

    def evaluate_element_query(self, query: str) -> InputPolicyVerdict:
        if query not in self.allowed_element_queries:
            return InputPolicyVerdict(
                allowed=False,
                reason=f"dynamic element query is not allowlisted: {query}",
                kind=InputKind.CLICK_ELEMENT,
            )
        return InputPolicyVerdict(
            allowed=True,
            reason="dynamic element query is allowlisted",
            kind=InputKind.CLICK_ELEMENT,
        )

    def evaluate_semantic_target(self, target_key: str) -> InputPolicyVerdict:
        if target_key not in self.allowed_semantic_targets:
            return InputPolicyVerdict(
                allowed=False,
                reason=f"semantic bbox target is not allowlisted: {target_key}",
                kind=InputKind.CLICK_SEMANTIC_BBOX,
            )
        return InputPolicyVerdict(
            allowed=True,
            reason="semantic bbox target is allowlisted",
            kind=InputKind.CLICK_SEMANTIC_BBOX,
        )

    def evaluate_drag(self) -> InputPolicyVerdict:
        if not self.allow_map_drag:
            return InputPolicyVerdict(
                allowed=False,
                reason="map drag is not enabled by input policy",
                kind=InputKind.DRAG,
            )
        return InputPolicyVerdict(
            allowed=True,
            reason="map drag is enabled",
            kind=InputKind.DRAG,
        )

    def evaluate_key(self, key: str) -> InputPolicyVerdict:
        normalized = key.lower().strip()
        if normalized not in self.allowed_keys:
            return InputPolicyVerdict(
                allowed=False,
                reason=f"key is not allowlisted: {key}",
                kind=InputKind.KEY_PRESS,
            )
        return InputPolicyVerdict(
            allowed=True,
            reason="key is allowlisted",
            kind=InputKind.KEY_PRESS,
        )
