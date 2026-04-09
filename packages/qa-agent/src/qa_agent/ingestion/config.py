from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class AliasConfig(BaseModel):
    canonical_map: dict[str, str] = Field(default_factory=dict)
    aliases: dict[str, list[str]] = Field(default_factory=dict)


class EnumConfig(BaseModel):
    factions: dict[str, str] = Field(default_factory=dict)
    troop_types: dict[str, str] = Field(default_factory=dict)
    role_tags: dict[str, str] = Field(default_factory=dict)
    skill_types: dict[str, str] = Field(default_factory=dict)
    trigger_types: dict[str, str] = Field(default_factory=dict)
    target_scopes: dict[str, str] = Field(default_factory=dict)
    rarities: dict[str, str] = Field(default_factory=dict)


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file must be a mapping: {path}")
    return data


def load_alias_config(path: Path) -> AliasConfig:
    return AliasConfig.model_validate(_load_yaml(path))


def load_enum_config(path: Path) -> EnumConfig:
    return EnumConfig.model_validate(_load_yaml(path))

