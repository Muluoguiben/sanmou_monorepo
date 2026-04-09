from __future__ import annotations

from typing import Any


def score_wait_for_resource(wait_action: dict[str, Any]) -> tuple[float, dict[str, float]]:
    unlock_value = float(wait_action.get("unlock_score_hint", 0)) * 0.85
    chapter_bonus = 18.0 if wait_action.get("chapter_relevance") == "complete_current_task" else 10.0
    short_wait_bonus = 10.0 if int(wait_action.get("wait_seconds", 0) or 0) <= 900 else 0.0
    delay_penalty = int(wait_action.get("wait_seconds", 0) or 0) / 180
    shortage_penalty = float(wait_action.get("missing_amount", 0)) / 1200

    breakdown = {
        "unlock_value": round(unlock_value, 2),
        "chapter_bonus": chapter_bonus,
        "short_wait_bonus": short_wait_bonus,
        "delay_penalty": round(-delay_penalty, 2),
        "shortage_penalty": round(-shortage_penalty, 2),
    }
    return round(sum(breakdown.values()), 2), breakdown


def score_wait_for_stamina(wait_action: dict[str, Any]) -> tuple[float, dict[str, float]]:
    unlock_value = float(wait_action.get("unlock_score_hint", 0)) * 0.8
    chapter_bonus = 16.0 if wait_action.get("unlock_chapter_relevance") in {"advance_current_task", "complete_current_task"} else 6.0
    short_wait_bonus = 8.0 if int(wait_action.get("wait_seconds", 0) or 0) <= 1200 else 0.0
    delay_penalty = int(wait_action.get("wait_seconds", 0) or 0) / 100
    gap_penalty = float(wait_action.get("stamina_gap", 0)) * 2

    breakdown = {
        "unlock_value": round(unlock_value, 2),
        "chapter_bonus": chapter_bonus,
        "short_wait_bonus": short_wait_bonus,
        "delay_penalty": round(-delay_penalty, 2),
        "gap_penalty": round(-gap_penalty, 2),
    }
    return round(sum(breakdown.values()), 2), breakdown
