from __future__ import annotations

from pathlib import Path

import yaml

from .models import KnowledgeEntry


def load_entries_from_file(path: Path) -> list[KnowledgeEntry]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        raise ValueError(f"Knowledge source must be a list: {path}")
    return [KnowledgeEntry.model_validate(item) for item in data]


def load_entries(paths: list[Path]) -> list[KnowledgeEntry]:
    entries: list[KnowledgeEntry] = []
    for path in sorted(paths):
        entries.extend(load_entries_from_file(path))
    return entries

