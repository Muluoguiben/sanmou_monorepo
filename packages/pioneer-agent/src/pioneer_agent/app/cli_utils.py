"""Small shared helpers for app CLIs."""
from __future__ import annotations

from pathlib import Path


def user_path(value: str) -> Path:
    """argparse type for filesystem arguments: expands `~` so an operator's
    `--state ~/x.json` targets the home directory instead of silently creating
    a literal './~/' tree."""
    return Path(value).expanduser()
