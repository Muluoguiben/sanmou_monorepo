from __future__ import annotations

import math
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
    BECOMES_PRESENT = "becomes_present"
    INCREASES_TO = "increases_to"


class DeltaMatchPolicy(str, Enum):
    ALL = "all"
    ANY = "any"


@dataclass(frozen=True)
class ExpectedStateDelta:
    path: str
    expected_after: Any = None
    before: Any = None
    operator: DeltaOperator | str = DeltaOperator.EQUALS
    collection_path: str | None = None
    identity_field: str | None = None
    identity_value: Any = None
    identity_param: str | None = None
    before_param: str | None = None
    expected_after_param: str | None = None


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

        preflight = self.validate_before(before_state)
        if not preflight.verified:
            return preflight

        if self.match_policy == DeltaMatchPolicy.ALL:
            checked: list[str] = []
            for delta in self.expected_deltas:
                checked.append(_delta_label(delta))
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
            checked.append(_delta_label(delta))
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

    def validate_before(
        self,
        before_state: Mapping[str, Any] | None,
    ) -> VerificationResult:
        if not self.expected_deltas:
            return VerificationResult(
                status=VerificationStatus.UNKNOWN,
                reason="no expected state delta was provided",
                timeout_seconds=self.timeout_seconds,
            )
        if before_state is None:
            return VerificationResult(
                status=VerificationStatus.UNKNOWN,
                reason="no pre-action state was provided",
                timeout_seconds=self.timeout_seconds,
            )

        checked: list[str] = []
        before_required_operators = {
            DeltaOperator.GREATER_THAN_BEFORE,
            DeltaOperator.LESS_THAN_BEFORE,
            DeltaOperator.INCREASES_TO,
        }
        for delta in self.expected_deltas:
            checked.append(_delta_label(delta))
            for param_name in (
                delta.identity_param,
                delta.before_param,
                delta.expected_after_param,
            ):
                if param_name is not None:
                    return VerificationResult(
                        status=VerificationStatus.FAILED,
                        reason=f"unbound action parameter in verifier delta: {param_name}",
                        checked=tuple(checked),
                        timeout_seconds=self.timeout_seconds,
                    )
            scope, found, value, reason = _resolve_delta_value(
                before_state,
                delta,
                phase="before",
            )
            if not scope:
                return VerificationResult(
                    status=VerificationStatus.FAILED,
                    reason=reason,
                    checked=tuple(checked),
                    timeout_seconds=self.timeout_seconds,
                )
            operator = _coerce_operator(delta.operator)
            requires_value = (
                delta.before is not None
                or operator in before_required_operators
            )
            if requires_value and not found:
                return VerificationResult(
                    status=VerificationStatus.FAILED,
                    reason=reason,
                    checked=tuple(checked),
                    timeout_seconds=self.timeout_seconds,
                )
            if delta.before is not None and not _strict_equal(value, delta.before):
                return VerificationResult(
                    status=VerificationStatus.FAILED,
                    reason=(
                        f"expected previous {_delta_label(delta)} to be "
                        f"{delta.before!r}, got {value!r}"
                    ),
                    checked=tuple(checked),
                    timeout_seconds=self.timeout_seconds,
                )
            if (
                operator == DeltaOperator.BECOMES_PRESENT
                and found
                and value not in (None, "", [], {})
            ):
                return VerificationResult(
                    status=VerificationStatus.FAILED,
                    reason=(
                        f"expected previous {_delta_label(delta)} to be "
                        "absent or empty before dispatch"
                    ),
                    checked=tuple(checked),
                    timeout_seconds=self.timeout_seconds,
                )
            if operator == DeltaOperator.INCREASES_TO:
                if delta.expected_after is None:
                    return VerificationResult(
                        status=VerificationStatus.FAILED,
                        reason=(
                            f"expected target value for {_delta_label(delta)} "
                            "before dispatch"
                        ),
                        checked=tuple(checked),
                        timeout_seconds=self.timeout_seconds,
                    )
                increases = (
                    _is_finite_number(value)
                    and _is_finite_number(delta.expected_after)
                    and value < delta.expected_after
                )
                if not increases:
                    return VerificationResult(
                        status=VerificationStatus.FAILED,
                        reason=(
                            f"expected {_delta_label(delta)} baseline {value!r} "
                            f"to be below target {delta.expected_after!r} before dispatch"
                        ),
                        checked=tuple(checked),
                        timeout_seconds=self.timeout_seconds,
                    )

        return VerificationResult(
            status=VerificationStatus.VERIFIED,
            reason="pre-action verifier target is uniquely bound",
            checked=tuple(checked),
            timeout_seconds=self.timeout_seconds,
        )


