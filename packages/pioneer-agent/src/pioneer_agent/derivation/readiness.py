from __future__ import annotations

from typing import Any


def compute_combat_readiness(container: dict[str, Any], lineup: dict[str, Any]) -> dict[str, Any]:
    stamina = float(container.get("container_stamina", 0))
    soldiers = float(container.get("soldiers", 0))
    avg_level = float(lineup.get("avg_level", 0))

    level_score = min(avg_level * 4, 100)
    soldier_score = min(soldiers / 200, 100) if soldiers else 0
    stamina_score = min(stamina * 5, 100)
    position_score = 90 if container.get("position_context") == "outer" else 60
    stability_score = 90 if container.get("status") in {"idle", "ready"} else 50

    score = (level_score + soldier_score + stamina_score + position_score + stability_score) / 5
    weakest = min(
        [
            ("level", level_score),
            ("soldiers", soldier_score),
            ("stamina", stamina_score),
            ("position", position_score),
            ("stability", stability_score),
        ],
        key=lambda item: item[1],
    )[0]

    return {
        "level_readiness": round(level_score, 2),
        "soldier_readiness": round(soldier_score, 2),
        "stamina_readiness": round(stamina_score, 2),
        "position_readiness": round(position_score, 2),
        "stability_readiness": round(stability_score, 2),
        "combat_readiness_score": round(score, 2),
        "primary_constraint": weakest,
    }

