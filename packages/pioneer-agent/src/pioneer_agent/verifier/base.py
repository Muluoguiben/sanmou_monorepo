from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    FAILED = "failed"
    UNKNOWN = "unknown"


class DeltaOperator(str, Enum):
    EQUALS = "equals"
    PRESENT = "present"
    ABSENT = "absent"
    GREATER_THAN_BEFORE = "greater_than_before"
    LESS_THAN_BEFORE = "less_than_before"


class DeltaMatchPolicy(str, Enum):
    ALL = "all"
    ANY = "any"


@dataclass(frozen=True)
class ExpectedStateDelta:
    path: str
    expected_after: Any = None
    before: Any = None
    operator: DeltaOperator | str = DeltaOperator.EQUALS


@dataclass(frozen=True)
class VerificationResult:
    status: VerificationStatus
    reason: str
    checked: tuple[str, ...] = ()
    timeout_seconds: float | None = None

    @property
    def verified(self) -> bool:
        return self.status == VerificationStatus.VERIFIED


@dataclass(frozen=True)
class VerifierBase:
    expected_deltas: tuple[ExpectedStateDelta, ...] = field(default_factory=tuple)
    timeout_seconds: float = 5.0
    match_policy: DeltaMatchPolicy | str = DeltaMatchPolicy.ALL

    def __init__(
        self,
        expected_deltas: Sequence[ExpectedStateDelta] | None = None,
        *,
        timeout_seconds: float = 5.0,
        match_policy: DeltaMatchPolicy | str = DeltaMatchPolicy.ALL,
    ) -> None:
        object.__setattr__(self, "expected_deltas", tuple(expected_deltas or ()))
        object.__setattr__(self, "timeout_seconds", timeout_seconds)
        object.__setattr__(self, "match_policy", _coerce_match_policy(match_policy))

    def verify(
        self,
        before_state: Mapping[str, Any] | None,
        after_state: Mapping[str, Any] | None,
    ) -> VerificationResult:
        if not self.expected_deltas:
            return VerificationResult(
                status=VerificationStatus.UNKNOWN,
                reason="no expected state delta was provided",
                timeout_seconds=self.timeout_seconds,
            )
        if after_state is None:
            return VerificationResult(
                status=VerificationStatus.UNKNOWN,
                reason="no post-action state was provided",
                timeout_seconds=self.timeout_seconds,
            )

        if self.match_policy == DeltaMatchPolicy.ALL:
            checked: list[str] = []
            for delta in self.expected_deltas:
                checked.append(delta.path)
                matched, reason = _match_delta(delta, before_state, after_state)
                if not matched:
                    return VerificationResult(
                        status=VerificationStatus.FAILED,
                        reason=reason,
                        checked=tuple(checked),
                        timeout_seconds=self.timeout_seconds,
                    )

            return VerificationResult(
                status=VerificationStatus.VERIFIED,
                reason="all expected state deltas matched",
                checked=tuple(checked),
                timeout_seconds=self.timeout_seconds,
            )

        checked = []
        failures: list[str] = []
        for delta in self.expected_deltas:
            checked.append(delta.path)
            matched, reason = _match_delta(delta, before_state, after_state)
            if matched:
                return VerificationResult(
                    status=VerificationStatus.VERIFIED,
                    reason="at least one expected state delta matched",
                    checked=tuple(checked),
                    timeout_seconds=self.timeout_seconds,
                )
            failures.append(reason)

        return VerificationResult(
            status=VerificationStatus.FAILED,
            reason="no expected state delta matched: " + "; ".join(failures),
            checked=tuple(checked),
            timeout_seconds=self.timeout_seconds,
        )


def _match_delta(
    delta: ExpectedStateDelta,
    before_state: Mapping[str, Any] | None,
    after_state: Mapping[str, Any],
) -> tuple[bool, str]:
    operator = _coerce_operator(delta.operator)
    after_found, after_value = _get_path(after_state, delta.path)

    if operator == DeltaOperator.ABSENT:
        if after_found:
            return False, f"expected {delta.path} to be absent after action, got {after_value!r}"
        return True, "matched"

    if not after_found:
        return False, f"missing expected path after action: {delta.path}"

    before_found = False
    before_value: Any = None
    if before_state is not None:
        before_found, before_value = _get_path(before_state, delta.path)

    if delta.before is not None and before_found and before_value != delta.before:
        return (
            False,
            f"expected previous {delta.path} to be {delta.before!r}, got {before_value!r}",
        )

    if operator == DeltaOperator.EQUALS:
        if after_value != delta.expected_after:
            return (
                False,
                f"expected {delta.path} to be {delta.expected_after!r}, got {after_value!r}",
            )
        return True, "matched"

    if operator == DeltaOperator.PRESENT:
        if after_value in (None, "", [], {}):
            return False, f"expected {delta.path} to be present after action"
        return True, "matched"

    if operator == DeltaOperator.GREATER_THAN_BEFORE:
        if not before_found:
            return False, f"missing previous path before action: {delta.path}"
        try:
            if after_value > before_value:
                return True, "matched"
        except TypeError:
            return False, f"expected comparable values for {delta.path}"
        return False, f"expected {delta.path} to increase from {before_value!r}, got {after_value!r}"

    if operator == DeltaOperator.LESS_THAN_BEFORE:
        if not before_found:
            return False, f"missing previous path before action: {delta.path}"
        try:
            if after_value < before_value:
                return True, "matched"
        except TypeError:
            return False, f"expected comparable values for {delta.path}"
        return False, f"expected {delta.path} to decrease from {before_value!r}, got {after_value!r}"

    return False, f"unsupported delta operator: {operator.value}"


def _get_path(state: Mapping[str, Any], path: str) -> tuple[bool, Any]:
    current: Any = state
    for part in path.split("."):
        if isinstance(current, Mapping):
            if part not in current:
                return False, None
            current = current[part]
            continue
        if _is_sequence(current) and part.isdigit():
            index = int(part)
            if index >= len(current):
                return False, None
            current = current[index]
            continue
        return False, None
    return True, current


def _coerce_match_policy(value: DeltaMatchPolicy | str) -> DeltaMatchPolicy:
    if isinstance(value, DeltaMatchPolicy):
        return value
    return DeltaMatchPolicy(str(value))


def _coerce_operator(value: DeltaOperator | str) -> DeltaOperator:
    if isinstance(value, DeltaOperator):
        return value
    return DeltaOperator(str(value))


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
