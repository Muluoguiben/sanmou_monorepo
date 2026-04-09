"""Game knowledge config loader and data access."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_CONFIG_DIR = Path(__file__).parent


def get_config_dir() -> Path:
    """Return the directory containing game knowledge YAML files."""
    return _CONFIG_DIR


class ConfigLoader:
    """Generic YAML config loader scoped to a single directory."""

    def __init__(self, config_dir: Path) -> None:
        self.config_dir = config_dir

    def load_yaml(self, filename: str) -> dict[str, Any]:
        path = self.config_dir / filename
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    def load_all(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for path in sorted(self.config_dir.glob("*.yaml")):
            result[path.stem] = self.load_yaml(path.name)
        return result


def load_game_configs() -> dict[str, dict[str, Any]]:
    """Load all game knowledge configs from the bundled data."""
    return ConfigLoader(_CONFIG_DIR).load_all()
