"""End-to-end vision probe: screenshot → Gemini → RuntimeState fragment.

Usage:
  # From a saved image file (no bridge needed)
  PYTHONPATH=src python3 -m pioneer_agent.app.vision_probe --image /tmp/game.png

  # Live capture via the Windows bridge (requires game running on Windows)
  PYTHONPATH=src python3 -m pioneer_agent.app.vision_probe --live

  # Live + save to state file:
  PYTHONPATH=src python3 -m pioneer_agent.app.vision_probe --live --out data/state.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from pioneer_agent.core.models import RuntimeState
from pioneer_agent.perception.domains import (
    apply_resource_bar,
    extract_resource_bar,
)


def _capture_live() -> bytes:
    from pioneer_agent.adapters.bridge_client import BridgeClient

    with BridgeClient() as bridge:
        return bridge.screenshot()


def _load_image(path: Path) -> bytes:
    return path.read_bytes()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the vision pipeline on one screenshot.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--image", type=Path, help="Path to a saved PNG screenshot.")
    source.add_argument("--live", action="store_true", help="Capture live via Windows bridge.")
    parser.add_argument("--out", type=Path, help="Write merged RuntimeState JSON to this path.")
    parser.add_argument("--state-in", type=Path, help="Merge into this existing RuntimeState JSON.")
    args = parser.parse_args(argv)

    image_bytes = _capture_live() if args.live else _load_image(args.image)
    print(f"[probe] image size: {len(image_bytes)} bytes", file=sys.stderr)

    fragment = extract_resource_bar(image_bytes, captured_at=datetime.now())
    print(f"[probe] page_type: {fragment.page_type}", file=sys.stderr)
    print(f"[probe] global_state: {fragment.global_state}", file=sys.stderr)
    print(f"[probe] economy: {fragment.economy}", file=sys.stderr)
    if fragment.notes:
        print(f"[probe] notes: {fragment.notes[:5]}", file=sys.stderr)

    if args.state_in is not None:
        state = RuntimeState.model_validate_json(args.state_in.read_text(encoding="utf-8"))
    else:
        state = RuntimeState()

    merged = apply_resource_bar(state, fragment)
    payload = merged.model_dump(mode="json", exclude_defaults=False)

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[probe] wrote merged state → {args.out}", file=sys.stderr)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
