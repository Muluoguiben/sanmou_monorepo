from __future__ import annotations

from typing import Any


def score_transfer(transfer: dict[str, Any]) -> tuple[float, dict[str, float]]:
    stamina_gain = max(float(transfer.get("target_stamina", 0)) - float(transfer.get("current_stamina", 0)), 0) * 2
    soldier_gain = max(float(transfer.get("target_soldiers", 0)) - float(transfer.get("current_soldiers", 0)), 0) / 150
    host_gain = max(float(transfer.get("target_host_score", 0)) - float(transfer.get("current_host_score", 0)), 0) / 2
    tempo_gain = 18.0 if transfer.get("target_position_context") == "outer" else 8.0
    execution_penalty = -18.0
    risk_penalty = -10.0
    breakdown = {
        "stamina_gain": stamina_gain,
        "soldier_gain": soldier_gain,
        "host_gain": host_gain,
        "tempo_gain": tempo_gain,
        "execution_penalty": execution_penalty,
        "risk_penalty": risk_penalty,
    }
    return round(sum(breakdown.values()), 2), {key: round(value, 2) for key, value in breakdown.items()}


def is_transfer_candidate_valid(current_host: dict[str, Any], target_host: dict[str, Any], swap_window: dict[str, Any], carrier_pool: list[dict[str, Any]]) -> bool:
    if not swap_window.get("enabled"):
        return False
    if current_host.get("team_id") == target_host.get("team_id"):
        return False
    if not target_host.get("exists") or not target_host.get("slot_unlocked", True):
        return False
    if not target_host.get("can_host_now", True):
        return False
    if float(target_host.get("container_stamina", 0)) <= float(current_host.get("container_stamina", 0)):
        return False
    return any(carrier.get("usable_for_swap") for carrier in carrier_pool)