def _match_delta(
    delta: ExpectedStateDelta,
    before_state: Mapping[str, Any] | None,
    after_state: Mapping[str, Any],
) -> tuple[bool, str]:
    for param_name in (
        delta.identity_param,
        delta.before_param,
        delta.expected_after_param,
    ):
        if param_name is not None:
            return False, f"unbound action parameter in verifier delta: {param_name}"

    operator = _coerce_operator(delta.operator)
    after_scope, after_found, after_value, after_reason = _resolve_delta_value(
        after_state,
        delta,
        phase="after",
    )

    if operator == DeltaOperator.ABSENT:
        if not after_scope:
            return False, after_reason
        if after_found:
            return False, f"expected {_delta_label(delta)} to be absent after action, got {after_value!r}"
        return True, "matched"

    if not after_scope or not after_found:
        return False, after_reason

    before_scope = False
    before_found = False
    before_value: Any = None
    before_reason = "no pre-action state was provided"
    if before_state is not None:
        before_scope, before_found, before_value, before_reason = _resolve_delta_value(
            before_state,
            delta,
            phase="before",
        )

    if delta.before is not None:
        if not before_scope or not before_found:
            return False, before_reason
        if not _strict_equal(before_value, delta.before):
            return (
                False,
                f"expected previous {_delta_label(delta)} to be {delta.before!r}, got {before_value!r}",
            )

    if operator == DeltaOperator.EQUALS:
        if not _strict_equal(after_value, delta.expected_after):
            return (
                False,
                f"expected {_delta_label(delta)} to be {delta.expected_after!r}, got {after_value!r}",
            )
        return True, "matched"

    if operator == DeltaOperator.PRESENT:
        if after_value in (None, "", [], {}):
            return False, f"expected {_delta_label(delta)} to be present after action"
        return True, "matched"

    if operator == DeltaOperator.GREATER_THAN_BEFORE:
        if not before_scope or not before_found:
            return False, before_reason
        if not (
            _is_finite_number(after_value)
            and _is_finite_number(before_value)
        ):
            return False, f"expected comparable values for {_delta_label(delta)}"
        if after_value > before_value:
            return True, "matched"
        return False, f"expected {_delta_label(delta)} to increase from {before_value!r}, got {after_value!r}"

    if operator == DeltaOperator.LESS_THAN_BEFORE:
        if not before_scope or not before_found:
            return False, before_reason
        if not (
            _is_finite_number(after_value)
            and _is_finite_number(before_value)
        ):
            return False, f"expected comparable values for {_delta_label(delta)}"
        if after_value < before_value:
            return True, "matched"
        return False, f"expected {_delta_label(delta)} to decrease from {before_value!r}, got {after_value!r}"

    if operator == DeltaOperator.BECOMES_PRESENT:
        if before_state is None or not before_scope:
            return False, before_reason
        if after_value in (None, "", [], {}):
            return False, f"expected {_delta_label(delta)} to become present"
        if before_found and before_value not in (None, "", [], {}):
            return False, f"expected previous {_delta_label(delta)} to be absent or empty"
        return True, "matched"

    if operator == DeltaOperator.INCREASES_TO:
        if not before_scope or not before_found:
            return False, before_reason
        if delta.expected_after is None:
            return False, f"missing target value for {_delta_label(delta)}"
        if not all(
            _is_finite_number(value)
            for value in (before_value, after_value, delta.expected_after)
        ):
            return False, f"expected comparable values for {_delta_label(delta)}"
        increased = after_value > before_value
        if not increased:
            return (
                False,
                f"expected {_delta_label(delta)} to increase from "
                f"{before_value!r}, got {after_value!r}",
            )
        if not _strict_equal(after_value, delta.expected_after):
            return (
                False,
                f"expected {_delta_label(delta)} to reach "
                f"{delta.expected_after!r}, got {after_value!r}",
            )
        return True, "matched"

    return False, f"unsupported delta operator: {operator.value}"


def _strict_equal(left: Any, right: Any) -> bool:
    """Keep Python's bool/int equivalence from satisfying state deltas."""
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    return left == right


def _is_finite_number(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return not isinstance(value, float) or math.isfinite(value)


def _resolve_delta_value(
    state: Mapping[str, Any],
    delta: ExpectedStateDelta,
    *,
    phase: str,
) -> tuple[bool, bool, Any, str]:
    if delta.collection_path is None:
        found, value = _get_path(state, delta.path)
        reason = f"missing expected path {phase} action: {delta.path}"
        return True, found, value, reason

    if not delta.identity_field or delta.identity_value is None:
        return False, False, None, "entity selector is incomplete"
    collection_found, collection = _get_path(state, delta.collection_path)
    if not collection_found or not _is_sequence(collection):
        return (
            False,
            False,
            None,
            f"missing entity collection {phase} action: {delta.collection_path}",
        )
    matches = [
        item
        for item in collection
        if isinstance(item, Mapping)
        and item.get(delta.identity_field) == delta.identity_value
    ]
    if len(matches) != 1:
        return (
            False,
            False,
            None,
            f"expected exactly one {delta.collection_path} entity with "
            f"{delta.identity_field}={delta.identity_value!r} {phase} action, got {len(matches)}",
        )
    found, value = _get_path(matches[0], delta.path)
    return (
        True,
        found,
        value,
        f"missing target field {phase} action: {_delta_label(delta)}",
    )


def _delta_label(delta: ExpectedStateDelta) -> str:
    if delta.collection_path is None:
        return delta.path
    return (
        f"{delta.collection_path}[{delta.identity_field}="
        f"{delta.identity_value!r}].{delta.path}"
    )


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
