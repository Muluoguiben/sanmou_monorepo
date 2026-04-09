from __future__ import annotations

from typing import Any


def score_attack_land(land: dict[str, Any]) -> tuple[float, dict[str, float]]:
    yield_score = float(land.get("yield_per_hour", 0)) / 10
    chapter_gain = 30.0 if land.get("chapter_relevance") in {"advance_current_task", "complete_current_task"} else 10.0
    strategic_gain = float(len(land.get("strategic_tags", [])) * 5)
    tempo_gain = 12.0 if land.get("level_fit") == "safe" else 4.0 if land.get("level_fit") == "edge" else -18.0
    loss_penalty = float(land.get("expected_battle_loss", 0)) / 100
    march_penalty = float(land.get("march_seconds", 0)) / 10
    stamina_penalty = max(float(land.get("required_stamina", 0)) - float(land.get("current_stamina", 0)), 0) * 2
    risk_penalty = (1 - float(land.get("expected_win_rate", 1.0))) * 100

    breakdown = {
        "yield": yield_score,
        "chapter": chapter_gain,
        "strategic": strategic_gain,
        "tempo": tempo_gain,
        "loss_penalty": -loss_penalty,
        "march_penalty": -march_penalty,
        "stamina_penalty": -stamina_penalty,
        "risk_penalty": -risk_penalty,
    }
    return round(sum(breakdown.values()), 2), {key: round(value, 2) for key, value in breakdown.items()}
