"""Fixed-position UI button registry.

Stores fractional (0-1) coordinates of stable UI elements like the bottom
menu (出城/武将/同盟/职业/征战军演) and the ESC close button. The controller
resolves these to pixel coordinates against the live window size before
dispatching click commands via bridge_client.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_LAYOUT_PATH = Path(__file__).resolve().parents[1] / "config" / "ui_layout.yaml"


@dataclass(frozen=True)
class UIButton:
    key: str
    label: str
    x_frac: float
    y_frac: float

    def resolve(self, window_width: int, window_height: int) -> tuple[int, int]:
        return (
            round(self.x_frac * window_width),
            round(self.y_frac * window_height),
        )


class UIRegistry:
    def __init__(self, buttons: dict[str, UIButton]) -> None:
        self._buttons = buttons

    @classmethod
    def load(cls, path: Path = DEFAULT_LAYOUT_PATH) -> "UIRegistry":
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        buttons: dict[str, UIButton] = {}
        for key, entry in (raw.get("buttons") or {}).items():
            buttons[key] = UIButton(
                key=key,
                label=entry.get("label", key),
                x_frac=float(entry["x"]),
                y_frac=float(entry["y"]),
            )
        return cls(buttons)

    def get(self, key: str) -> UIButton:
        if key not in self._buttons:
            raise KeyError(f"UI button '{key}' not in registry (known: {sorted(self._buttons)})")
        return self._buttons[key]

    def resolve_pixel(self, key: str, window_width: int, window_height: int) -> tuple[int, int]:
        return self.get(key).resolve(window_width, window_height)

    def keys(self) -> list[str]:
        return sorted(self._buttons)
