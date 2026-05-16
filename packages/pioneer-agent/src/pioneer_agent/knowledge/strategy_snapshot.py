from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import yaml

REQUIRED_SECTIONS = (
    "schema_version",
    "generated_at",
    "sources",
    "building_priorities",
    "land_risk_rules",
    "lineup_hints",
)


@dataclass(frozen=True)
class StrategySnapshot:
    data: dict[str, Any]

    @property
    def schema_version(self) -> str:
        return str(self.data["schema_version"])

    @property
    def generated_at(self) -> str:
        return str(self.data["generated_at"])

    @property
    def sources(self) -> list[dict[str, Any]]:
        return list(self.data["sources"])

    def section(self, name: str) -> list[dict[str, Any]]:
        value = self.data.get(name, [])
        if not isinstance(value, list):
            raise ValueError(f"Snapshot section must be a list: {name}")
        return value

    def get(self, section: str, key: str, default: Any = None) -> dict[str, Any] | Any:
        for item in self.section(section):
            if item.get("key") == key:
                return item
        return default

    def get_building_priority(self, key: str, default: Any = None) -> dict[str, Any] | Any:
        return self.get("building_priorities", key, default)

    def get_land_risk_rule(self, key: str, default: Any = None) -> dict[str, Any] | Any:
        return self.get("land_risk_rules", key, default)

    def get_lineup_hint(self, key: str, default: Any = None) -> dict[str, Any] | Any:
        return self.get("lineup_hints", key, default)


def _validate_snapshot(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Strategy snapshot must be a mapping")
    missing = [section for section in REQUIRED_SECTIONS if section not in data]
    if missing:
        raise ValueError(f"Strategy snapshot missing required sections: {', '.join(missing)}")
    return data


def load_strategy_snapshot(path: Path) -> StrategySnapshot:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        data = yaml.safe_load(text)
    return StrategySnapshot(_validate_snapshot(data))
