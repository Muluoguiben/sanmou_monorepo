from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ExpectedStateDelta:
    path: str
    expected_after: Any
    before: Any = None


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

    def __init__(
        self,
        expected_deltas: Sequence[ExpectedStateDelta] | None = None,
        *,
        timeout_seconds: float = 5.0,
    ) -> None:
        object.__setattr__(self, "expected_deltas", tuple(expected_deltas or ()))
        object.__setattr__(self, "timeout_seconds", timeout_seconds)

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

        checked: list[str] = []
        for delta in self.expected_deltas:
            checked.append(delta.path)
            after_found, after_value = _get_path(after_state, delta.path)
            if not after_found:
                return VerificationResult(
                    status=VerificationStatus.FAILED,
                    reason=f"missing expected path after action: {delta.path}",
                    checked=tuple(checked),
                    timeout_seconds=self.timeout_seconds,
                )
            if after_value != delta.expected_after:
                return VerificationResult(
                    status=VerificationStatus.FAILED,
                    reason=(
                        f"expected {delta.path} to be {delta.expected_after!r}, "
                        f"got {after_value!r}"
                    ),
                    checked=tuple(checked),
                    timeout_seconds=self.timeout_seconds,
                )
            if delta.before is not None and before_state is not None:
                before_found, before_value = _get_path(before_state, delta.path)
                if before_found and before_value != delta.before:
                    return VerificationResult(
                        status=VerificationStatus.FAILED,
                        reason=(
                            f"expected previous {delta.path} to be {delta.before!r}, "
                            f"got {before_value!r}"
                        ),
                        checked=tuple(checked),
                        timeout_seconds=self.timeout_seconds,
                    )

        return VerificationResult(
            status=VerificationStatus.VERIFIED,
            reason="all expected state deltas matched",
            checked=tuple(checked),
            timeout_seconds=self.timeout_seconds,
        )


def _get_path(state: Mapping[str, Any], path: str) -> tuple[bool, Any]:
    current: Any = state
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return False, None
        current = current[part]
    return True, current
