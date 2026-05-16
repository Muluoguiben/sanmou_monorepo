from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pioneer_agent.core.enums import ActionType
from pioneer_agent.verifier.base import (
    ExpectedStateDelta,
    VerificationResult,
    VerificationStatus,
    VerifierBase,
)


@dataclass(frozen=True)
class ActionVerifierEvalCase:
    case_id: str
    action_type: ActionType
    case_type: str
    expected_deltas: tuple[ExpectedStateDelta, ...]
    before_state: dict[str, Any]
    after_state: dict[str, Any] | None
    expected_status: VerificationStatus
    reason_contains: str | None = None
    timeout_seconds: float = 5.0


@dataclass(frozen=True)
class ActionVerifierEvalResult:
    case: ActionVerifierEvalCase
    verification: VerificationResult

    @property
    def passed(self) -> bool:
        if self.verification.status != self.case.expected_status:
            return False
        if self.case.reason_contains and self.case.reason_contains not in self.verification.reason:
            return False
        return True


def load_action_verifier_eval(path: Path) -> tuple[ActionVerifierEvalCase, ...]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return tuple(_parse_case(item) for item in raw.get("cases", []))


def run_action_verifier_eval(
    cases: tuple[ActionVerifierEvalCase, ...],
) -> tuple[ActionVerifierEvalResult, ...]:
    results: list[ActionVerifierEvalResult] = []
    for case in cases:
        verifier = VerifierBase(
            case.expected_deltas,
            timeout_seconds=case.timeout_seconds,
        )
        results.append(
            ActionVerifierEvalResult(
                case=case,
                verification=verifier.verify(case.before_state, case.after_state),
            )
        )
    return tuple(results)


def _parse_case(raw: dict[str, Any]) -> ActionVerifierEvalCase:
    return ActionVerifierEvalCase(
        case_id=str(raw["id"]),
        action_type=ActionType(str(raw["action_type"])),
        case_type=str(raw["case_type"]),
        expected_deltas=tuple(_parse_delta(item) for item in raw["expected_deltas"]),
        before_state=dict(raw.get("before_state") or {}),
        after_state=raw.get("after_state"),
        expected_status=VerificationStatus(str(raw["expected_status"])),
        reason_contains=raw.get("reason_contains"),
        timeout_seconds=float(raw.get("timeout_seconds", 5.0)),
    )


def _parse_delta(raw: dict[str, Any]) -> ExpectedStateDelta:
    return ExpectedStateDelta(
        path=str(raw["path"]),
        before=raw.get("before"),
        expected_after=raw.get("expected_after"),
    )
