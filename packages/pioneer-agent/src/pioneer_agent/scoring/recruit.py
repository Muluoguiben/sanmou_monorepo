from __future__ import annotations

from typing import Any


def score_recruit_soldiers(team: dict[str, Any]) -> tuple[float, dict[str, float]]:
    recruit_amount = float(team.get("recruit_amount", 0))
    deficit = float(team.get("soldier_deficit", 0))
    reserve_troops = max(float(team.get("reserve_troops_available", 0)), 1.0)

    soldier_recovery = recruit_amount / 180
    readiness_gain = 28.0 if team.get("primary_constraint") == "soldiers" else 14.0
    host_bonus = 24.0 if team.get("is_main_host") else 8.0
    urgency_bonus = 12.0 if deficit / max(float(team.get("max_soldiers", 1)), 1.0) >= 0.25 else 4.0
    reserve_penalty = recruit_amount / reserve_troops * 10

    breakdown = {
        "soldier_recovery": round(soldier_recovery, 2),
        "readiness_gain": readiness_gain,
        "host_bonus": host_bonus,
        "urgency_bonus": urgency_bonus,
        "reserve_penalty": round(-reserve_penalty, 2),
    }
    return round(sum(breakdown.values()), 2), breakdown
