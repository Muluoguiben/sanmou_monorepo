from __future__ import annotations

from enum import Enum
from typing import Any, Mapping


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


_RISK_ORDER = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}


def normalize_risk_level(risk: RiskLevel | str | Mapping[str, Any] | None) -> RiskLevel:
    if risk is None:
        return RiskLevel.LOW
    if isinstance(risk, RiskLevel):
        return risk
    if isinstance(risk, str):
        return _normalize_risk_string(risk)

    for key in ("level", "risk_level", "severity"):
        value = risk.get(key)
        if isinstance(value, (RiskLevel, str)):
            return normalize_risk_level(value)

    score = risk.get("score")
    if isinstance(score, (int, float)):
        if score >= 0.85:
            return RiskLevel.CRITICAL
        if score >= 0.6:
            return RiskLevel.HIGH
        if score >= 0.3:
            return RiskLevel.MEDIUM
    return RiskLevel.LOW


def risk_at_least(level: RiskLevel, threshold: RiskLevel) -> bool:
    return _RISK_ORDER[level] >= _RISK_ORDER[threshold]


def _normalize_risk_string(value: str) -> RiskLevel:
    normalized = value.lower().strip()
    if normalized in {"safe", "none", "minimal"}:
        return RiskLevel.LOW
    for level in RiskLevel:
        if normalized == level.value:
            return level
    raise ValueError(f"unknown risk level: {value}")
