"""Calibrate fixed-position UI buttons against a reference screenshot.

Uses the Gemini locator to find a button and prints the fractional
coordinates. If `--update` is passed, writes the result back into
`src/pioneer_agent/config/ui_layout.yaml`.

Usage:
  # Probe a single button
  PYTHONPATH=src python3 -m pioneer_agent.app.ui_calibrate \
      --image /tmp/city_building.png --button wu_jiang

  # Calibrate all default buttons and overwrite the YAML
  PYTHONPATH=src python3 -m pioneer_agent.app.ui_calibrate \
      --image /tmp/city_building.png --all --update
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml
from PIL import Image

from pioneer_agent.perception.ui_registry import DEFAULT_LAYOUT_PATH, UIRegistry
from pioneer_agent.perception.vision import VisionClient, find_elements

QUERIES: dict[str, str] = {
    "chu_cheng": "出城 button at bottom-left corner of the screen",
    "wu_jiang": "武将 (heroes) button in the bottom menu bar",
    "tong_meng": "同盟 (alliance) button in the bottom menu bar",
    "zhi_ye": "职业 (profession) button in the bottom menu bar",
    "zheng_zhan_jun_yan": "征战军演 (campaign/drill) button in the bottom-right menu",
    "esc_close": "close / ESC button (X icon) at the top-right of a popup",
}


def _calibrate_one(client: VisionClient, image_path: Path, key: str) -> tuple[float, float] | None:
    query = QUERIES.get(key)
    if query is None:
        print(f"[calibrate] no query for key '{key}'", file=sys.stderr)
        return None
    boxes = find_elements(client, image_path, query)
    if not boxes:
        print(f"[calibrate] {key}: no match", file=sys.stderr)
        return None
    img = Image.open(image_path)
    # Take the first/highest-confidence match; Gemini returns in reading order.
    box = boxes[0]
    x_center = (box.x_min + box.x_max) / 2 / 1000
    y_center = (box.y_min + box.y_max) / 2 / 1000
    pix_x = round(x_center * img.width)
    pix_y = round(y_center * img.height)
    print(
        f"[calibrate] {key}: label='{box.label}' frac=({x_center:.3f},{y_center:.3f}) "
        f"px=({pix_x},{pix_y}) on {img.width}x{img.height}"
    )
    return x_center, y_center


def _update_yaml(path: Path, updates: dict[str, tuple[float, float]]) -> None:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    buttons = raw.setdefault("buttons", {})
    for key, (x, y) in updates.items():
        entry = buttons.setdefault(key, {"label": key})
        entry["x"] = round(x, 4)
        entry["y"] = round(y, 4)
    path.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"[calibrate] wrote {len(updates)} entries → {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calibrate fixed UI button positions.")
    parser.add_argument("--image", type=Path, required=True, help="Reference screenshot.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--button", help="Single registry key to calibrate.")
    group.add_argument("--all", action="store_true", help="Calibrate every known key.")
    parser.add_argument("--update", action="store_true", help="Write results back to ui_layout.yaml.")
    parser.add_argument("--layout", type=Path, default=DEFAULT_LAYOUT_PATH)
    args = parser.parse_args(argv)

    # Surface current registry so user can compare.
    reg = UIRegistry.load(args.layout)
    print(f"[calibrate] current registry has {len(reg.keys())} buttons: {reg.keys()}", file=sys.stderr)

    client = VisionClient()
    keys = list(QUERIES) if args.all else [args.button]
    updates: dict[str, tuple[float, float]] = {}
    for key in keys:
        result = _calibrate_one(client, args.image, key)
        if result is not None:
            updates[key] = result

    if args.update and updates:
        _update_yaml(args.layout, updates)
    elif args.update:
        print("[calibrate] no updates to write", file=sys.stderr)
    return 0 if updates else 1


if __name__ == "__main__":
    raise SystemExit(main())
