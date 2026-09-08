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
    seen: set[str] = set()
    for path in sorted(paths):
        for entry in load_entries_from_file(path):
            if entry.id in seen:
                raise ValueError(f"Duplicate knowledge entry id: {entry.id}")
            seen.add(entry.id)
            entries.append(entry)
    return entries

