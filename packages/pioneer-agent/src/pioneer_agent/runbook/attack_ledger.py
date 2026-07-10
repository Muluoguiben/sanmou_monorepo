"""Read-only battle-report aggregation for opening Runbook metrics.

The ledger consumes perception history already present in ``RuntimeState``. It
does not record dispatches, mutate state, or claim that a content fingerprint
identifies an attack. When timestamps cannot be compared safely, risk metrics
use conservative bounds while verified progress remains fail-closed.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping

from pioneer_agent.core.models import RuntimeState

_RESULTS = frozenset({"win", "draw", "loss", "unknown"})
_OCCUPATION_RESULTS = frozenset(
    {"occupied", "not_occupied", "already_owned", "failed", "unknown"}
)
ATTACK_LEDGER_METRIC_KEYS = frozenset(
    {"battle_loss_rate", "consecutive_defeats", "highest_land_level_cleared"}
)
_RESULT_RISK_ORDER = {"win": 0, "draw": 1, "unknown": 2, "loss": 3}
_OCCUPATION_RISK_ORDER = {
    "occupied": 0,
    "already_owned": 1,
    "unknown": 2,
    "not_occupied": 3,
    "failed": 4,
}


@dataclass(frozen=True, slots=True)
class AttackReport:
    report_id: str
    captured_at: datetime
    result: str
    occupation_result: str
    attacker_loss_ratio: float | None
    land_level: int | None
    precise_identity: bool
    action_verified: bool
    time_ambiguous: bool = False


@dataclass(frozen=True, slots=True)
class AttackLedger:
    """A normalized, de-duplicated view over observed battle reports."""

    reports: tuple[AttackReport, ...] = ()
    ordering_trusted: bool = True
    skipped_reports: int = 0
    ambiguous_report_ids: tuple[str, ...] = ()

    @classmethod
    def from_runtime_state(cls, state: RuntimeState) -> "AttackLedger":
        raw_reports = _reports_from_state(state)
        by_id: dict[str, AttackReport] = {}
        ambiguous_ids: set[str] = set()
        skipped = 0

        for raw in raw_reports:
            report = _normalize_report(raw)
            if report is None:
                skipped += 1
                continue
            if report.report_id in ambiguous_ids:
                by_id[report.report_id] = _merge_incomparable_reports(
                    by_id[report.report_id], report
                )
                continue

            existing = by_id.get(report.report_id)
            if existing is None:
                by_id[report.report_id] = report
                continue

            comparison = _compare_datetimes(report.captured_at, existing.captured_at)
            if comparison is None:
                ambiguous_ids.add(report.report_id)
                by_id[report.report_id] = _merge_incomparable_reports(
                    existing, report
                )
                continue
            if comparison >= 0:
                by_id[report.report_id] = report

        reports = list(by_id.values())
        awareness = {_is_aware(report.captured_at) for report in reports}
        ordering_trusted = not ambiguous_ids and len(awareness) <= 1
        if ordering_trusted:
            reports.sort(key=lambda report: _sortable_datetime(report.captured_at))
        else:
            # Deterministic presentation only; risk metrics use conservative
            # bounds instead of treating this as a chronological sequence.
            reports.sort(
                key=lambda report: (
                    _is_aware(report.captured_at),
                    report.captured_at.isoformat(),
                    report.report_id,
                )
            )

        return cls(
            reports=tuple(reports),
            ordering_trusted=ordering_trusted,
            skipped_reports=skipped,
            ambiguous_report_ids=tuple(sorted(ambiguous_ids)),
        )

    def runbook_metrics(self) -> dict[str, int | float]:
        metrics: dict[str, int | float] = {}

        if self.reports:
            if self.ordering_trusted:
                latest = self.reports[-1]
                if latest.attacker_loss_ratio is not None:
                    metrics["battle_loss_rate"] = latest.attacker_loss_ratio

                consecutive = _consecutive_defeats(self.reports)
                if consecutive is not None:
                    metrics["consecutive_defeats"] = consecutive
            else:
                # With no trustworthy chronology, use risk-conservative bounds:
                # the highest observed loss and every precise loss as if they
                # could form one consecutive tail. This may stop early, but can
                # never manufacture safe progress from ambiguous ordering.
                observed_losses = [
                    report.attacker_loss_ratio
                    for report in self.reports
                    if report.attacker_loss_ratio is not None
                ]
                if observed_losses:
                    metrics["battle_loss_rate"] = max(observed_losses)
                defeat_upper_bound = sum(
                    1
                    for report in self.reports
                    if report.precise_identity and report.result == "loss"
                )
                if defeat_upper_bound:
                    metrics["consecutive_defeats"] = defeat_upper_bound

        verified_levels = [
            report.land_level
            for report in self.reports
            if report.precise_identity
            and report.action_verified
            and report.result == "win"
            and report.occupation_result == "occupied"
            and report.land_level is not None
        ]
        if verified_levels:
            metrics["highest_land_level_cleared"] = max(verified_levels)

        return metrics


def attack_metrics_from_runtime_state(state: RuntimeState) -> dict[str, int | float]:
    return AttackLedger.from_runtime_state(state).runbook_metrics()


def _reports_from_state(state: RuntimeState) -> list[Any]:
    reports: list[Any] = []
    history = state.map_state.get("battle_reports")
    if isinstance(history, list):
        reports.extend(history)
    latest = state.map_state.get("latest_battle_report")
    if isinstance(latest, Mapping):
        reports.append(latest)
    return reports


def _normalize_report(raw: Any) -> AttackReport | None:
    if not isinstance(raw, Mapping):
        return None

    report_id = raw.get("report_id")
    if not isinstance(report_id, str) or not report_id.strip():
        return None
    captured_at = _parse_datetime(raw.get("captured_at"))
    if captured_at is None:
        return None

    result = raw.get("result")
    occupation = raw.get("occupation_result")
    if result not in _RESULTS or occupation not in _OCCUPATION_RESULTS:
        return None

    verification = raw.get("verification")
    verification = verification if isinstance(verification, Mapping) else {}
    checks = verification.get("checks")
    checks = checks if isinstance(checks, Mapping) else {}
    measurement_issues = raw.get("measurement_issues")
    loss_conflicted = (
        bool(measurement_issues)
        or checks.get("loss_consistency") == "inconsistent"
    )

    identity_source = raw.get("report_id_source")
    identity_confidence = raw.get("report_identity_confidence")
    precise_identity = (
        identity_source == "explicit" and identity_confidence == "high"
    )
    action_verified = (
        verification.get("action_verification_ready") is True
        and verification.get("verifier_status") == "verified"
        and verification.get("parse_status") == "complete"
        and not loss_conflicted
    )

    return AttackReport(
        report_id=report_id.strip(),
        captured_at=captured_at,
        result=str(result),
        occupation_result=str(occupation),
        attacker_loss_ratio=(None if loss_conflicted else _loss_ratio(raw)),
        land_level=_land_level(raw.get("land_level")),
        precise_identity=precise_identity,
        action_verified=action_verified,
    )


def _merge_incomparable_reports(
    left: AttackReport,
    right: AttackReport,
) -> AttackReport:
    """Conservatively collapse one ambiguous report identity into one attempt."""
    chosen_time = min(
        (left.captured_at, right.captured_at),
        key=lambda value: (_is_aware(value), value.isoformat()),
    )
    ratios = [
        ratio
        for ratio in (left.attacker_loss_ratio, right.attacker_loss_ratio)
        if ratio is not None
    ]
    levels = [level for level in (left.land_level, right.land_level) if level is not None]
    return AttackReport(
        report_id=left.report_id,
        captured_at=chosen_time,
        result=max((left.result, right.result), key=_RESULT_RISK_ORDER.__getitem__),
        occupation_result=max(
            (left.occupation_result, right.occupation_result),
            key=_OCCUPATION_RISK_ORDER.__getitem__,
        ),
        attacker_loss_ratio=max(ratios) if ratios else None,
        land_level=max(levels) if levels else None,
        precise_identity=left.precise_identity and right.precise_identity,
        # An action verifier cannot establish temporal correlation when the two
        # observations for the same identity cannot be ordered.
        action_verified=False,
        time_ambiguous=True,
    )


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _compare_datetimes(left: datetime, right: datetime) -> int | None:
    if _is_aware(left) != _is_aware(right):
        return None
    left_value = _sortable_datetime(left)
    right_value = _sortable_datetime(right)
    if left_value < right_value:
        return -1
    if left_value > right_value:
        return 1
    return 0


def _sortable_datetime(value: datetime) -> datetime:
    return value.astimezone(UTC) if _is_aware(value) else value


def _is_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _loss_ratio(report: Mapping[str, Any]) -> float | None:
    ratio_value = report.get("attacker_loss_ratio")
    ratio_present = ratio_value is not None
    ratio = _number(ratio_value)
    losses_value = report.get("attacker_losses")
    initial_value = report.get("attacker_initial_soldiers")
    counts_present = losses_value is not None or initial_value is not None
    losses = _number(losses_value)
    initial = _number(initial_value)

    if ratio_present:
        if ratio is None or not 0.0 <= ratio <= 1.0:
            return None
        if counts_present:
            if losses is None or initial is None:
                return None
            if initial <= 0 or losses < 0 or losses > initial:
                return None
            derived = losses / initial
            if not math.isclose(ratio, derived, rel_tol=0.0, abs_tol=0.0001):
                return None
        return round(ratio, 4)

    if losses is None or initial is None or initial <= 0 or losses < 0 or losses > initial:
        return None
    return round(losses / initial, 4)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _land_level(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 1 <= value <= 12 else None


def _consecutive_defeats(reports: tuple[AttackReport, ...]) -> int | None:
    latest = reports[-1]
    if latest.result == "unknown" or not latest.precise_identity:
        return None

    count = 0
    for report in reversed(reports):
        if not report.precise_identity or report.result == "unknown":
            # Exact identity is required to extend the streak, but confirmed
            # recent explicit losses remain a safe lower bound for >= aborts.
            return count
        if report.result == "loss":
            count += 1
            continue
        return count
    return count
