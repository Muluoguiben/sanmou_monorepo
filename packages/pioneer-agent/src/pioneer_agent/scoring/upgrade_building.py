from __future__ import annotations

from typing import Any


def score_upgrade_building(building: dict[str, Any]) -> tuple[float, dict[str, float]]:
    chapter_gain = 45.0 if building.get("chapter_relevance") == "complete_current_task" else 20.0 if building.get("chapter_relevance") == "prepare_next_chapter" else 8.0
    economy_gain = float(building.get("economy_gain", 0))
    battle_gain = float(building.get("battle_support_gain", 0))
    tempo_gain = 10.0 if building.get("chapter_relevance") == "complete_current_task" else 4.0
    resource_penalty = float(building.get("resource_cost_penalty", 0))
    breakdown = {
        "chapter_gain": chapter_gain,
        "economy_gain": economy_gain,
        "battle_gain": battle_gain,
        "tempo_gain": tempo_gain,
        "resource_penalty": -resource_penalty,
    }
    return round(sum(breakdown.values()), 2), {key: round(value, 2) for key, value in breakdown.items()}


def is_upgrade_candidate_valid(building: dict[str, Any]) -> bool:
    return bool(building.get("building_id")) and not building.get("blocked_by")
