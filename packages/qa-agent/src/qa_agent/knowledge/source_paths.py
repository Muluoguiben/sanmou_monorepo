from __future__ import annotations

from pathlib import Path


def discover_source_paths(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.yaml") if path.is_file())

