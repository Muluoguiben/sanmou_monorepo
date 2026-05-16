from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


KILL_SWITCH_ENV = "SANMOU_KILL_SWITCH_FILE"


@dataclass(frozen=True)
class KillSwitch:
    """File-based local stop switch for runtime/executor input dispatch."""

    path: Path

    def is_triggered(self) -> bool:
        return self.path.exists()

    def trigger(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("stop\n", encoding="utf-8")

    def clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


def default_kill_switch_path(project_root: Path | None = None) -> Path:
    configured = os.environ.get(KILL_SWITCH_ENV)
    if configured:
        return Path(configured).expanduser()
    root = project_root or Path.cwd()
    return root / "data" / "runtime" / "KILL_SWITCH"
