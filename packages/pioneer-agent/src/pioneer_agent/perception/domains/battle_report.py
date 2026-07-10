"""Extract structured, non-authoritative battle-report observations."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pioneer_agent.core.models import FieldMeta

from ..vision import VisionClient
from ..vision.prompts import (
    BATTLE_REPORT_INSTRUCTION,
    BATTLE_REPORT_SCHEMA,
    BattleReportDetection,
    BattleReportHeroDetection,
)

SOURCE_LABEL = "vision.battle_report"


@dataclass
class BattleReportFragment:
    map_state: dict[str, Any] = field(default_factory=dict)
    field_meta: dict[str, FieldMeta] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    raw: BattleReportDetection | None = None


def extract_battle_report(
    image: bytes | Path,
    *,
    client: VisionClient | None = None,
    captured_at: datetime | None = None,
) -> BattleReportFragment:
    vision = client or VisionClient()
    result = vision.extract(
        image=image,
        instruction=BATTLE_REPORT_INSTRUCTION,
        response_schema=BATTLE_REPORT_SCHEMA,
    )
    parsed = BattleReportDetection.model_validate(result.data)
    return _build_fragment(parsed, captured_at=captured_at)


def _build_fragment(
    parsed: BattleReportDetection,
    *,
    captured_at: datetime | None,
) -> BattleReportFragment:
    if parsed.page_type != "battle":
        return BattleReportFragment(
            notes=list(parsed.visible_notes) + list(parsed.key_events),
            raw=parsed,
        )

    report = _report_dict(parsed, captured_at=captured_at)
    verification = _verification_summary(report)
    report["verification"] = verification

    return BattleReportFragment(
        map_state={
            "latest_battle_report": report,
            "battle_reports": [report],
            "battle_report_verification": verification,
        },
        field_meta={
            "map_state.latest_battle_report": FieldMeta(
                value="loaded",
                confidence=0.84,
                source=SOURCE_LABEL,
                updated_at=captured_at,
            ),
            "map_state.battle_report_verification": FieldMeta(
                value=verification["parse_status"],
                confidence=0.84,
                source=SOURCE_LABEL,
                updated_at=captured_at,
            ),
        },
        notes=list(parsed.visible_notes) + list(parsed.key_events),
        raw=parsed,
    )


def _report_dict(
    parsed: BattleReportDetection,
    *,
    captured_at: datetime | None,
) -> dict[str, Any]:
    attacker_losses = _resolve_losses(
        parsed.attacker_losses,
        parsed.attacker_initial_soldiers,
        parsed.attacker_remaining_soldiers,
    )
    defender_losses = _resolve_losses(
        parsed.defender_losses,
        parsed.defender_initial_soldiers,
        parsed.defender_remaining_soldiers,
    )
    attacker_heroes = [_hero_dict(hero) for hero in parsed.attacker_heroes]
    defender_heroes = [_hero_dict(hero) for hero in parsed.defender_heroes]
    measurement_issues = _measurement_issues(
        parsed,
        attacker_losses=attacker_losses,
        defender_losses=defender_losses,
        attacker_heroes=attacker_heroes,
        defender_heroes=defender_heroes,
    )

    report: dict[str, Any] = {
        "report_id": parsed.report_id or _synthetic_report_id(parsed),
        "report_id_source": "explicit" if parsed.report_id else "content_fingerprint",
        "report_identity_confidence": "high" if parsed.report_id else "low",
        "source": SOURCE_LABEL,
        "page_type": parsed.page_type,
        "result": parsed.result,
        "occupation_result": parsed.occupation_result,
        "resource_type": parsed.resource_type,
        "attacker_heroes": attacker_heroes,
        "defender_heroes": defender_heroes,
        "key_events": list(parsed.key_events),
        "visible_sections": list(parsed.visible_sections),
        "visible_notes": list(parsed.visible_notes),
    }
    _set_if_not_none(report, "report_time", parsed.report_time)
    if captured_at is not None:
        report["captured_at"] = captured_at.isoformat()
    if parsed.target_x is not None or parsed.target_y is not None:
        report["target_coordinate"] = _drop_none(
            {"x": parsed.target_x, "y": parsed.target_y}
        )
    _set_if_not_none(report, "land_level", parsed.land_level)
    _set_if_not_none(report, "attacker_team_id", parsed.attacker_team_id)
    _set_if_not_none(report, "attacker_name", parsed.attacker_name)
    _set_if_not_none(report, "defender_name", parsed.defender_name)
    _set_if_not_none(report, "attacker_initial_soldiers", parsed.attacker_initial_soldiers)
    _set_if_not_none(report, "attacker_remaining_soldiers", parsed.attacker_remaining_soldiers)
    _set_if_not_none(report, "attacker_losses", attacker_losses)
    _set_if_not_none(report, "defender_initial_soldiers", parsed.defender_initial_soldiers)
    _set_if_not_none(report, "defender_remaining_soldiers", parsed.defender_remaining_soldiers)
    _set_if_not_none(report, "defender_losses", defender_losses)
    _set_if_not_none(report, "rounds", parsed.rounds)
    _set_if_not_none(report, "experience_gained", parsed.experience_gained)
    _set_if_not_none(report, "honor_gained", parsed.honor_gained)
    if attacker_losses is not None and parsed.attacker_initial_soldiers:
        report["attacker_loss_ratio"] = round(
            attacker_losses / parsed.attacker_initial_soldiers,
            4,
        )
    if measurement_issues:
        report["measurement_issues"] = measurement_issues
    return _drop_none(report)


def _hero_dict(hero: BattleReportHeroDetection) -> dict[str, Any]:
    losses = _resolve_losses(hero.losses, hero.initial_soldiers, hero.remaining_soldiers)
    payload: dict[str, Any] = {
        "name": hero.name,
        "level": hero.level,
        "initial_soldiers": hero.initial_soldiers,
        "remaining_soldiers": hero.remaining_soldiers,
        "losses": losses,
        "tactics": list(hero.tactics),
        "visible_notes": list(hero.visible_notes),
    }
    if losses is not None and hero.initial_soldiers:
        payload["loss_ratio"] = round(losses / hero.initial_soldiers, 4)
    return _drop_none(payload)


def _resolve_losses(
    explicit_losses: int | None,
    initial_soldiers: int | None,
    remaining_soldiers: int | None,
) -> int | None:
    if _troop_measurement_conflict(
        explicit_losses,
        initial_soldiers,
        remaining_soldiers,
    ):
        return None
    if explicit_losses is not None:
        return explicit_losses
    if initial_soldiers is None or remaining_soldiers is None:
        return None
    return initial_soldiers - remaining_soldiers


def _troop_measurement_conflict(
    explicit_losses: int | None,
    initial_soldiers: int | None,
    remaining_soldiers: int | None,
) -> bool:
    values = (explicit_losses, initial_soldiers, remaining_soldiers)
    if any(value is not None and value < 0 for value in values):
        return True
    if initial_soldiers is None:
        return False
    if remaining_soldiers is not None and remaining_soldiers > initial_soldiers:
        return True
    if explicit_losses is not None and explicit_losses > initial_soldiers:
        return True
    return (
        explicit_losses is not None
        and remaining_soldiers is not None
        and explicit_losses != initial_soldiers - remaining_soldiers
    )


def _measurement_issues(
    parsed: BattleReportDetection,
    *,
    attacker_losses: int | None,
    defender_losses: int | None,
    attacker_heroes: list[dict[str, Any]],
    defender_heroes: list[dict[str, Any]],
) -> list[str]:
    issues: list[str] = []
    measurements = [
        (
            "attacker_total",
            parsed.attacker_losses,
            parsed.attacker_initial_soldiers,
            parsed.attacker_remaining_soldiers,
        ),
        (
            "defender_total",
            parsed.defender_losses,
            parsed.defender_initial_soldiers,
            parsed.defender_remaining_soldiers,
        ),
    ]
    measurements.extend(
        (
            f"attacker_hero_{index}",
            hero.losses,
            hero.initial_soldiers,
            hero.remaining_soldiers,
        )
        for index, hero in enumerate(parsed.attacker_heroes)
    )
    measurements.extend(
        (
            f"defender_hero_{index}",
            hero.losses,
            hero.initial_soldiers,
            hero.remaining_soldiers,
        )
        for index, hero in enumerate(parsed.defender_heroes)
    )
    for label, explicit, initial, remaining in measurements:
        if _troop_measurement_conflict(explicit, initial, remaining):
            issues.append(f"{label}_inconsistent")

    _append_aggregate_loss_issue(
        issues,
        label="attacker",
        total_loss=attacker_losses,
        heroes=attacker_heroes,
    )
    _append_aggregate_loss_issue(
        issues,
        label="defender",
        total_loss=defender_losses,
        heroes=defender_heroes,
    )
    return issues


def _append_aggregate_loss_issue(
    issues: list[str],
    *,
    label: str,
    total_loss: int | None,
    heroes: list[dict[str, Any]],
) -> None:
    if total_loss is None or not heroes:
        return
    hero_losses = [hero.get("losses") for hero in heroes]
    if any(not isinstance(loss, int) for loss in hero_losses):
        return
    if sum(hero_losses) != total_loss:
        issues.append(f"{label}_hero_loss_sum_mismatch")


def _verification_summary(report: dict[str, Any]) -> dict[str, Any]:
    measurement_issues = list(report.get("measurement_issues") or [])
    report_complete = _is_complete_report(report) and not measurement_issues
    checks = {
        "battle_result": "known" if report.get("result") != "unknown" else "unknown",
        "loss_measured": "measured" if _has_loss_measurement(report) else "unknown",
        "occupation": (
            "known"
            if report.get("occupation_result") not in {None, "unknown"}
            else "unknown"
        ),
        "loss_consistency": "inconsistent" if measurement_issues else "not_conflicted",
        "report_parse": "complete" if report_complete else "partial",
    }
    return {
        "parse_status": "complete" if report_complete else "partial",
        "checks": checks,
        "issues": measurement_issues,
        # A parsed screenshot is not an action verifier. Correlation against the
        # dispatched action, target, team, and observation window is still absent.
        "action_verification_ready": False,
        "verifier_status": "unverified",
    }


def _has_loss_measurement(report: dict[str, Any]) -> bool:
    if report.get("attacker_losses") is not None:
        return True
    return any(
        hero.get("losses") is not None
        for hero in report.get("attacker_heroes", [])
        if isinstance(hero, dict)
    )


def _is_complete_report(report: dict[str, Any]) -> bool:
    has_result = report.get("result") != "unknown"
    has_occupation = report.get("occupation_result") not in {None, "unknown"}
    has_loss = _has_loss_measurement(report)
    has_context = bool(report.get("target_coordinate")) or report.get("land_level") is not None
    has_sides = bool(report.get("attacker_heroes")) and bool(report.get("defender_heroes"))
    return has_result and has_occupation and has_loss and has_context and has_sides


def _synthetic_report_id(parsed: BattleReportDetection) -> str:
    signature = {
        "report_time": parsed.report_time,
        "result": parsed.result,
        "occupation_result": parsed.occupation_result,
        "target_x": parsed.target_x,
        "target_y": parsed.target_y,
        "land_level": parsed.land_level,
        "resource_type": parsed.resource_type,
        "attacker_team_id": parsed.attacker_team_id,
        "attacker_losses": parsed.attacker_losses,
        "defender_losses": parsed.defender_losses,
        "attacker_heroes": [hero.model_dump(exclude_none=True) for hero in parsed.attacker_heroes],
        "defender_heroes": [hero.model_dump(exclude_none=True) for hero in parsed.defender_heroes],
    }
    payload = json.dumps(signature, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
    return f"vision-{digest}"


def _set_if_not_none(payload: dict[str, Any], key: str, value: Any) -> None:
    if value is not None:
        payload[key] = value


def _drop_none(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}
